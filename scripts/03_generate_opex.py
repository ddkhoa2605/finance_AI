from pathlib import Path

import numpy as np
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACTUAL_PATH = PROJECT_ROOT / "data" / "processed" / "actual.csv"
OPEX_PATH = PROJECT_ROOT / "data" / "processed" / "opex.csv"
FINANCE_FACT_PATH = PROJECT_ROOT / "data" / "processed" / "finance_fact.csv"
CONFIG_PATH = PROJECT_ROOT / "config" / "opex.yaml"
REPORT_PATH = PROJECT_ROOT / "reports" / "opex_generation_report.md"

VERSION_ACTUAL = "ACTUAL"
PROJECT_CURRENCY = "USD"
OPEX_SOURCE = "synthetic_opex_v1"
EBITDA_SOURCE = "derived_from_actual_and_synthetic_opex"
TOLERANCE = 0.01
REQUIRED_RANDOM_SEED = 42

ACTUAL_REQUIRED_COLUMNS = [
    "period_date",
    "country",
    "product",
    "segment",
    "account",
    "version",
    "currency",
    "source",
    "amount",
]
CANONICAL_COLUMNS = [
    "period_date",
    "country",
    "product",
    "segment",
    "department",
    "account",
    "version",
    "currency",
    "source",
    "amount",
]
DEPARTMENT_GRAIN = ["period_date", "country", "department", "version"]
COUNTRY_ACCOUNT_GRAIN = ["period_date", "country", "account", "version"]
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


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Config file not found: {CONFIG_PATH}")

    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict) or not config.get("departments"):
        raise ValueError("OPEX config must define at least one department.")
    if config.get("random_seed") != REQUIRED_RANDOM_SEED:
        raise ValueError(
            f"OPEX config random_seed must be {REQUIRED_RANDOM_SEED}."
        )

    expected_months = set(range(1, 13))
    seasonality = config.get("seasonality")
    if not isinstance(seasonality, dict) or set(seasonality) != expected_months:
        raise ValueError("OPEX config must define seasonality for months 1 through 12.")
    if any(factor <= 0 for factor in seasonality.values()):
        raise ValueError("Seasonality factors must be positive.")

    country_coefficients = config.get("country_coefficients")
    if not isinstance(country_coefficients, dict) or not country_coefficients:
        raise ValueError("OPEX config must define country_coefficients.")
    if any(factor <= 0 for factor in country_coefficients.values()):
        raise ValueError("Country coefficients must be positive.")

    noise_config = config.get("controlled_noise")
    required_noise_keys = {"loc", "scale", "minimum", "maximum"}
    if not isinstance(noise_config, dict) or not required_noise_keys.issubset(noise_config):
        raise ValueError("OPEX config must define controlled_noise settings.")
    if noise_config["scale"] < 0 or noise_config["minimum"] > noise_config["maximum"]:
        raise ValueError("Controlled noise bounds or scale are invalid.")
    if noise_config["minimum"] <= -1:
        raise ValueError("Controlled noise minimum must keep noise_factor positive.")

    required_keys = {"display_name", "account", "fixed_monthly", "revenue_ratio"}
    for department_key, department_config in config["departments"].items():
        missing = required_keys.difference(department_config)
        if missing:
            raise ValueError(
                f"Department {department_key} is missing config keys: {sorted(missing)}"
            )
        if department_config["fixed_monthly"] < 0:
            raise ValueError(f"Department {department_key} has negative fixed_monthly.")
        if department_config["revenue_ratio"] < 0:
            raise ValueError(f"Department {department_key} has negative revenue_ratio.")
    return config


def load_actual() -> pd.DataFrame:
    if not ACTUAL_PATH.exists():
        raise FileNotFoundError(f"Actual data file not found: {ACTUAL_PATH}")

    actual_df = pd.read_csv(ACTUAL_PATH, parse_dates=["period_date"])
    missing = [
        column for column in ACTUAL_REQUIRED_COLUMNS if column not in actual_df.columns
    ]
    if missing:
        raise ValueError(f"actual.csv is missing required columns: {missing}")
    if actual_df.empty:
        raise ValueError("actual.csv is empty.")
    return actual_df


def get_country_month_revenue(actual_df: pd.DataFrame) -> pd.DataFrame:
    revenue_df = actual_df.loc[
        (actual_df["account"] == "REVENUE")
        & (actual_df["version"] == VERSION_ACTUAL)
    ].copy()
    if revenue_df.empty:
        raise ValueError("actual.csv contains no ACTUAL REVENUE rows.")

    return (
        revenue_df.groupby(["period_date", "country"], as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "revenue"})
        .sort_values(["period_date", "country"])
        .reset_index(drop=True)
    )


def add_revenue_share(revenue_df: pd.DataFrame) -> pd.DataFrame:
    result = revenue_df.copy()
    monthly_total = result.groupby("period_date")["revenue"].transform("sum")
    if (monthly_total <= 0).any():
        raise ValueError("Cannot allocate fixed OPEX for a month with non-positive revenue.")
    result["revenue_share"] = result["revenue"] / monthly_total
    return result


def generate_department_opex(
    revenue_df: pd.DataFrame,
    department_key: str,
    department_config: dict,
    config: dict,
    rng: np.random.Generator,
) -> pd.DataFrame:
    result = revenue_df.copy()
    result["fixed_component"] = (
        float(department_config["fixed_monthly"]) * result["revenue_share"]
    )
    result["variable_component"] = (
        result["revenue"] * float(department_config["revenue_ratio"])
    )
    result["base_amount"] = result["fixed_component"] + result["variable_component"]
    result["seasonality_factor"] = result["period_date"].dt.month.map(
        config["seasonality"]
    )
    result["country_factor"] = result["country"].map(
        config["country_coefficients"]
    )
    if result[["seasonality_factor", "country_factor"]].isna().any().any():
        raise ValueError("Missing seasonality or country coefficient for OPEX row.")

    noise_config = config["controlled_noise"]
    result["noise"] = np.clip(
        rng.normal(
            loc=noise_config["loc"],
            scale=noise_config["scale"],
            size=len(result),
        ),
        noise_config["minimum"],
        noise_config["maximum"],
    )
    result["noise_factor"] = 1 + result["noise"]
    result["amount"] = (
        result["base_amount"]
        * result["seasonality_factor"]
        * result["country_factor"]
        * result["noise_factor"]
    )
    result["department_key"] = department_key
    result["department"] = department_config["display_name"]
    result["account"] = department_config["account"]
    return result


def generate_all_opex(revenue_df: pd.DataFrame, config: dict) -> pd.DataFrame:
    rng = np.random.default_rng(config["random_seed"])
    frames = [
        generate_department_opex(
            revenue_df,
            department_key,
            department_config,
            config,
            rng,
        )
        for department_key, department_config in config["departments"].items()
    ]
    return (
        pd.concat(frames, ignore_index=True)
        .sort_values(["period_date", "country", "department", "account"])
        .reset_index(drop=True)
    )


def to_canonical_department_opex(department_opex: pd.DataFrame) -> pd.DataFrame:
    result = department_opex.copy()
    result["product"] = pd.NA
    result["segment"] = pd.NA
    result["version"] = VERSION_ACTUAL
    result["currency"] = PROJECT_CURRENCY
    result["source"] = OPEX_SOURCE
    return result[CANONICAL_COLUMNS].copy()


def build_opex_total(department_opex: pd.DataFrame) -> pd.DataFrame:
    result = (
        department_opex.groupby(["period_date", "country"], as_index=False)["amount"]
        .sum()
        .sort_values(["period_date", "country"])
        .reset_index(drop=True)
    )
    result["product"] = pd.NA
    result["segment"] = pd.NA
    result["department"] = pd.NA
    result["account"] = "OPEX_TOTAL"
    result["version"] = VERSION_ACTUAL
    result["currency"] = PROJECT_CURRENCY
    result["source"] = OPEX_SOURCE
    return result[CANONICAL_COLUMNS].copy()


def get_country_month_gross_profit(actual_df: pd.DataFrame) -> pd.DataFrame:
    gross_profit_df = actual_df.loc[
        (actual_df["account"] == "GROSS_PROFIT")
        & (actual_df["version"] == VERSION_ACTUAL)
    ].copy()
    if gross_profit_df.empty:
        raise ValueError("actual.csv contains no ACTUAL GROSS_PROFIT rows.")

    return (
        gross_profit_df.groupby(["period_date", "country"], as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "gross_profit"})
        .sort_values(["period_date", "country"])
        .reset_index(drop=True)
    )


def build_ebitda(
    gross_profit_df: pd.DataFrame, opex_total: pd.DataFrame
) -> pd.DataFrame:
    opex_df = opex_total[["period_date", "country", "amount"]].rename(
        columns={"amount": "opex_total"}
    )
    result = gross_profit_df.merge(
        opex_df,
        on=["period_date", "country"],
        how="inner",
        validate="one_to_one",
    )
    if len(result) != len(gross_profit_df) or len(result) != len(opex_total):
        raise ValueError("Gross-profit and OPEX coverage must match for EBITDA.")

    result["amount"] = result["gross_profit"] - result["opex_total"]
    result["product"] = pd.NA
    result["segment"] = pd.NA
    result["department"] = pd.NA
    result["account"] = "EBITDA"
    result["version"] = VERSION_ACTUAL
    result["currency"] = PROJECT_CURRENCY
    result["source"] = EBITDA_SOURCE
    return result[CANONICAL_COLUMNS].copy()


def build_opex_output(
    department_opex: pd.DataFrame,
    opex_total: pd.DataFrame,
    ebitda: pd.DataFrame,
) -> pd.DataFrame:
    return (
        pd.concat([department_opex, opex_total, ebitda], ignore_index=True)
        .sort_values(
            ["period_date", "country", "account", "department"],
            na_position="last",
        )
        .reset_index(drop=True)
    )


def build_finance_fact(actual_df: pd.DataFrame, opex_output: pd.DataFrame) -> pd.DataFrame:
    actual_for_finance = actual_df.copy()
    actual_for_finance["department"] = pd.NA
    actual_for_finance = actual_for_finance[CANONICAL_COLUMNS]

    return (
        pd.concat([actual_for_finance, opex_output], ignore_index=True)
        .sort_values(
            ["period_date", "country", "product", "segment", "department", "account"],
            na_position="last",
        )
        .reset_index(drop=True)
    )


def assert_unique(df: pd.DataFrame, columns: list[str], label: str) -> None:
    duplicate_count = int(df.duplicated(subset=columns).sum())
    if duplicate_count:
        raise ValueError(f"{label} has {duplicate_count} duplicate rows at {columns}.")


def validate_department_opex_non_negative(department_opex: pd.DataFrame) -> None:
    if not (department_opex["amount"] >= 0).all():
        raise ValueError("Department OPEX cannot be negative.")


def validate_fixed_allocation(
    department_opex: pd.DataFrame, config: dict
) -> pd.DataFrame:
    fixed_check = (
        department_opex.groupby(["period_date", "department_key"], as_index=False)[
            "fixed_component"
        ]
        .sum()
        .sort_values(["period_date", "department_key"])
        .reset_index(drop=True)
    )
    fixed_check["expected_fixed_monthly"] = fixed_check["department_key"].map(
        {
            department_key: float(department_config["fixed_monthly"])
            for department_key, department_config in config["departments"].items()
        }
    )
    fixed_check["difference"] = (
        fixed_check["fixed_component"] - fixed_check["expected_fixed_monthly"]
    )
    if not np.allclose(fixed_check["difference"], 0, atol=TOLERANCE):
        raise ValueError("Fixed OPEX allocation does not reconcile to monthly config.")
    return fixed_check


def validate_synthetic_adjustments(
    department_opex: pd.DataFrame, config: dict
) -> None:
    """Validate the applied seasonality, country, and bounded-noise formula."""
    noise_config = config["controlled_noise"]
    if not department_opex["noise"].between(
        noise_config["minimum"], noise_config["maximum"]
    ).all():
        raise ValueError("Controlled OPEX noise exceeded its configured bounds.")
    if (department_opex["noise_factor"] <= 0).any():
        raise ValueError("Controlled OPEX noise produced a non-positive factor.")

    expected_amount = (
        department_opex["base_amount"]
        * department_opex["seasonality_factor"]
        * department_opex["country_factor"]
        * department_opex["noise_factor"]
    )
    if not np.allclose(department_opex["amount"], expected_amount, atol=TOLERANCE):
        raise ValueError("Adjusted OPEX does not match its configured factor formula.")


def validate_opex_total(
    department_opex: pd.DataFrame, opex_total: pd.DataFrame
) -> None:
    department_total = (
        department_opex.groupby(["period_date", "country"], as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "department_amount"})
    )
    total_check = department_total.merge(
        opex_total[["period_date", "country", "amount"]].rename(
            columns={"amount": "opex_total_amount"}
        ),
        on=["period_date", "country"],
        how="outer",
        validate="one_to_one",
    )
    if total_check.isna().any().any() or not np.allclose(
        total_check["department_amount"], total_check["opex_total_amount"], atol=TOLERANCE
    ):
        raise ValueError("OPEX Total does not reconcile to department OPEX.")


def validate_ebitda(
    gross_profit_df: pd.DataFrame, opex_total: pd.DataFrame, ebitda: pd.DataFrame
) -> None:
    check = gross_profit_df.merge(
        opex_total[["period_date", "country", "amount"]].rename(
            columns={"amount": "opex_total"}
        ),
        on=["period_date", "country"],
        how="inner",
        validate="one_to_one",
    ).merge(
        ebitda[["period_date", "country", "amount"]].rename(
            columns={"amount": "ebitda"}
        ),
        on=["period_date", "country"],
        how="inner",
        validate="one_to_one",
    )
    if len(check) != len(gross_profit_df) or not np.allclose(
        check["gross_profit"] - check["opex_total"], check["ebitda"], atol=TOLERANCE
    ):
        raise ValueError("EBITDA does not reconcile to gross profit minus OPEX Total.")


def validate_grain_uniqueness(
    department_opex: pd.DataFrame, opex_total: pd.DataFrame, ebitda: pd.DataFrame
) -> None:
    assert_unique(department_opex, DEPARTMENT_GRAIN, "Department OPEX")
    assert_unique(opex_total, COUNTRY_ACCOUNT_GRAIN, "OPEX Total")
    assert_unique(ebitda, COUNTRY_ACCOUNT_GRAIN, "EBITDA")


def validate_row_coverage(artifacts: dict, config: dict) -> None:
    """Ensure every country-month receives one row for each OPEX output type."""
    country_month_rows = len(artifacts["revenue"])
    department_count = len(config["departments"])
    expected_department_rows = country_month_rows * department_count

    if len(artifacts["department_opex"]) != expected_department_rows:
        raise ValueError(
            "Department OPEX row coverage failed: "
            f"expected {expected_department_rows}, "
            f"received {len(artifacts['department_opex'])}."
        )

    rows_per_department = artifacts["department_opex_detail"].groupby(
        "department_key"
    ).size()
    if not (rows_per_department == country_month_rows).all():
        raise ValueError("A department is missing one or more country-month rows.")
    if len(artifacts["opex_total"]) != country_month_rows:
        raise ValueError("OPEX Total is missing one or more country-month rows.")
    if len(artifacts["ebitda"]) != country_month_rows:
        raise ValueError("EBITDA is missing one or more country-month rows.")


def build_artifacts(actual_df: pd.DataFrame, config: dict) -> dict:
    revenue_df = add_revenue_share(get_country_month_revenue(actual_df))
    department_opex_detail = generate_all_opex(revenue_df, config)
    department_opex = to_canonical_department_opex(department_opex_detail)
    opex_total = build_opex_total(department_opex_detail)
    gross_profit_df = get_country_month_gross_profit(actual_df)
    ebitda = build_ebitda(gross_profit_df, opex_total)
    opex_output = build_opex_output(department_opex, opex_total, ebitda)
    finance_fact = build_finance_fact(actual_df, opex_output)
    return {
        "department_opex_detail": department_opex_detail,
        "revenue": revenue_df,
        "department_opex": department_opex,
        "opex_total": opex_total,
        "gross_profit": gross_profit_df,
        "ebitda": ebitda,
        "opex_output": opex_output,
        "finance_fact": finance_fact,
    }


def validate_artifacts(artifacts: dict, config: dict) -> tuple[dict, pd.DataFrame]:
    validate_department_opex_non_negative(artifacts["department_opex"])
    fixed_check = validate_fixed_allocation(
        artifacts["department_opex_detail"], config
    )
    validate_synthetic_adjustments(artifacts["department_opex_detail"], config)
    validate_opex_total(artifacts["department_opex"], artifacts["opex_total"])
    validate_ebitda(
        artifacts["gross_profit"], artifacts["opex_total"], artifacts["ebitda"]
    )
    validate_grain_uniqueness(
        artifacts["department_opex"], artifacts["opex_total"], artifacts["ebitda"]
    )
    validate_row_coverage(artifacts, config)
    assert_unique(artifacts["finance_fact"], FINANCE_FACT_GRAIN, "finance_fact.csv")

    return (
        {
            "department_opex_non_negative": True,
            "random_seed_42_configured": True,
            "fixed_allocation_reconciliation": True,
            "seasonality_country_noise_formula": True,
            "controlled_noise_bounds": True,
            "opex_total_reconciliation": True,
            "ebitda_reconciliation": True,
            "opex_grain_uniqueness": True,
            "no_accidental_row_loss": True,
            "finance_fact_grain_uniqueness": True,
        },
        fixed_check,
    )


def validate_determinism(actual_df: pd.DataFrame, config: dict, first: dict) -> None:
    second = build_artifacts(actual_df, config)
    for name in ["opex_output", "finance_fact"]:
        pd.testing.assert_frame_equal(first[name], second[name], check_exact=True)


def write_outputs(opex_output: pd.DataFrame, finance_fact: pd.DataFrame) -> None:
    OPEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    opex_output.to_csv(OPEX_PATH, index=False, date_format="%Y-%m-%d")
    finance_fact.to_csv(FINANCE_FACT_PATH, index=False, date_format="%Y-%m-%d")


def validate_csv_round_trip() -> None:
    opex_df = pd.read_csv(OPEX_PATH, parse_dates=["period_date"])
    finance_fact_df = pd.read_csv(FINANCE_FACT_PATH, parse_dates=["period_date"])
    if list(opex_df.columns) != CANONICAL_COLUMNS:
        raise ValueError("opex.csv schema does not match the canonical contract.")
    if list(finance_fact_df.columns) != CANONICAL_COLUMNS:
        raise ValueError("finance_fact.csv schema does not match the canonical contract.")
    assert_unique(finance_fact_df, FINANCE_FACT_GRAIN, "finance_fact.csv")


def generate_report(
    artifacts: dict, validation: dict, fixed_check: pd.DataFrame, config: dict
) -> str:
    lines = ["# OPEX Generation Report", "", "## Pipeline Result", ""]
    lines.extend(
        [
            "- Status: passed",
            f"- Random seed: {REQUIRED_RANDOM_SEED}",
            f"- OPEX rows: {len(artifacts['opex_output']):,}",
            f"- Finance fact rows: {len(artifacts['finance_fact']):,}",
            "",
            "## Validation Checks",
            "",
        ]
    )
    for name, passed in validation.items():
        lines.append(f"- {name}: {'passed' if passed else 'failed'}")

    lines.extend(
        [
            "- deterministic_rebuild: passed",
            "- csv_round_trip: passed",
            "",
            "## Synthetic Assumptions",
            "",
            "- Seasonality and country coefficients are loaded from `config/opex.yaml`.",
            f"- Controlled noise: normal(loc={config['controlled_noise']['loc']}, "
            f"scale={config['controlled_noise']['scale']}), clipped to "
            f"[{config['controlled_noise']['minimum']}, "
            f"{config['controlled_noise']['maximum']}].",
            "- Final OPEX = Base OPEX × Seasonality × Country Factor × Noise Factor.",
            "",
            "## Fixed Allocation by Month and Department",
            "",
            fixed_check.to_markdown(index=False),
            "",
            "Each fixed_component total reconciles to its department fixed_monthly config.",
            "",
            "## Output Files",
            "",
            f"- `{OPEX_PATH.name}`: {len(artifacts['opex_output']):,} rows",
            f"- `{FINANCE_FACT_PATH.name}`: {len(artifacts['finance_fact']):,} rows",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    config = load_config()
    actual_df = load_actual()
    artifacts = build_artifacts(actual_df, config)
    validation, fixed_check = validate_artifacts(artifacts, config)
    validate_determinism(actual_df, config, artifacts)
    write_outputs(artifacts["opex_output"], artifacts["finance_fact"])
    validate_csv_round_trip()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        generate_report(artifacts, validation, fixed_check, config), encoding="utf-8"
    )

    print("OPEX pipeline completed successfully.")
    print(f"- OPEX: {len(artifacts['opex_output']):,} rows -> {OPEX_PATH}")
    print(
        f"- Finance fact: {len(artifacts['finance_fact']):,} rows -> "
        f"{FINANCE_FACT_PATH}"
    )
    print(f"Validation report generated: {REPORT_PATH}")


if __name__ == "__main__":
    main()
