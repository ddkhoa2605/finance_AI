"""Generate deterministic Phase 7 what-if scenarios and comparisons."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from calculation.finance import OPERATING_ACCOUNTS, reconstruct_operating_finance, validate_operating_finance
from scenarios.engine import LocalScenarioEngine
from scenarios.registry import build_registry
from verify_phase5_snapshot import MANIFEST_PATH, verify_entry


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_CONFIG_PATH = PROJECT_ROOT / "config" / "scenarios.yaml"
OPEX_CONFIG_PATH = PROJECT_ROOT / "config" / "opex.yaml"
FINANCE_FACT_PATH = PROJECT_ROOT / "data" / "processed" / "finance_fact.csv"
BASELINE_DRIVER_PATHS = {
    "ACTUAL": PROJECT_ROOT / "data" / "processed" / "drivers.csv",
    "BUDGET": PROJECT_ROOT / "data" / "processed" / "budget_drivers.csv",
    "FORECAST": PROJECT_ROOT / "data" / "processed" / "forecast_drivers.csv",
}
PHASE6_PROTECTED_PATHS = [
    PROJECT_ROOT / "data" / "anomaly_benchmark" / "drivers_with_events.csv",
    PROJECT_ROOT / "data" / "anomaly_benchmark" / "finance_fact_with_events.csv",
    PROJECT_ROOT / "data" / "anomaly_benchmark" / "event_impacts.csv",
    PROJECT_ROOT / "data" / "ground_truth" / "events.json",
]

OUTPUT_DIR = PROJECT_ROOT / "data" / "scenarios"
DRIVERS_OUTPUT_PATH = OUTPUT_DIR / "scenario_drivers.csv"
FINANCE_OUTPUT_PATH = OUTPUT_DIR / "scenario_finance.csv"
COMPARISON_OUTPUT_PATH = OUTPUT_DIR / "scenario_comparison.csv"
REGISTRY_OUTPUT_PATH = OUTPUT_DIR / "scenario_registry.json"
REPORT_PATH = PROJECT_ROOT / "reports" / "scenario_generation_report.md"

DRIVER_SORT = ["period_date", "country", "product", "segment"]
FINANCE_SORT = [
    "period_date", "country", "product", "segment", "department", "account", "version"
]


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_phase5_snapshot() -> dict:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError("Phase 5 snapshot manifest is required for Phase 7.")
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    failures = []
    for section in ["strict_artifacts", "source_files"]:
        for relative_path, expected in manifest[section].items():
            failures.extend(verify_entry(relative_path, expected))
    if failures:
        raise ValueError("Phase 5 baseline drift detected:\n" + "\n".join(failures))
    return manifest


def hash_existing(paths: list[Path]) -> dict[str, str]:
    return {
        str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"): sha256(path)
        for path in paths
        if path.exists()
    }


def load_baseline_drivers() -> dict[str, pd.DataFrame]:
    baselines = {}
    for version, path in BASELINE_DRIVER_PATHS.items():
        frame = pd.read_csv(path, parse_dates=["period_date"])
        frame = frame.loc[frame["version"] == version].copy()
        if frame.empty:
            raise ValueError(f"{path.name} contains no {version} driver rows.")
        baselines[version] = frame.sort_values(DRIVER_SORT).reset_index(drop=True)
    return baselines


def load_baseline_finance() -> dict[str, pd.DataFrame]:
    finance = pd.read_csv(FINANCE_FACT_PATH, parse_dates=["period_date"])
    result = {}
    for version in BASELINE_DRIVER_PATHS:
        selected = finance.loc[finance["version"] == version].copy()
        if selected.empty:
            raise ValueError(f"finance_fact.csv contains no {version} rows.")
        result[version] = selected.sort_values(
            FINANCE_SORT, na_position="last"
        ).reset_index(drop=True)
    return result


def validate_all_baselines(
    baselines: dict[str, pd.DataFrame],
    baseline_finance: dict[str, pd.DataFrame],
    opex_config: dict,
    tolerance: float,
) -> None:
    for version, drivers in baselines.items():
        driver_grain = ["period_date", "country", "product", "segment", "version"]
        if drivers.duplicated(driver_grain).any():
            raise ValueError(f"Authoritative {version} driver grain is not unique.")
        if (drivers[["units", "average_sale_price", "unit_cogs"]] < 0).any().any():
            raise ValueError(f"Authoritative {version} drivers contain negative values.")
        if not drivers["discount_rate"].between(0, 1).all():
            raise ValueError(f"Authoritative {version} Discount Rate is outside [0, 1].")
        operating = reconstruct_operating_finance(
            drivers,
            version=version,
            source="scenario_baseline_validation",
        )
        validate_operating_finance(operating, tolerance)
        authoritative = baseline_finance[version]
        keys = [
            "period_date", "country", "product", "segment", "account", "version"
        ]
        expected = authoritative.loc[
            authoritative["account"].isin(OPERATING_ACCOUNTS), keys + ["amount"]
        ]
        check = operating[keys + ["amount"]].merge(
            expected,
            on=keys,
            how="outer",
            suffixes=("_reconstructed", "_authoritative"),
            indicator=True,
            validate="one_to_one",
        )
        if (check["_merge"] != "both").any() or check[
            ["amount_reconstructed", "amount_authoritative"]
        ].isna().any().any() or not np.allclose(
            check["amount_reconstructed"],
            check["amount_authoritative"],
            atol=tolerance,
        ):
            raise ValueError(
                f"Reconstructed {version} operating baseline does not match finance_fact.csv."
            )

        finance_grain = [
            "period_date", "country", "product", "segment", "department", "account", "version"
        ]
        if authoritative.duplicated(finance_grain).any():
            raise ValueError(f"Authoritative {version} finance grain is not unique.")
        department = authoritative.loc[
            authoritative["account"].str.startswith("OPEX_")
            & (authoritative["account"] != "OPEX_TOTAL")
        ]
        if (department["amount"] < 0).any():
            raise ValueError(f"Authoritative {version} department OPEX is negative.")
        expected_departments = len(opex_config["departments"])
        coverage = department.groupby(["period_date", "country"])["account"].nunique()
        if not (coverage == expected_departments).all():
            raise ValueError(f"Authoritative {version} OPEX department coverage is incomplete.")
        department_sum = department.groupby(["period_date", "country"])["amount"].sum()
        opex_total = authoritative.loc[
            authoritative["account"] == "OPEX_TOTAL"
        ].set_index(["period_date", "country"])["amount"]
        if not np.allclose(
            department_sum.sort_index(), opex_total.sort_index(), atol=tolerance
        ):
            raise ValueError(f"Authoritative {version} OPEX Total does not reconcile.")
        gross_profit = authoritative.loc[
            authoritative["account"] == "GROSS_PROFIT"
        ].groupby(["period_date", "country"])["amount"].sum()
        ebitda = authoritative.loc[authoritative["account"] == "EBITDA"].set_index(
            ["period_date", "country"]
        )["amount"]
        if not np.allclose(
            gross_profit.sort_index() - opex_total.sort_index(),
            ebitda.sort_index(),
            atol=tolerance,
        ):
            raise ValueError(f"Authoritative {version} EBITDA does not reconcile.")
        expected_rows = len(drivers) * len(OPERATING_ACCOUNTS) + len(coverage) * (
            expected_departments + 2
        )
        if len(authoritative) != expected_rows:
            raise ValueError(f"Authoritative {version} finance row coverage mismatch.")


def add_output_metadata(result: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    request = result["request"]
    drivers = result["scenario_drivers"].copy()
    finance = result["scenario_finance"].copy()
    for frame in [drivers, finance]:
        frame.insert(0, "base_version", request["base_version"])
        frame.insert(0, "scenario_name", request["name"])
        frame.insert(0, "scenario_id", request["scenario_id"])
    return drivers, finance


def assert_result_equal(first: dict, second: dict) -> None:
    for key in ["scenario_drivers", "scenario_operating", "scenario_finance", "comparison"]:
        pd.testing.assert_frame_equal(first[key], second[key], check_exact=True)
    for key in ["department", "opex_total", "ebitda", "output"]:
        pd.testing.assert_frame_equal(
            first["scenario_opex"][key], second["scenario_opex"][key], check_exact=True
        )
    if first["metadata"] != second["metadata"]:
        raise ValueError("Scenario metadata is not deterministic.")


def validate_combined_outputs(
    drivers: pd.DataFrame,
    finance: pd.DataFrame,
    comparison: pd.DataFrame,
    scenario_ids: set[str],
    tolerance: float,
) -> None:
    if set(drivers["scenario_id"]) != scenario_ids:
        raise ValueError("Combined scenario drivers have incomplete scenario coverage.")
    if set(finance["scenario_id"]) != scenario_ids:
        raise ValueError("Combined scenario finance has incomplete scenario coverage.")
    if set(comparison["scenario_id"]) != scenario_ids:
        raise ValueError("Combined comparison has incomplete scenario coverage.")
    driver_grain = [
        "scenario_id", "period_date", "country", "product", "segment", "version"
    ]
    finance_grain = [
        "scenario_id", "period_date", "country", "product", "segment", "department",
        "account", "version",
    ]
    if drivers.duplicated(driver_grain).any() or finance.duplicated(finance_grain).any():
        raise ValueError("Combined scenario output grain is not unique.")
    if (drivers[["units", "average_sale_price", "unit_cogs"]] < 0).any().any():
        raise ValueError("Combined scenario drivers contain negative values.")
    if not drivers["discount_rate"].between(0, 1).all():
        raise ValueError("Combined scenario Discount Rate is outside [0, 1].")
    if not np.allclose(
        comparison["scenario_value"] - comparison["baseline_value"],
        comparison["impact"],
        atol=tolerance,
    ):
        raise ValueError("Scenario comparison impact reconciliation failed.")
    if comparison[["baseline_value", "scenario_value", "impact"]].isna().any().any():
        raise ValueError("Scenario comparison contains a missing primary value.")

    for scenario_id in scenario_ids:
        subset = finance.loc[finance["scenario_id"] == scenario_id]
        operating = subset.loc[subset["account"].isin(OPERATING_ACCOUNTS)].drop(
            columns=["scenario_id", "scenario_name", "base_version"]
        )
        validate_operating_finance(operating, tolerance)
        department = subset.loc[
            subset["account"].str.startswith("OPEX_")
            & (subset["account"] != "OPEX_TOTAL")
        ]
        totals = department.groupby(["period_date", "country"])["amount"].sum()
        reported = subset.loc[subset["account"] == "OPEX_TOTAL"].set_index(
            ["period_date", "country"]
        )["amount"]
        if not np.allclose(totals.sort_index(), reported.sort_index(), atol=tolerance):
            raise ValueError(f"OPEX Total round-trip failed for {scenario_id}.")
        gp = subset.loc[subset["account"] == "GROSS_PROFIT"].groupby(
            ["period_date", "country"]
        )["amount"].sum()
        ebitda = subset.loc[subset["account"] == "EBITDA"].set_index(
            ["period_date", "country"]
        )["amount"]
        if not np.allclose(
            gp.sort_index() - reported.sort_index(), ebitda.sort_index(), atol=tolerance
        ):
            raise ValueError(f"EBITDA round-trip failed for {scenario_id}.")


def validate_csv_round_trip(
    drivers: pd.DataFrame,
    finance: pd.DataFrame,
    comparison: pd.DataFrame,
    scenario_ids: set[str],
    tolerance: float,
) -> None:
    loaded_drivers = pd.read_csv(DRIVERS_OUTPUT_PATH, parse_dates=["period_date"])
    loaded_finance = pd.read_csv(FINANCE_OUTPUT_PATH, parse_dates=["period_date"])
    loaded_comparison = pd.read_csv(COMPARISON_OUTPUT_PATH)
    if list(loaded_drivers.columns) != list(drivers.columns):
        raise ValueError("Scenario driver CSV round-trip changed schema.")
    if list(loaded_finance.columns) != list(finance.columns):
        raise ValueError("Scenario finance CSV round-trip changed schema.")
    if list(loaded_comparison.columns) != list(comparison.columns):
        raise ValueError("Scenario comparison CSV round-trip changed schema.")
    if (len(loaded_drivers), len(loaded_finance), len(loaded_comparison)) != (
        len(drivers), len(finance), len(comparison)
    ):
        raise ValueError("Scenario CSV round-trip changed row counts.")
    validate_combined_outputs(
        loaded_drivers, loaded_finance, loaded_comparison, scenario_ids, tolerance
    )


def lever_summary(request: dict) -> str:
    labels = {
        "units_change_pct": "Units",
        "price_change_pct": "Price",
        "discount_rate_change_pp": "Discount Rate",
        "unit_cogs_change_pct": "Unit COGS",
    }
    parts = []
    for key, label in labels.items():
        value = float(request["levers"].get(key, 0.0))
        if value != 0:
            suffix = "pp" if key == "discount_rate_change_pp" else "%"
            display = value * 100
            parts.append(f"{label} {display:+.1f}{suffix}")
    for department, value in (
        request["levers"].get("department_opex_change_pct", {}) or {}
    ).items():
        parts.append(f"{department} OPEX {float(value) * 100:+.1f}%")
    return "; ".join(parts)


def write_report(
    config: dict,
    results: list[dict],
    drivers: pd.DataFrame,
    finance: pd.DataFrame,
    comparison: pd.DataFrame,
    validations: list[str],
) -> None:
    summary_rows = []
    for result in results:
        request = result["request"]
        impacts = result["comparison"].set_index("metric")["impact"]
        summary_rows.append(
            {
                "scenario_id": request["scenario_id"],
                "name": request["name"],
                "baseline": request["base_version"],
                "lever": lever_summary(request),
                "scope_driver_rows": result["metadata"]["matched_driver_rows"],
                "opex_rows": sum(result["metadata"]["matched_department_opex_rows"].values()),
                "revenue_impact": impacts["REVENUE"],
                "gross_profit_impact": impacts["GROSS_PROFIT"],
                "opex_total_impact": impacts["OPEX_TOTAL"],
                "ebitda_impact": impacts["EBITDA"],
            }
        )
    summary = pd.DataFrame(summary_rows)
    driver_comparison = comparison.loc[
        comparison["metric_type"] == "driver",
        ["scenario_id", "metric", "baseline_value", "scenario_value", "impact", "impact_pct"],
    ]
    check_lines = "\n".join(f"- {check}: passed" for check in validations)
    content = f"""# Scenario Generation Report

## Pipeline Result

- Status: passed
- Engine: LocalScenarioEngine
- Default baseline: {config['default_base_version']}
- Scenarios generated: {len(results)}
- Scenario driver rows: {len(drivers):,}
- Scenario finance rows: {len(finance):,}
- Scenario comparison rows: {len(comparison):,}

Scenario is a deterministic management simulation, not a forecast or prediction.
Each scenario starts from canonical baseline drivers, leaves the baseline untouched,
reconstructs the five operating accounts, recalculates revenue-linked OPEX, applies
any explicit department OPEX lever, and finally recalculates OPEX Total and EBITDA.

For a Budget baseline, authoritative management-plan OPEX is preserved as the base;
the shared OPEX engine contributes only the incremental change caused by scenario
Revenue. This prevents an unrelated Budget-versus-synthetic-methodology variance.

## Scenario Impact Summary

{summary.to_markdown(index=False, floatfmt='.2f')}

Financial impacts use company-wide totals within the scenario period so that
cross-country fixed-OPEX allocation effects are not omitted. Driver comparisons use
the direct request scope.

## Driver Comparison

{driver_comparison.to_markdown(index=False, floatfmt='.6f')}

For percentage levers, the request value is multiplicative change (for example
`0.03` means +3%). `discount_rate_change_pp` is additive percentage points. No price
elasticity or other implicit driver relationship is assumed in V1.

## Validation Checks

{check_lines}

## Isolation and Lineage

- Supported baselines validated: ACTUAL, BUDGET, FORECAST
- Default forward-looking baseline: FORECAST
- Anomaly benchmark is never used as a Scenario Engine baseline
- Phase 2-6 protected artifacts are hash-identical before and after generation
- Shared finance engine: `scripts/calculation/finance.py`
- Shared OPEX engine: `scripts/calculation/opex.py`
- Structured scenario assumptions: `config/scenarios.yaml`
- Registry contains request, config, baseline and output hashes; no runtime timestamp

## Output Files

- `data/scenarios/scenario_drivers.csv`: {len(drivers):,} rows
- `data/scenarios/scenario_finance.csv`: {len(finance):,} rows
- `data/scenarios/scenario_comparison.csv`: {len(comparison):,} rows
- `data/scenarios/scenario_registry.json`: {len(results)} scenarios
"""
    REPORT_PATH.write_text(content, encoding="utf-8")


def main() -> None:
    phase5_manifest = verify_phase5_snapshot()
    protected_paths = [
        PROJECT_ROOT / path for path in phase5_manifest["strict_artifacts"]
    ] + PHASE6_PROTECTED_PATHS
    protected_before = hash_existing(protected_paths)

    config = load_yaml(SCENARIO_CONFIG_PATH)
    opex_config = load_yaml(OPEX_CONFIG_PATH)
    tolerance = float(config["tolerance"])
    requests = config["scenarios"]
    scenario_ids = [request.get("scenario_id") for request in requests]
    if len(scenario_ids) != len(set(scenario_ids)):
        raise ValueError("Scenario IDs must be unique; duplicate registry entries are not allowed.")

    baselines = load_baseline_drivers()
    baseline_finance = load_baseline_finance()
    validate_all_baselines(baselines, baseline_finance, opex_config, tolerance)
    engine = LocalScenarioEngine(baselines, baseline_finance, config, opex_config)
    results = [engine.run(request) for request in requests]

    rerun_results = [engine.run(request) for request in requests]
    for first, second in zip(results, rerun_results, strict=True):
        assert_result_equal(first, second)
    shuffled_engine = LocalScenarioEngine(
        {
            version: frame.sample(frac=1, random_state=42).reset_index(drop=True)
            for version, frame in baselines.items()
        },
        {
            version: frame.sample(frac=1, random_state=84).reset_index(drop=True)
            for version, frame in baseline_finance.items()
        },
        config,
        opex_config,
    )
    shuffled_results = [shuffled_engine.run(request) for request in requests]
    for first, shuffled in zip(results, shuffled_results, strict=True):
        assert_result_equal(first, shuffled)

    driver_frames = []
    finance_frames = []
    for result in results:
        drivers, finance = add_output_metadata(result)
        driver_frames.append(drivers)
        finance_frames.append(finance)
    scenario_drivers = pd.concat(driver_frames, ignore_index=True).sort_values(
        ["scenario_id"] + DRIVER_SORT
    ).reset_index(drop=True)
    scenario_finance = pd.concat(finance_frames, ignore_index=True).sort_values(
        ["scenario_id"] + FINANCE_SORT, na_position="last"
    ).reset_index(drop=True)
    scenario_comparison = pd.concat(
        [result["comparison"] for result in results], ignore_index=True
    ).sort_values(["scenario_id", "metric_type", "metric"]).reset_index(drop=True)
    expected_ids = set(scenario_ids)
    validate_combined_outputs(
        scenario_drivers, scenario_finance, scenario_comparison, expected_ids, tolerance
    )

    baseline_lineage = {
        version: {
            "path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "sha256": sha256(path),
            "rows": len(baselines[version]),
        }
        for version, path in BASELINE_DRIVER_PATHS.items()
    }
    registry = build_registry(
        results,
        engine.get_metadata(),
        sha256(SCENARIO_CONFIG_PATH),
        baseline_lineage,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    scenario_drivers.to_csv(DRIVERS_OUTPUT_PATH, index=False)
    scenario_finance.to_csv(FINANCE_OUTPUT_PATH, index=False)
    scenario_comparison.to_csv(COMPARISON_OUTPUT_PATH, index=False)
    REGISTRY_OUTPUT_PATH.write_text(
        json.dumps(registry, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    validate_csv_round_trip(
        scenario_drivers, scenario_finance, scenario_comparison, expected_ids, tolerance
    )

    verify_phase5_snapshot()
    protected_after = hash_existing(protected_paths)
    if protected_before != protected_after:
        raise ValueError("A protected Phase 2–6 artifact changed during Scenario generation.")

    validations = [
        "scenario_engine_interface_and_local_implementation",
        "actual_budget_forecast_baselines_selectable_and_reconciled",
        "baseline_and_anomaly_artifacts_preserved",
        "scenario_ids_unique",
        "scope_nonzero_and_isolated",
        "explicit_driver_lever_magnitude",
        "no_implicit_elasticity",
        "driver_grain_unique_and_bounds_valid",
        "finance_reconstruction",
        "five_department_opex_coverage",
        "department_opex_lever_magnitude",
        "opex_total_reconciliation",
        "ebitda_reconciliation",
        "scenario_vs_baseline_comparison",
        "sample_scenario_causal_directions",
        "derived_row_coverage",
        "deterministic_rerun",
        "row_order_independence",
        "csv_round_trip",
    ]
    write_report(
        config,
        results,
        scenario_drivers,
        scenario_finance,
        scenario_comparison,
        validations,
    )

    print("PHASE_7_STATUS=PASS")
    print(f"SCENARIOS={len(results)}")
    print(f"SCENARIO_DRIVER_ROWS={len(scenario_drivers)}")
    print(f"SCENARIO_FINANCE_ROWS={len(scenario_finance)}")
    print(f"SCENARIO_COMPARISON_ROWS={len(scenario_comparison)}")
    for result in results:
        print(
            f"{result['request']['scenario_id']}_MATCHED_DRIVER_ROWS="
            f"{result['metadata']['matched_driver_rows']}"
        )
    print(f"REPORT={REPORT_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
