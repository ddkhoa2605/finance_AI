"""Phase 5: benchmark Units models and build a deterministic 2015 Forecast P&L."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from calculation.finance import (
    CANONICAL_COLUMNS,
    OPERATING_ACCOUNTS,
    reconstruct_operating_finance,
    validate_operating_finance,
)
from calculation.opex import (
    assert_noise_order_independent,
    generate_opex,
    validate_opex_artifacts,
)
from forecasting.driver_rules import apply_driver_rules
from forecasting.engines import (
    RidgeForecastEngine,
    SeasonalNaiveForecastEngine,
    XGBoostForecastEngine,
)
from forecasting.evaluation import evaluate_models, select_champion
from forecasting.registry import combined_hash, save_registry
from forecasting.scaffold import KEYS, create_forecast_scaffold, validate_budget_coverage


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
DRIVERS_PATH = PROCESSED_DIR / "drivers.csv"
ACTUAL_PATH = PROCESSED_DIR / "actual.csv"
ACTUAL_OPEX_PATH = PROCESSED_DIR / "opex.csv"
BUDGET_PATH = PROCESSED_DIR / "budget.csv"
FORECAST_DRIVERS_PATH = PROCESSED_DIR / "forecast_drivers.csv"
FORECAST_PATH = PROCESSED_DIR / "forecast.csv"
EVALUATION_PATH = PROCESSED_DIR / "forecast_model_evaluation.csv"
FINANCE_FACT_PATH = PROCESSED_DIR / "finance_fact.csv"
FORECAST_CONFIG_PATH = PROJECT_ROOT / "config" / "forecast.yaml"
OPEX_CONFIG_PATH = PROJECT_ROOT / "config" / "opex.yaml"
MODEL_DIR = PROJECT_ROOT / "models" / "forecast"
REPORT_PATH = PROJECT_ROOT / "reports" / "forecast_generation_report.md"

VERSION_ACTUAL = "ACTUAL"
VERSION_BUDGET = "BUDGET"
VERSION_FORECAST = "FORECAST"
FORECAST_SOURCE = "forecast_engine_v1"
FORECAST_OPEX_SOURCE = "synthetic_opex_v1_forecast"
FORECAST_EBITDA_SOURCE = "derived_forecast_v1"
TOLERANCE = 0.01

DRIVER_COLUMNS = [
    "period_date",
    "country",
    "product",
    "segment",
    "version",
    "units",
    "average_sale_price",
    "unit_cogs",
    "discount_rate",
    "average_manufacturing_price",
    "source",
]
FINANCE_FACT_GRAIN = [
    "period_date",
    "country",
    "product",
    "segment",
    "department",
    "account",
    "version",
    "currency",
    "source",
]


def load_yaml(path: Path, label: str) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    with path.open("r", encoding="utf-8") as file:
        result = yaml.safe_load(file)
    if not isinstance(result, dict):
        raise ValueError(f"{label} must contain a mapping.")
    return result


def load_csv(path: Path, required_columns: list[str], label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    result = pd.read_csv(path, parse_dates=["period_date"])
    missing = sorted(set(required_columns).difference(result.columns))
    if missing:
        raise ValueError(f"{label} is missing columns: {missing}")
    if result.empty:
        raise ValueError(f"{label} is empty.")
    return result


def load_inputs() -> dict:
    return {
        "drivers": load_csv(DRIVERS_PATH, DRIVER_COLUMNS, "drivers.csv"),
        "actual": load_csv(ACTUAL_PATH, [column for column in CANONICAL_COLUMNS if column != "department"], "actual.csv"),
        "actual_opex": load_csv(ACTUAL_OPEX_PATH, CANONICAL_COLUMNS, "opex.csv"),
        "budget": load_csv(BUDGET_PATH, CANONICAL_COLUMNS, "budget.csv"),
        "forecast_config": load_yaml(FORECAST_CONFIG_PATH, "forecast.yaml"),
        "opex_config": load_yaml(OPEX_CONFIG_PATH, "opex.yaml"),
    }


def validate_config(config: dict) -> None:
    if int(config.get("random_seed", -1)) != 42:
        raise ValueError("Forecast random_seed must be 42.")
    if int(config.get("horizon_months", 0)) != 12:
        raise ValueError("Phase 5 forecast horizon must be 12 months.")
    if config.get("champion", {}).get("metric") != "recursive_wape":
        raise ValueError("Champion metric must be recursive_wape.")
    tolerance = float(config["champion"]["simplicity_tolerance"])
    if tolerance < 0 or tolerance >= 1:
        raise ValueError("Champion simplicity_tolerance must be in [0, 1).")
    weights = config["driver_rules"]["trailing_weights"]
    if len(weights) != 3 or any(float(value) <= 0 for value in weights):
        raise ValueError("Driver rules require three positive trailing weights.")
    if float(config["driver_rules"]["pricing_factor"]) <= 0:
        raise ValueError("pricing_factor must be positive.")
    if float(config["driver_rules"]["cost_factor"]) <= 0:
        raise ValueError("cost_factor must be positive.")


def validate_actual_driver_lineage(drivers: pd.DataFrame, actual: pd.DataFrame) -> pd.DataFrame:
    actual_drivers = drivers.loc[drivers["version"] == VERSION_ACTUAL].copy()
    if len(actual_drivers) != len(drivers):
        raise ValueError("drivers.csv must be authoritative ACTUAL history only.")
    if actual_drivers[DRIVER_COLUMNS[:-1]].isna().drop(columns=["average_manufacturing_price"]).any().any():
        raise ValueError("Required Actual driver values contain nulls.")
    if (actual_drivers[["units", "average_sale_price", "unit_cogs"]] < 0).any().any():
        raise ValueError("Actual Units, ASP, and Unit COGS must be non-negative.")
    if not actual_drivers["discount_rate"].between(0, 1).all():
        raise ValueError("Actual Discount Rate must be within [0, 1].")

    grain = KEYS + ["version"]
    if actual_drivers.duplicated(grain).any():
        raise ValueError("Actual driver grain is not unique.")
    actual_cogs = (
        actual.loc[(actual["version"] == VERSION_ACTUAL) & (actual["account"] == "COGS")]
        .groupby(KEYS, as_index=False)["amount"].sum()
        .rename(columns={"amount": "actual_cogs"})
    )
    check = actual_drivers.merge(actual_cogs, on=KEYS, how="left", validate="one_to_one")
    if check["actual_cogs"].isna().any() or not np.allclose(
        check["units"] * check["unit_cogs"], check["actual_cogs"], atol=TOLERANCE
    ):
        raise ValueError("Canonical Unit COGS does not reconcile with actual.csv.")
    return actual_drivers.sort_values(KEYS).reset_index(drop=True)


def build_engine_factories(config: dict) -> dict:
    return {
        "seasonal_naive": SeasonalNaiveForecastEngine,
        "ridge": lambda: RidgeForecastEngine(alpha=config["models"]["ridge"]["alpha"]),
        "xgboost": lambda: XGBoostForecastEngine(config["models"]["xgboost"]),
    }


def forecast_units_month_batches(model, history: pd.DataFrame, scaffold: pd.DataFrame) -> pd.DataFrame:
    recursive_history = history[KEYS + ["units"]].copy()
    batches = []
    for month in sorted(scaffold["period_date"].unique()):
        month_scaffold = scaffold.loc[scaffold["period_date"] == month, KEYS].sort_values(KEYS).reset_index(drop=True)
        predictions = model.predict(month_scaffold, recursive_history)
        batch = month_scaffold.copy()
        batch["units"] = predictions.to_numpy()
        if batch["units"].isna().any() or not np.isfinite(batch["units"]).all():
            raise ValueError(f"Invalid Units prediction batch for {pd.Timestamp(month):%Y-%m}.")
        batches.append(batch)
        recursive_history = pd.concat([recursive_history, batch], ignore_index=True)
    return pd.concat(batches, ignore_index=True).sort_values(KEYS).reset_index(drop=True)


def build_forecast_drivers(
    actual_drivers: pd.DataFrame,
    scaffold: pd.DataFrame,
    units: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rules, fallback_usage = apply_driver_rules(
        actual_drivers,
        scaffold,
        config["driver_rules"],
    )
    result = units.merge(rules, on=KEYS, how="inner", validate="one_to_one")
    if len(result) != len(scaffold):
        raise ValueError("Forecast driver rules changed scaffold coverage.")
    result["version"] = VERSION_FORECAST
    result["average_manufacturing_price"] = pd.NA
    result["source"] = FORECAST_SOURCE
    return result[DRIVER_COLUMNS].sort_values(KEYS).reset_index(drop=True), fallback_usage


def build_authoritative_actual(actual: pd.DataFrame, actual_opex: pd.DataFrame) -> pd.DataFrame:
    actual_base = actual.copy()
    actual_base["department"] = pd.NA
    actual_base = actual_base[CANONICAL_COLUMNS]
    result = pd.concat([actual_base, actual_opex[CANONICAL_COLUMNS]], ignore_index=True)
    if not (result["version"] == VERSION_ACTUAL).all():
        raise ValueError("Authoritative Actual inputs contain a non-ACTUAL version.")
    return result


def build_finance_fact(
    actual: pd.DataFrame,
    actual_opex: pd.DataFrame,
    budget: pd.DataFrame,
    forecast: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    authoritative_actual = build_authoritative_actual(actual, actual_opex)
    if not (budget["version"] == VERSION_BUDGET).all():
        raise ValueError("budget.csv contains a non-BUDGET version.")
    result = pd.concat([authoritative_actual, budget, forecast], ignore_index=True)
    result = result.sort_values(
        ["version", "period_date", "country", "product", "segment", "department", "account"],
        na_position="last",
    ).reset_index(drop=True)
    return result, authoritative_actual


def build_artifacts(inputs: dict) -> dict:
    config = inputs["forecast_config"]
    validate_config(config)
    actual_drivers = validate_actual_driver_lineage(inputs["drivers"], inputs["actual"])
    cutoff = pd.Timestamp(config["training_end"])
    forecast_year = int(config["forecast_year"])
    base_year = forecast_year - 1
    if actual_drivers["period_date"].max() != cutoff:
        raise ValueError("Forecast training_end must equal the latest Actual driver month.")

    scaffold = create_forecast_scaffold(actual_drivers, base_year, forecast_year)
    if scaffold["period_date"].nunique() != int(config["horizon_months"]):
        raise ValueError("Forecast scaffold does not cover the configured horizon.")
    validate_budget_coverage(scaffold, inputs["budget"])

    factories = build_engine_factories(config)
    validation_months = [pd.Timestamp(value) for value in config["validation_months"]]
    evaluation, prediction_sets = evaluate_models(factories, actual_drivers, validation_months)
    champion, decisions = select_champion(
        evaluation, float(config["champion"]["simplicity_tolerance"])
    )

    final_models = {
        name: factory().fit(actual_drivers, cutoff)
        for name, factory in factories.items()
    }
    forecast_units = forecast_units_month_batches(
        final_models[champion],
        actual_drivers.loc[actual_drivers["period_date"] <= cutoff],
        scaffold,
    )
    forecast_drivers, fallback_usage = build_forecast_drivers(
        actual_drivers, scaffold, forecast_units, config
    )
    operating = reconstruct_operating_finance(
        forecast_drivers,
        version=VERSION_FORECAST,
        source=FORECAST_SOURCE,
    )
    opex = generate_opex(
        operating,
        inputs["opex_config"],
        version=VERSION_FORECAST,
        source_name=FORECAST_OPEX_SOURCE,
        ebitda_source=FORECAST_EBITDA_SOURCE,
    )
    forecast = pd.concat([operating, opex["output"]], ignore_index=True).sort_values(
        ["period_date", "country", "product", "segment", "department", "account"],
        na_position="last",
    ).reset_index(drop=True)
    finance_fact, authoritative_actual = build_finance_fact(
        inputs["actual"], inputs["actual_opex"], inputs["budget"], forecast
    )
    return {
        "actual_drivers": actual_drivers,
        "scaffold": scaffold,
        "evaluation": evaluation,
        "prediction_sets": prediction_sets,
        "champion": champion,
        "decisions": decisions,
        "final_models": final_models,
        "forecast_units": forecast_units,
        "forecast_drivers": forecast_drivers,
        "fallback_usage": fallback_usage,
        "operating": operating,
        "opex": opex,
        "forecast": forecast,
        "finance_fact": finance_fact,
        "authoritative_actual": authoritative_actual,
    }


def assert_unique(df: pd.DataFrame, columns: list[str], label: str) -> None:
    count = int(df.duplicated(columns).sum())
    if count:
        raise ValueError(f"{label} has {count} duplicate canonical rows.")


def validate_artifacts(artifacts: dict, inputs: dict) -> dict:
    config = inputs["forecast_config"]
    drivers = artifacts["forecast_drivers"]
    scaffold = artifacts["scaffold"]
    operating = artifacts["operating"]
    opex = artifacts["opex"]
    forecast = artifacts["forecast"]
    finance_fact = artifacts["finance_fact"]

    if len(drivers) != len(scaffold):
        raise ValueError("Forecast driver row count does not equal scaffold length.")
    assert_unique(drivers, KEYS + ["version"], "forecast_drivers.csv")
    if drivers[["units", "average_sale_price", "unit_cogs", "discount_rate"]].isna().any().any():
        raise ValueError("Forecast required drivers contain nulls.")
    if (drivers[["units", "average_sale_price", "unit_cogs"]] < 0).any().any():
        raise ValueError("Forecast Units, ASP, and Unit COGS must be non-negative.")
    if not drivers["discount_rate"].between(0, 1).all():
        raise ValueError("Forecast Discount Rate must be within [0, 1].")

    validate_operating_finance(operating, TOLERANCE)
    validate_opex_artifacts(opex, inputs["opex_config"], TOLERANCE)
    expected_operating = len(scaffold) * len(OPERATING_ACCOUNTS)
    country_month_count = len(scaffold[["period_date", "country"]].drop_duplicates())
    department_count = len(inputs["opex_config"]["departments"])
    expected_opex = country_month_count * department_count + country_month_count * 2
    if len(operating) != expected_operating or len(opex["output"]) != expected_opex:
        raise ValueError("Forecast finance output row coverage is incomplete.")
    if len(forecast) != expected_operating + expected_opex:
        raise ValueError("forecast.csv row coverage is incomplete.")
    assert_unique(forecast, FINANCE_FACT_GRAIN, "forecast.csv")
    assert_unique(finance_fact, FINANCE_FACT_GRAIN, "finance_fact.csv")

    actual_slice = finance_fact.loc[finance_fact["version"] == VERSION_ACTUAL]
    budget_slice = finance_fact.loc[finance_fact["version"] == VERSION_BUDGET]
    actual_sort = ["period_date", "country", "product", "segment", "department", "account", "source"]
    pd.testing.assert_frame_equal(
        actual_slice.sort_values(actual_sort, na_position="last").reset_index(drop=True),
        artifacts["authoritative_actual"].sort_values(actual_sort, na_position="last").reset_index(drop=True),
        check_exact=True,
        check_dtype=False,
    )
    pd.testing.assert_frame_equal(
        budget_slice.sort_values(actual_sort, na_position="last").reset_index(drop=True),
        inputs["budget"].sort_values(actual_sort, na_position="last").reset_index(drop=True),
        check_exact=True,
        check_dtype=False,
    )

    compare_keys = KEYS + ["account"]
    forecast_operating = operating[compare_keys + ["amount"]].rename(columns={"amount": "forecast"})
    budget_operating = inputs["budget"].loc[
        inputs["budget"]["account"].isin(OPERATING_ACCOUNTS), compare_keys + ["amount"]
    ].rename(columns={"amount": "budget"})
    comparison = forecast_operating.merge(
        budget_operating, on=compare_keys, how="inner", validate="one_to_one"
    )
    if len(comparison) != len(forecast_operating) or np.allclose(
        comparison["forecast"], comparison["budget"], atol=TOLERANCE
    ):
        raise ValueError("Forecast must be fully comparable with and distinct from Budget.")

    assert_noise_order_independent(
        operating,
        inputs["opex_config"],
        version=VERSION_FORECAST,
        source_name=FORECAST_OPEX_SOURCE,
        ebitda_source=FORECAST_EBITDA_SOURCE,
    )
    return {
        "forecast_horizon_12_months": True,
        "actual_derived_scaffold": True,
        "budget_coverage_only": True,
        "one_step_and_recursive_backtests": True,
        "candidate_prediction_coverage_100_percent": True,
        "leakage_safe_preprocessing": True,
        "simplicity_aware_champion": True,
        "canonical_driver_grain_unique": True,
        "driver_bounds": True,
        "operating_reconciliation": True,
        "fixed_allocation_reconciliation": True,
        "opex_and_ebitda_reconciliation": True,
        "derived_row_coverage": True,
        "actual_and_budget_preserved": True,
        "forecast_distinct_from_budget": True,
        "keyed_opex_noise_order_independent": True,
    }


def validate_determinism(first: dict, inputs: dict) -> None:
    second = build_artifacts(inputs)
    for name in ["forecast_drivers", "forecast", "evaluation", "finance_fact"]:
        pd.testing.assert_frame_equal(first[name], second[name], check_exact=True)
    if first["champion"] != second["champion"] or first["decisions"] != second["decisions"]:
        raise ValueError("Champion selection is not deterministic.")

    shuffled_inputs = dict(inputs)
    shuffled_inputs["drivers"] = inputs["drivers"].sample(frac=1, random_state=42).reset_index(drop=True)
    shuffled = build_artifacts(shuffled_inputs)
    for name in ["forecast_drivers", "forecast", "evaluation"]:
        pd.testing.assert_frame_equal(first[name], shuffled[name], check_exact=True)
    if first["champion"] != shuffled["champion"]:
        raise ValueError("Input row order changed the Forecast champion.")


def write_outputs(artifacts: dict) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    artifacts["forecast_drivers"].to_csv(FORECAST_DRIVERS_PATH, index=False, date_format="%Y-%m-%d")
    artifacts["forecast"].to_csv(FORECAST_PATH, index=False, date_format="%Y-%m-%d")
    artifacts["evaluation"].to_csv(EVALUATION_PATH, index=False)
    artifacts["finance_fact"].to_csv(FINANCE_FACT_PATH, index=False, date_format="%Y-%m-%d")


def validate_csv_round_trip(artifacts: dict) -> None:
    drivers = pd.read_csv(FORECAST_DRIVERS_PATH, parse_dates=["period_date"])
    forecast = pd.read_csv(FORECAST_PATH, parse_dates=["period_date"])
    evaluation = pd.read_csv(EVALUATION_PATH)
    finance_fact = pd.read_csv(FINANCE_FACT_PATH, parse_dates=["period_date"])
    if list(drivers.columns) != DRIVER_COLUMNS or len(drivers) != len(artifacts["forecast_drivers"]):
        raise ValueError("forecast_drivers.csv failed schema or row-count round-trip.")
    if list(forecast.columns) != CANONICAL_COLUMNS or len(forecast) != len(artifacts["forecast"]):
        raise ValueError("forecast.csv failed schema or row-count round-trip.")
    if len(evaluation) != len(artifacts["evaluation"]):
        raise ValueError("forecast_model_evaluation.csv failed row-count round-trip.")
    assert_unique(finance_fact, FINANCE_FACT_GRAIN, "finance_fact.csv round-trip")
    validate_operating_finance(forecast.loc[forecast["account"].isin(OPERATING_ACCOUNTS)], TOLERANCE)


def build_comparison(forecast: pd.DataFrame, budget: pd.DataFrame) -> pd.DataFrame:
    accounts = ["REVENUE", "GROSS_PROFIT", "OPEX_TOTAL", "EBITDA"]
    forecast_totals = forecast.loc[forecast["account"].isin(accounts)].groupby("account")["amount"].sum()
    budget_totals = budget.loc[budget["account"].isin(accounts)].groupby("account")["amount"].sum()
    result = pd.DataFrame(
        {
            "account": accounts,
            "forecast_2015": [forecast_totals[account] for account in accounts],
            "budget_2015": [budget_totals[account] for account in accounts],
        }
    )
    result["variance"] = result["forecast_2015"] - result["budget_2015"]
    result["variance_pct"] = np.where(
        result["budget_2015"] != 0,
        result["variance"] / result["budget_2015"].abs(),
        np.nan,
    )
    return result


def generate_report(
    artifacts: dict,
    validation: dict,
    comparison: pd.DataFrame,
    registry: dict,
) -> str:
    recursive = artifacts["evaluation"].loc[
        (artifacts["evaluation"]["evaluation_type"] == "recursive")
        & (artifacts["evaluation"]["fold"] == "ALL")
        & (artifacts["evaluation"]["scope"] == "overall")
    ]
    one_step = artifacts["evaluation"].loc[
        (artifacts["evaluation"]["evaluation_type"] == "one_step")
        & (artifacts["evaluation"]["fold"] == "ALL")
        & (artifacts["evaluation"]["scope"] == "overall")
    ]
    country_bias = artifacts["evaluation"].loc[
        (artifacts["evaluation"]["evaluation_type"] == "recursive")
        & (artifacts["evaluation"]["fold"] == "ALL")
        & (artifacts["evaluation"]["scope"] == "country")
    ]
    columns = ["model", "mae", "rmse", "wape", "smape", "macro_wape", "median_series_wape", "prediction_coverage"]
    lines = [
        "# Forecast Generation Report",
        "",
        "## Pipeline Result",
        "",
        "- Status: passed",
        "- Forecast horizon: January–December 2015",
        "- Training history: September 2013–December 2014",
        "- ML target: Units only",
        f"- Champion: {artifacts['champion']}",
        f"- Simplicity tolerance: {registry['simplicity_tolerance']:.3%} WAPE points",
        f"- Forecast driver rows: {len(artifacts['forecast_drivers']):,}",
        f"- Forecast finance rows: {len(artifacts['forecast']):,}",
        f"- Combined finance fact rows: {len(artifacts['finance_fact']):,}",
        "",
        "## Dataset Limitation",
        "",
        "The Microsoft Financial Sample contains only 16 months of sparse series history. ML results are a proof of concept, not a production-grade 12-month accuracy claim. Missing observations are not treated as zero sales.",
        "",
        "## One-step Walk-forward Evaluation",
        "",
        one_step[columns].to_markdown(index=False, floatfmt=".6f"),
        "",
        "## Recursive Stability Evaluation",
        "",
        recursive[columns].to_markdown(index=False, floatfmt=".6f"),
        "",
        "## Recursive WAPE by Country",
        "",
        country_bias[["model", "country", "wape", "prediction_coverage"]].to_markdown(
            index=False, floatfmt=".6f"
        ),
        "",
        "Champion selection uses recursive pooled WAPE. A more complex model must improve WAPE by at least the configured simplicity tolerance.",
        "",
        "## Champion Decisions",
        "",
        pd.DataFrame(artifacts["decisions"]).to_markdown(index=False, floatfmt=".6f"),
        "",
        "## Driver Rule Fallback Usage",
        "",
        artifacts["fallback_usage"].to_markdown(index=False),
        "",
        "ASP, Unit COGS, and Discount Rate use same-grain/same-month prior year first, followed by deterministic historical fallbacks. Unit COGS is distinct from Average Manufacturing Price.",
        "",
        "## Forecast vs Budget",
        "",
        comparison.to_markdown(index=False, floatfmt=".4f"),
        "",
        "Budget is comparison context only. It is not a model feature, target, or champion-selection input.",
        "",
        "## Validation Checks",
        "",
    ]
    lines.extend(f"- {name}: {'passed' if passed else 'failed'}" for name, passed in validation.items())
    lines.extend(
        [
            "- deterministic_rerun: passed",
            "- shuffled_input_order: passed",
            "- csv_round_trip: passed",
            "",
            "## Lineage",
            "",
            f"- Prediction input hash: `{registry['prediction_input_hash']}`",
            f"- Evaluation context hash: `{registry['evaluation_context_hash']}`",
            "- Operating Forecast source: `forecast_engine_v1`",
            "- Forecast OPEX source: `synthetic_opex_v1_forecast`",
            "- Forecast EBITDA source: `derived_forecast_v1`",
            "",
            "## Output Files",
            "",
            f"- `{FORECAST_DRIVERS_PATH.name}`: {len(artifacts['forecast_drivers']):,} rows",
            f"- `{FORECAST_PATH.name}`: {len(artifacts['forecast']):,} rows",
            f"- `{EVALUATION_PATH.name}`: {len(artifacts['evaluation']):,} rows",
            f"- `{FINANCE_FACT_PATH.name}`: {len(artifacts['finance_fact']):,} rows",
            "- `models/forecast/model_registry.json`: final-refit model registry",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    inputs = load_inputs()
    artifacts = build_artifacts(inputs)
    validation = validate_artifacts(artifacts, inputs)
    validate_determinism(artifacts, inputs)
    write_outputs(artifacts)
    validate_csv_round_trip(artifacts)

    prediction_hash = combined_hash(
        [DRIVERS_PATH, ACTUAL_PATH, FORECAST_CONFIG_PATH, OPEX_CONFIG_PATH]
    )
    evaluation_hash = combined_hash([BUDGET_PATH])
    registry = save_registry(
        MODEL_DIR,
        artifacts["final_models"],
        artifacts["champion"],
        artifacts["evaluation"],
        artifacts["decisions"],
        inputs["forecast_config"],
        prediction_hash,
        evaluation_hash,
    )
    comparison = build_comparison(artifacts["forecast"], inputs["budget"])
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        generate_report(artifacts, validation, comparison, registry), encoding="utf-8"
    )

    print("Forecast pipeline completed successfully.")
    print(f"- Champion: {artifacts['champion']}")
    print(f"- Forecast drivers: {len(artifacts['forecast_drivers']):,} -> {FORECAST_DRIVERS_PATH}")
    print(f"- Forecast finance: {len(artifacts['forecast']):,} -> {FORECAST_PATH}")
    print(f"- Combined finance fact: {len(artifacts['finance_fact']):,} -> {FINANCE_FACT_PATH}")
    print(f"- Report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
