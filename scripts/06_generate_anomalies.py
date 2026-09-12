"""Build an isolated, deterministic controlled-event benchmark for Phase 6."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import yaml

from anomalies.ground_truth import build_event_impacts, build_events_ground_truth
from anomalies.injector import (
    apply_driver_events,
    apply_opex_events,
    validate_event_config,
    validate_no_direct_overlap,
)
from anomalies.validators import (
    validate_baseline_reconstruction,
    validate_benchmark,
    validate_exact_event_operations,
    validate_impact_directions,
)
from calculation.finance import OPERATING_ACCOUNTS, reconstruct_operating_finance
from calculation.opex import assert_noise_order_independent, generate_opex
from verify_phase5_snapshot import MANIFEST_PATH, verify_entry


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DRIVERS_PATH = PROJECT_ROOT / "data" / "processed" / "drivers.csv"
ACTUAL_PATH = PROJECT_ROOT / "data" / "processed" / "actual.csv"
OPEX_PATH = PROJECT_ROOT / "data" / "processed" / "opex.csv"
ANOMALY_CONFIG_PATH = PROJECT_ROOT / "config" / "anomalies.yaml"
OPEX_CONFIG_PATH = PROJECT_ROOT / "config" / "opex.yaml"

BENCHMARK_DIR = PROJECT_ROOT / "data" / "anomaly_benchmark"
GROUND_TRUTH_DIR = PROJECT_ROOT / "data" / "ground_truth"
DRIVERS_OUTPUT_PATH = BENCHMARK_DIR / "drivers_with_events.csv"
FINANCE_OUTPUT_PATH = BENCHMARK_DIR / "finance_fact_with_events.csv"
IMPACTS_OUTPUT_PATH = BENCHMARK_DIR / "event_impacts.csv"
EVENTS_OUTPUT_PATH = GROUND_TRUTH_DIR / "events.json"
REPORT_PATH = PROJECT_ROOT / "reports" / "anomaly_generation_report.md"

OPEX_SOURCE = "controlled_event_opex_v1"
EBITDA_SOURCE = "derived_controlled_event_v1"
DRIVER_GRAIN = ["period_date", "country", "product", "segment", "version"]
FINANCE_SORT = [
    "period_date", "country", "product", "segment", "department", "account", "version"
]


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_phase5_baseline() -> dict:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            "Phase 5 snapshot is required before creating the anomaly benchmark."
        )
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    failures = []
    for section in ["strict_artifacts", "source_files"]:
        for relative_path, expected in manifest[section].items():
            failures.extend(verify_entry(relative_path, expected))
    if failures:
        raise ValueError("Phase 5 baseline drift detected:\n" + "\n".join(failures))
    return manifest


def load_baseline(year: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    drivers = pd.read_csv(DRIVERS_PATH, parse_dates=["period_date"])
    actual = pd.read_csv(ACTUAL_PATH, parse_dates=["period_date"])
    opex = pd.read_csv(OPEX_PATH, parse_dates=["period_date"])

    drivers = drivers.loc[
        (drivers["version"] == "ACTUAL") & (drivers["period_date"].dt.year == year)
    ].copy()
    actual = actual.loc[
        (actual["version"] == "ACTUAL") & (actual["period_date"].dt.year == year)
    ].copy()
    opex = opex.loc[
        (opex["version"] == "ACTUAL") & (opex["period_date"].dt.year == year)
    ].copy()
    if drivers.empty or actual.empty or opex.empty:
        raise ValueError(f"Authoritative Actual inputs have no complete benchmark data for {year}.")
    return drivers, actual, opex


def build_scenario(
    base_drivers: pd.DataFrame,
    events: list[dict],
    anomaly_config: dict,
    opex_config: dict,
) -> dict:
    changed_drivers, driver_matches = apply_driver_events(base_drivers, events)
    changed_drivers["version"] = anomaly_config["benchmark_version"]
    changed_drivers["source"] = anomaly_config["source_name"]
    changed_drivers = changed_drivers.sort_values(DRIVER_GRAIN).reset_index(drop=True)

    operating = reconstruct_operating_finance(
        changed_drivers,
        version=anomaly_config["benchmark_version"],
        source=anomaly_config["source_name"],
    )
    opex = generate_opex(
        operating,
        opex_config,
        version=anomaly_config["benchmark_version"],
        source_name=OPEX_SOURCE,
        ebitda_source=EBITDA_SOURCE,
    )
    opex, opex_matches = apply_opex_events(
        opex,
        events,
        source_name=OPEX_SOURCE,
        ebitda_source=EBITDA_SOURCE,
    )
    finance = pd.concat([operating, opex["output"]], ignore_index=True).sort_values(
        FINANCE_SORT, na_position="last"
    ).reset_index(drop=True)
    matches = {**driver_matches, **opex_matches}
    return {
        "drivers": changed_drivers,
        "operating": operating,
        "opex": opex,
        "finance": finance,
        "matched_rows": matches,
    }


def assert_scenario_equal(first: dict, second: dict) -> None:
    for key in ["drivers", "operating", "finance"]:
        pd.testing.assert_frame_equal(first[key], second[key], check_exact=True)
    for key in ["department", "opex_total", "ebitda", "output"]:
        pd.testing.assert_frame_equal(
            first["opex"][key], second["opex"][key], check_exact=True
        )
    if first["matched_rows"] != second["matched_rows"]:
        raise ValueError("Event match counts are not deterministic.")


def write_report(
    config: dict,
    impacts: pd.DataFrame,
    scenario: dict,
    validation_names: list[str],
    phase5_manifest: dict,
) -> None:
    event_rows = []
    for event in config["events"]:
        filters = ", ".join(
            f"{key}={event[key]}"
            for key in ["country", "product", "segment", "department"]
            if event.get(key) is not None
        )
        event_rows.append(
            {
                "event_id": event["event_id"],
                "type": event["event_type"],
                "period": (
                    f"{pd.Timestamp(event['period_start']).strftime('%Y-%m-%d')} to "
                    f"{pd.Timestamp(event['period_end']).strftime('%Y-%m-%d')}"
                ),
                "scope": filters,
                "operation": f"{event['operation']} {float(event['value']):g}",
                "matched_rows": scenario["matched_rows"][event["event_id"]],
                "root_cause": event["root_cause"],
            }
        )
    event_table = pd.DataFrame(event_rows).to_markdown(index=False)
    impact_table = impacts[
        [
            "event_id", "metric", "before", "after", "delta", "delta_pct",
            "expected_direction", "actual_direction", "direction_pass",
        ]
    ].to_markdown(index=False, floatfmt=".6f")
    validation_lines = "\n".join(f"- {name}: passed" for name in validation_names)
    content = f"""# Anomaly Generation Report

## Pipeline Result

- Status: passed
- Benchmark year: {int(config['benchmark_year'])}
- Benchmark version: {config['benchmark_version']}
- Events: {len(config['events'])}
- Driver rows: {len(scenario['drivers']):,}
- Finance fact rows: {len(scenario['finance']):,}
- Phase 5 snapshot: {phase5_manifest['snapshot_tag']} (unchanged)

The benchmark is an isolated copy of authoritative Actual 2014. It does not retrain
the Phase 5 forecast and does not overwrite any file under `data/processed/`.

## Controlled Events

{event_table}

Events are cumulative in the final benchmark. Event-level impacts below are measured
using one isolated event at a time against the same reconstructed baseline, which
keeps the ground-truth attribution unambiguous.

EVT_001 has a counterintuitive local EBITDA result: its Gross Profit decreases, but
the shared revenue-linked and country-allocated OPEX engine reduces Mexico OPEX by a
larger amount. The observed EBITDA increase is therefore recorded as ground truth,
not replaced with an assumed direction.

## Event Impacts

{impact_table}

`delta_pct` is calculated as `(after - before) / abs(before)`. A blank value means
the baseline metric is zero. Discount event value `0.05` means five percentage
points, not a five-percent multiplier.

## Validation Checks

{validation_lines}

## Lineage and Isolation

- Authoritative driver input: `data/processed/drivers.csv`
- Shared finance engine: `scripts/calculation/finance.py`
- Shared OPEX engine: `scripts/calculation/opex.py`
- Event configuration: `config/anomalies.yaml`
- Ground truth attribution: isolated event versus baseline
- Final benchmark semantics: all configured events applied cumulatively
- Phase 5 baseline SHA-256 checks: passed before and after generation

## Output Files

- `data/anomaly_benchmark/drivers_with_events.csv`: {len(scenario['drivers']):,} rows
- `data/anomaly_benchmark/finance_fact_with_events.csv`: {len(scenario['finance']):,} rows
- `data/anomaly_benchmark/event_impacts.csv`: {len(impacts):,} rows
- `data/ground_truth/events.json`: {len(config['events']):,} events
"""
    REPORT_PATH.write_text(content, encoding="utf-8")


def validate_csv_round_trip(scenario: dict, config: dict, opex_config: dict) -> None:
    drivers = pd.read_csv(DRIVERS_OUTPUT_PATH, parse_dates=["period_date"])
    finance = pd.read_csv(FINANCE_OUTPUT_PATH, parse_dates=["period_date"])
    if list(drivers.columns) != list(scenario["drivers"].columns):
        raise ValueError("Driver CSV round-trip changed the schema.")
    if list(finance.columns) != list(scenario["finance"].columns):
        raise ValueError("Finance CSV round-trip changed the schema.")
    if len(drivers) != len(scenario["drivers"]) or len(finance) != len(scenario["finance"]):
        raise ValueError("CSV round-trip changed a benchmark row count.")

    operating = finance.loc[finance["account"].isin(OPERATING_ACCOUNTS)].copy()
    round_trip_opex = {key: value.copy() for key, value in scenario["opex"].items()}
    round_trip_opex["department"] = finance.loc[
        finance["account"].str.startswith("OPEX_")
        & (finance["account"] != "OPEX_TOTAL")
    ].copy()
    round_trip_opex["opex_total"] = finance.loc[
        finance["account"] == "OPEX_TOTAL"
    ].copy()
    round_trip_opex["ebitda"] = finance.loc[finance["account"] == "EBITDA"].copy()
    round_trip_opex["output"] = finance.loc[
        ~finance["account"].isin(OPERATING_ACCOUNTS)
    ].copy()
    validate_benchmark(
        drivers,
        operating,
        round_trip_opex,
        finance,
        {**config, "opex_config": opex_config},
    )


def main() -> None:
    phase5_manifest = verify_phase5_baseline()
    baseline_hashes_before = {
        path: sha256(PROJECT_ROOT / path)
        for path in phase5_manifest["strict_artifacts"]
    }
    config = load_yaml(ANOMALY_CONFIG_PATH)
    opex_config = load_yaml(OPEX_CONFIG_PATH)
    events = config["events"]
    tolerance = float(config["tolerance"])
    validate_event_config(events)

    base_drivers, actual, authoritative_opex = load_baseline(
        int(config["benchmark_year"])
    )
    validate_no_direct_overlap(base_drivers, events)

    baseline = build_scenario(base_drivers, [], config, opex_config)
    validate_baseline_reconstruction(
        baseline["operating"], actual, baseline["opex"]["output"],
        authoritative_opex, tolerance,
    )

    isolated = {
        event["event_id"]: build_scenario(base_drivers, [event], config, opex_config)
        for event in events
    }
    matched_rows = {
        event_id: scenario["matched_rows"][event_id]
        for event_id, scenario in isolated.items()
    }
    validate_exact_event_operations(baseline, isolated, events, tolerance)
    impacts = build_event_impacts(events, baseline, isolated, matched_rows, tolerance)
    validate_impact_directions(impacts)

    scenario = build_scenario(base_drivers, events, config, opex_config)
    validate_benchmark(
        scenario["drivers"], scenario["operating"], scenario["opex"],
        scenario["finance"], {**config, "opex_config": opex_config},
    )
    rerun = build_scenario(base_drivers, events, config, opex_config)
    assert_scenario_equal(scenario, rerun)
    shuffled = build_scenario(
        base_drivers.sample(frac=1, random_state=42).reset_index(drop=True),
        events,
        config,
        opex_config,
    )
    assert_scenario_equal(scenario, shuffled)
    assert_noise_order_independent(
        scenario["operating"], opex_config, config["benchmark_version"],
        OPEX_SOURCE, EBITDA_SOURCE,
    )

    expected_driver_rows = len(base_drivers)
    expected_operating_rows = expected_driver_rows * len(OPERATING_ACCOUNTS)
    country_month_count = len(
        scenario["operating"][["period_date", "country"]].drop_duplicates()
    )
    department_count = len(opex_config["departments"])
    expected_finance_rows = (
        expected_operating_rows
        + country_month_count * department_count
        + country_month_count * 2
    )
    if len(scenario["drivers"]) != expected_driver_rows:
        raise ValueError("Anomaly driver row coverage mismatch.")
    if len(scenario["finance"]) != expected_finance_rows:
        raise ValueError("Anomaly finance row coverage mismatch.")

    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    GROUND_TRUTH_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    scenario["drivers"].to_csv(DRIVERS_OUTPUT_PATH, index=False)
    scenario["finance"].to_csv(FINANCE_OUTPUT_PATH, index=False)
    impacts.to_csv(IMPACTS_OUTPUT_PATH, index=False)

    ground_truth = build_events_ground_truth(
        events,
        impacts,
        matched_rows,
        {
            "snapshot_tag": phase5_manifest["snapshot_tag"],
            "artifacts": baseline_hashes_before,
        },
        config["benchmark_version"],
    )
    EVENTS_OUTPUT_PATH.write_text(
        json.dumps(ground_truth, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    validate_csv_round_trip(scenario, config, opex_config)
    verify_phase5_baseline()
    baseline_hashes_after = {
        path: sha256(PROJECT_ROOT / path)
        for path in phase5_manifest["strict_artifacts"]
    }
    if baseline_hashes_before != baseline_hashes_after:
        raise ValueError("A Phase 5 authoritative artifact changed during Phase 6.")

    validations = [
        "phase5_authoritative_outputs_unchanged",
        "event_ids_unique_and_config_valid",
        "event_filters_match_nonzero_rows",
        "direct_event_scopes_do_not_overlap",
        "exact_event_operations",
        "expected_financial_directions",
        "baseline_reconstruction_matches_actual",
        "driver_grain_unique_and_bounds_valid",
        "gross_sales_reconciliation",
        "revenue_reconciliation",
        "cogs_reconciliation",
        "gross_profit_reconciliation",
        "opex_total_reconciliation",
        "ebitda_reconciliation",
        "derived_row_coverage",
        "deterministic_rerun",
        "row_order_independence",
        "csv_round_trip",
    ]
    write_report(config, impacts, scenario, validations, phase5_manifest)

    print("PHASE_6_STATUS=PASS")
    print(f"EVENTS={len(events)}")
    print(f"DRIVER_ROWS={len(scenario['drivers'])}")
    print(f"FINANCE_ROWS={len(scenario['finance'])}")
    for event_id, count in sorted(matched_rows.items()):
        print(f"{event_id}_MATCHED_ROWS={count}")
    print(f"REPORT={REPORT_PATH.relative_to(PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
