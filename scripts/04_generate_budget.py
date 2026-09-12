from pathlib import Path

import numpy as np
import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DRIVERS_PATH = PROJECT_ROOT / "data" / "processed" / "drivers.csv"
ACTUAL_PATH = PROJECT_ROOT / "data" / "processed" / "actual.csv"
OPEX_PATH = PROJECT_ROOT / "data" / "processed" / "opex.csv"
FINANCE_FACT_PATH = PROJECT_ROOT / "data" / "processed" / "finance_fact.csv"
BUDGET_DRIVER_PATH = PROJECT_ROOT / "data" / "processed" / "budget_drivers.csv"
BUDGET_PATH = PROJECT_ROOT / "data" / "processed" / "budget.csv"
ASSUMPTION_PATH = PROJECT_ROOT / "data" / "processed" / "budget_assumptions.csv"
CONFIG_PATH = PROJECT_ROOT / "config" / "budget.yaml"
REPORT_PATH = PROJECT_ROOT / "reports" / "budget_generation_report.md"

VERSION_ACTUAL = "ACTUAL"
VERSION_BUDGET = "BUDGET"
PROJECT_CURRENCY = "USD"
BUDGET_SOURCE = "budget_engine_v1"
TOLERANCE = 0.01

DRIVER_GRAIN = ["period_date", "country", "product", "segment", "version"]
OPERATING_GRAIN = [
    "period_date",
    "country",
    "product",
    "segment",
    "account",
    "version",
]
OPEX_GRAIN = ["period_date", "country", "department", "account", "version"]
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
CANONICAL_COLUMNS = FINANCE_FACT_GRAIN + ["amount"]
BUDGET_DRIVER_COLUMNS = [
    "period_date",
    "country",
    "product",
    "segment",
    "version",
    "units",
    "average_sale_price",
    "unit_cogs",
    "discount_rate",
    "source",
]
ASSUMPTION_COLUMNS = [
    "scenario",
    "period",
    "dimension_type",
    "dimension_value",
    "assumption_name",
    "assumption_value",
]
OPERATING_ACCOUNT_MAPPING = {
    "budget_gross_sales": "GROSS_SALES",
    "budget_discounts": "DISCOUNT",
    "budget_revenue": "REVENUE",
    "budget_cogs": "COGS",
    "budget_gross_profit": "GROSS_PROFIT",
}
OPEX_CONFIG_KEYS = {
    "OPEX_SALES": "sales_growth",
    "OPEX_MARKETING": "marketing_growth",
    "OPEX_OPERATIONS": "operations_growth",
    "OPEX_RND": "rnd_growth",
    "OPEX_GNA": "gna_growth",
}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Budget config not found: {CONFIG_PATH}")
    with CONFIG_PATH.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise ValueError("budget.yaml must contain a mapping.")
    if config.get("budget_year") != config.get("base_year", 0) + 1:
        raise ValueError("budget_year must be exactly one year after base_year.")

    budget_config = config.get("budget", {})
    required_global = [
        "units_growth",
        "price_growth",
        "discount_rate_change",
        "cogs_inflation",
    ]
    for name in required_global:
        if "default" not in budget_config.get(name, {}):
            raise ValueError(f"Missing budget assumption: {name}.default")
        if float(budget_config[name]["default"]) <= -1:
            raise ValueError(f"Budget assumption {name} must be greater than -1.")

    opex_config = budget_config.get("opex", {})
    missing_opex = set(OPEX_CONFIG_KEYS.values()).difference(opex_config)
    if missing_opex:
        raise ValueError(f"Missing OPEX growth assumptions: {sorted(missing_opex)}")
    if any(float(opex_config[name]) <= -1 for name in OPEX_CONFIG_KEYS.values()):
        raise ValueError("Every OPEX growth assumption must be greater than -1.")
    return config


def load_csv(path: Path, required_columns: list[str], label: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    result = pd.read_csv(path, parse_dates=["period_date"])
    missing = [column for column in required_columns if column not in result.columns]
    if missing:
        raise ValueError(f"{label} is missing columns: {missing}")
    if result.empty:
        raise ValueError(f"{label} is empty.")
    return result


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    drivers = load_csv(
        DRIVERS_PATH,
        [
            "period_date",
            "country",
            "product",
            "segment",
            "version",
            "units",
            "average_sale_price",
            "discount_rate",
        ],
        "drivers.csv",
    )
    actual = load_csv(
        ACTUAL_PATH,
        [
            "period_date",
            "country",
            "product",
            "segment",
            "account",
            "version",
            "currency",
            "source",
            "amount",
        ],
        "actual.csv",
    )
    opex = load_csv(OPEX_PATH, CANONICAL_COLUMNS, "opex.csv")
    return drivers, actual, opex


def filter_base_year(
    df: pd.DataFrame, base_year: int, label: str
) -> pd.DataFrame:
    result = df.loc[
        (df["version"] == VERSION_ACTUAL)
        & (df["period_date"].dt.year == base_year)
    ].copy()
    if result.empty:
        raise ValueError(f"No ACTUAL {label} data for base year {base_year}.")
    return result


def move_to_budget_year(dates: pd.Series, budget_year: int) -> pd.Series:
    return dates.map(lambda value: value.replace(year=budget_year))


def attach_actual_unit_cogs(
    base_drivers: pd.DataFrame,
    actual: pd.DataFrame,
    base_year: int,
) -> pd.DataFrame:
    keys = ["period_date", "country", "product", "segment"]
    actual_cogs = actual.loc[
        (actual["version"] == VERSION_ACTUAL)
        & (actual["account"] == "COGS")
        & (actual["period_date"].dt.year == base_year)
    ]
    actual_cogs = (
        actual_cogs.groupby(keys, as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "actual_cogs"})
    )

    result = base_drivers.merge(
        actual_cogs,
        on=keys,
        how="left",
        validate="one_to_one",
    )
    if len(result) != len(base_drivers) or result["actual_cogs"].isna().any():
        raise ValueError("Actual COGS coverage does not match base-year drivers.")
    if (result["units"] <= 0).any():
        raise ValueError("Cannot calculate unit COGS with non-positive units.")
    result["actual_unit_cogs"] = result["actual_cogs"] / result["units"]
    return result


def build_budget_driver_detail(
    base_drivers: pd.DataFrame,
    actual: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    budget_config = config["budget"]
    result = attach_actual_unit_cogs(
        base_drivers, actual, int(config["base_year"])
    )
    result["actual_period_date"] = result["period_date"]
    result["actual_units"] = result["units"]
    result["actual_average_sale_price"] = result["average_sale_price"]
    result["actual_discount_rate"] = result["discount_rate"]

    units_growth = float(budget_config["units_growth"]["default"])
    price_growth = float(budget_config["price_growth"]["default"])
    discount_change = float(budget_config["discount_rate_change"]["default"])
    cogs_inflation = float(budget_config["cogs_inflation"]["default"])

    result["budget_units"] = result["actual_units"] * (1 + units_growth)
    result["budget_average_sale_price"] = (
        result["actual_average_sale_price"] * (1 + price_growth)
    )
    result["budget_discount_rate"] = (
        result["actual_discount_rate"] + discount_change
    ).clip(lower=0, upper=1)
    result["budget_unit_cogs"] = result["actual_unit_cogs"] * (1 + cogs_inflation)
    result["budget_gross_sales"] = (
        result["budget_units"] * result["budget_average_sale_price"]
    )
    result["budget_discounts"] = (
        result["budget_gross_sales"] * result["budget_discount_rate"]
    )
    result["budget_revenue"] = (
        result["budget_gross_sales"] - result["budget_discounts"]
    )
    result["budget_cogs"] = result["budget_units"] * result["budget_unit_cogs"]
    result["budget_gross_profit"] = result["budget_revenue"] - result["budget_cogs"]
    result["period_date"] = move_to_budget_year(
        result["period_date"], int(config["budget_year"])
    )
    return result.sort_values(
        ["period_date", "country", "product", "segment"]
    ).reset_index(drop=True)


def build_budget_drivers(detail: pd.DataFrame) -> pd.DataFrame:
    result = pd.DataFrame(
        {
            "period_date": detail["period_date"],
            "country": detail["country"],
            "product": detail["product"],
            "segment": detail["segment"],
            "version": VERSION_BUDGET,
            "units": detail["budget_units"],
            "average_sale_price": detail["budget_average_sale_price"],
            "unit_cogs": detail["budget_unit_cogs"],
            "discount_rate": detail["budget_discount_rate"],
            "source": BUDGET_SOURCE,
        }
    )
    return result[BUDGET_DRIVER_COLUMNS]


def build_budget_operating_finance(detail: pd.DataFrame) -> pd.DataFrame:
    id_columns = ["period_date", "country", "product", "segment"]
    result = detail.melt(
        id_vars=id_columns,
        value_vars=list(OPERATING_ACCOUNT_MAPPING),
        var_name="budget_measure",
        value_name="amount",
    )
    result["department"] = pd.NA
    result["account"] = result["budget_measure"].map(OPERATING_ACCOUNT_MAPPING)
    result["version"] = VERSION_BUDGET
    result["currency"] = PROJECT_CURRENCY
    result["source"] = BUDGET_SOURCE
    return result[CANONICAL_COLUMNS].sort_values(
        ["period_date", "country", "product", "segment", "account"]
    ).reset_index(drop=True)


def build_budget_department_opex(
    actual_opex: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    base_year = int(config["base_year"])
    budget_year = int(config["budget_year"])
    detail = actual_opex.loc[
        (actual_opex["version"] == VERSION_ACTUAL)
        & (actual_opex["period_date"].dt.year == base_year)
        & (actual_opex["account"].isin(OPEX_CONFIG_KEYS))
        & (actual_opex["department"].notna())
    ].copy()
    if detail.empty:
        raise ValueError(f"No department OPEX found for base year {base_year}.")

    opex_config = config["budget"]["opex"]
    detail["actual_period_date"] = detail["period_date"]
    detail["actual_amount"] = detail["amount"]
    detail["growth_assumption"] = detail["account"].map(
        {
            account: float(opex_config[config_key])
            for account, config_key in OPEX_CONFIG_KEYS.items()
        }
    )
    if detail["growth_assumption"].isna().any():
        raise ValueError("A department OPEX row has no growth assumption.")

    detail["period_date"] = move_to_budget_year(detail["period_date"], budget_year)
    detail["amount"] = detail["actual_amount"] * (1 + detail["growth_assumption"])
    detail["version"] = VERSION_BUDGET
    detail["source"] = BUDGET_SOURCE
    result = detail[CANONICAL_COLUMNS].sort_values(
        ["period_date", "country", "department", "account"]
    ).reset_index(drop=True)
    return result, detail.reset_index(drop=True)


def build_budget_opex_total(department_opex: pd.DataFrame) -> pd.DataFrame:
    result = (
        department_opex.groupby(
            ["period_date", "country", "version", "currency"], as_index=False
        )["amount"]
        .sum()
        .sort_values(["period_date", "country"])
        .reset_index(drop=True)
    )
    result["product"] = pd.NA
    result["segment"] = pd.NA
    result["department"] = pd.NA
    result["account"] = "OPEX_TOTAL"
    result["source"] = BUDGET_SOURCE
    return result[CANONICAL_COLUMNS]


def build_budget_ebitda(
    operating_finance: pd.DataFrame,
    opex_total: pd.DataFrame,
) -> pd.DataFrame:
    gross_profit = (
        operating_finance.loc[operating_finance["account"] == "GROSS_PROFIT"]
        .groupby(["period_date", "country"], as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": "gross_profit"})
    )
    result = gross_profit.merge(
        opex_total[["period_date", "country", "amount"]].rename(
            columns={"amount": "opex_total"}
        ),
        on=["period_date", "country"],
        how="inner",
        validate="one_to_one",
    )
    if len(result) != len(gross_profit) or len(result) != len(opex_total):
        raise ValueError("Budget Gross Profit and OPEX coverage do not align.")

    result["amount"] = result["gross_profit"] - result["opex_total"]
    result["product"] = pd.NA
    result["segment"] = pd.NA
    result["department"] = pd.NA
    result["account"] = "EBITDA"
    result["version"] = VERSION_BUDGET
    result["currency"] = PROJECT_CURRENCY
    result["source"] = BUDGET_SOURCE
    return result[CANONICAL_COLUMNS]


def build_budget_output(
    operating_finance: pd.DataFrame,
    department_opex: pd.DataFrame,
    opex_total: pd.DataFrame,
    ebitda: pd.DataFrame,
) -> pd.DataFrame:
    return (
        pd.concat(
            [operating_finance, department_opex, opex_total, ebitda],
            ignore_index=True,
        )
        .sort_values(
            ["period_date", "country", "product", "segment", "department", "account"],
            na_position="last",
        )
        .reset_index(drop=True)
    )


def build_assumptions(config: dict, actual_opex: pd.DataFrame) -> pd.DataFrame:
    budget_config = config["budget"]
    rows = [
        {
            "scenario": VERSION_BUDGET,
            "period": int(config["budget_year"]),
            "dimension_type": "GLOBAL",
            "dimension_value": "ALL",
            "assumption_name": name,
            "assumption_value": float(budget_config[name]["default"]),
        }
        for name in [
            "units_growth",
            "price_growth",
            "discount_rate_change",
            "cogs_inflation",
        ]
    ]

    department_names = (
        actual_opex.loc[
            actual_opex["account"].isin(OPEX_CONFIG_KEYS)
            & actual_opex["department"].notna(),
            ["account", "department"],
        ]
        .drop_duplicates()
        .set_index("account")["department"]
        .to_dict()
    )
    for account, config_key in OPEX_CONFIG_KEYS.items():
        rows.append(
            {
                "scenario": VERSION_BUDGET,
                "period": int(config["budget_year"]),
                "dimension_type": "DEPARTMENT",
                "dimension_value": department_names[account],
                "assumption_name": "opex_growth",
                "assumption_value": float(budget_config["opex"][config_key]),
            }
        )
    return pd.DataFrame(rows, columns=ASSUMPTION_COLUMNS)


def prepare_actual_finance(actual: pd.DataFrame, actual_opex: pd.DataFrame) -> pd.DataFrame:
    actual_base = actual.copy()
    actual_base["department"] = pd.NA
    actual_base = actual_base[CANONICAL_COLUMNS]
    result = pd.concat([actual_base, actual_opex[CANONICAL_COLUMNS]], ignore_index=True)
    if not (result["version"] == VERSION_ACTUAL).all():
        raise ValueError("Authoritative Actual files contain a non-ACTUAL version.")
    return result


def build_finance_fact(
    actual: pd.DataFrame,
    actual_opex: pd.DataFrame,
    budget: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    authoritative_actual = prepare_actual_finance(actual, actual_opex)
    finance_fact = (
        pd.concat([authoritative_actual, budget], ignore_index=True)
        .sort_values(
            [
                "version",
                "period_date",
                "country",
                "product",
                "segment",
                "department",
                "account",
            ],
            na_position="last",
        )
        .reset_index(drop=True)
    )
    return finance_fact, authoritative_actual


def assert_unique(df: pd.DataFrame, columns: list[str], label: str) -> None:
    duplicate_count = int(df.duplicated(subset=columns).sum())
    if duplicate_count:
        raise ValueError(f"{label} has {duplicate_count} duplicates at {columns}.")


def validate_driver_formulas(detail: pd.DataFrame, config: dict) -> None:
    budget_config = config["budget"]
    checks = {
        "Budget Units": (
            detail["budget_units"],
            detail["actual_units"]
            * (1 + float(budget_config["units_growth"]["default"])),
        ),
        "Budget Price": (
            detail["budget_average_sale_price"],
            detail["actual_average_sale_price"]
            * (1 + float(budget_config["price_growth"]["default"])),
        ),
        "Budget Discount Rate": (
            detail["budget_discount_rate"],
            (
                detail["actual_discount_rate"]
                + float(budget_config["discount_rate_change"]["default"])
            ).clip(0, 1),
        ),
        "Actual Unit COGS": (
            detail["actual_unit_cogs"],
            detail["actual_cogs"] / detail["actual_units"],
        ),
        "Budget Unit COGS": (
            detail["budget_unit_cogs"],
            detail["actual_unit_cogs"]
            * (1 + float(budget_config["cogs_inflation"]["default"])),
        ),
        "Budget Gross Sales": (
            detail["budget_gross_sales"],
            detail["budget_units"] * detail["budget_average_sale_price"],
        ),
        "Budget Discount": (
            detail["budget_discounts"],
            detail["budget_gross_sales"] * detail["budget_discount_rate"],
        ),
        "Budget Revenue": (
            detail["budget_revenue"],
            detail["budget_gross_sales"] - detail["budget_discounts"],
        ),
        "Budget COGS": (
            detail["budget_cogs"],
            detail["budget_units"] * detail["budget_unit_cogs"],
        ),
        "Budget Gross Profit": (
            detail["budget_gross_profit"],
            detail["budget_revenue"] - detail["budget_cogs"],
        ),
    }
    for label, (actual_values, expected_values) in checks.items():
        if not np.allclose(actual_values, expected_values, atol=TOLERANCE):
            raise ValueError(f"Formula validation failed: {label}.")


def validate_finance_formulas(
    operating_finance: pd.DataFrame,
    department_opex: pd.DataFrame,
    opex_total: pd.DataFrame,
    ebitda: pd.DataFrame,
) -> None:
    operating_keys = ["period_date", "country", "product", "segment"]
    operating_pivot = operating_finance.pivot(
        index=operating_keys, columns="account", values="amount"
    )
    if not np.allclose(
        operating_pivot["GROSS_SALES"] - operating_pivot["DISCOUNT"],
        operating_pivot["REVENUE"],
        atol=TOLERANCE,
    ):
        raise ValueError("Budget Revenue reconciliation failed.")
    if not np.allclose(
        operating_pivot["REVENUE"] - operating_pivot["COGS"],
        operating_pivot["GROSS_PROFIT"],
        atol=TOLERANCE,
    ):
        raise ValueError("Budget Gross Profit reconciliation failed.")

    department_total = department_opex.groupby(
        ["period_date", "country"], as_index=False
    )["amount"].sum()
    total_check = department_total.merge(
        opex_total[["period_date", "country", "amount"]],
        on=["period_date", "country"],
        how="outer",
        suffixes=("_departments", "_total"),
        validate="one_to_one",
    )
    if total_check.isna().any().any() or not np.allclose(
        total_check["amount_departments"], total_check["amount_total"], atol=TOLERANCE
    ):
        raise ValueError("Budget OPEX Total reconciliation failed.")

    gross_profit = (
        operating_finance.loc[operating_finance["account"] == "GROSS_PROFIT"]
        .groupby(["period_date", "country"], as_index=False)["amount"]
        .sum()
    )
    ebitda_check = gross_profit.merge(
        opex_total[["period_date", "country", "amount"]],
        on=["period_date", "country"],
        suffixes=("_gross_profit", "_opex_total"),
        validate="one_to_one",
    ).merge(
        ebitda[["period_date", "country", "amount"]].rename(
            columns={"amount": "ebitda"}
        ),
        on=["period_date", "country"],
        validate="one_to_one",
    )
    if not np.allclose(
        ebitda_check["amount_gross_profit"] - ebitda_check["amount_opex_total"],
        ebitda_check["ebitda"],
        atol=TOLERANCE,
    ):
        raise ValueError("Budget EBITDA reconciliation failed.")


def validate_date_alignment(driver_detail: pd.DataFrame, opex_detail: pd.DataFrame, config: dict) -> None:
    base_year = int(config["base_year"])
    budget_year = int(config["budget_year"])
    if not (
        (driver_detail["actual_period_date"].dt.year == base_year).all()
        and (driver_detail["period_date"].dt.year == budget_year).all()
        and (
            driver_detail["actual_period_date"].dt.month
            == driver_detail["period_date"].dt.month
        ).all()
    ):
        raise ValueError("Budget driver dates are not aligned month-to-month.")
    if not (
        (opex_detail["actual_period_date"].dt.year == base_year).all()
        and (opex_detail["period_date"].dt.year == budget_year).all()
        and (
            opex_detail["actual_period_date"].dt.month
            == opex_detail["period_date"].dt.month
        ).all()
    ):
        raise ValueError("Budget OPEX dates are not aligned month-to-month.")
    if set(driver_detail["period_date"].dt.month) != set(range(1, 13)):
        raise ValueError("Budget drivers do not cover all 12 months.")


def validate_opex_growth(opex_detail: pd.DataFrame) -> None:
    expected = opex_detail["actual_amount"] * (1 + opex_detail["growth_assumption"])
    if not np.allclose(opex_detail["amount"], expected, atol=TOLERANCE):
        raise ValueError("Budget department OPEX does not match growth assumptions.")


def validate_grains(artifacts: dict) -> None:
    assert_unique(artifacts["budget_drivers"], DRIVER_GRAIN, "budget_drivers.csv")
    assert_unique(artifacts["operating_finance"], OPERATING_GRAIN, "Budget operating fact")
    assert_unique(artifacts["department_opex"], OPEX_GRAIN, "Budget department OPEX")
    assert_unique(artifacts["opex_total"], COUNTRY_ACCOUNT_GRAIN, "Budget OPEX Total")
    assert_unique(artifacts["ebitda"], COUNTRY_ACCOUNT_GRAIN, "Budget EBITDA")
    assert_unique(artifacts["budget"], FINANCE_FACT_GRAIN, "budget.csv")
    assert_unique(artifacts["finance_fact"], FINANCE_FACT_GRAIN, "finance_fact.csv")


def validate_row_coverage(artifacts: dict) -> None:
    driver_rows = len(artifacts["base_drivers"])
    country_month_rows = len(
        artifacts["department_opex"][["period_date", "country"]].drop_duplicates()
    )
    if len(artifacts["budget_drivers"]) != driver_rows:
        raise ValueError("Budget driver row count does not match base-year drivers.")
    if len(artifacts["operating_finance"]) != driver_rows * 5:
        raise ValueError("Budget operating fact does not have five accounts per driver row.")
    if len(artifacts["department_opex"]) != country_month_rows * 5:
        raise ValueError("Budget OPEX does not have five departments per country-month.")
    if len(artifacts["opex_total"]) != country_month_rows:
        raise ValueError("Budget OPEX Total row coverage is incomplete.")
    if len(artifacts["ebitda"]) != country_month_rows:
        raise ValueError("Budget EBITDA row coverage is incomplete.")


def validate_actual_preserved(artifacts: dict) -> None:
    combined_actual = artifacts["finance_fact"].loc[
        artifacts["finance_fact"]["version"] == VERSION_ACTUAL
    ].reset_index(drop=True)
    expected_actual = artifacts["authoritative_actual"].sort_values(
        ["period_date", "country", "product", "segment", "department", "account"],
        na_position="last",
    ).reset_index(drop=True)
    combined_actual = combined_actual.sort_values(
        ["period_date", "country", "product", "segment", "department", "account"],
        na_position="last",
    ).reset_index(drop=True)
    pd.testing.assert_frame_equal(combined_actual, expected_actual, check_exact=True)


def validate_assumptions(assumptions: pd.DataFrame, config: dict) -> None:
    if list(assumptions.columns) != ASSUMPTION_COLUMNS or len(assumptions) != 9:
        raise ValueError("budget_assumptions.csv must contain the nine baseline assumptions.")
    if assumptions.duplicated(
        ["scenario", "period", "dimension_type", "dimension_value", "assumption_name"]
    ).any():
        raise ValueError("Budget assumptions contain duplicate keys.")
    if not (assumptions["scenario"] == VERSION_BUDGET).all():
        raise ValueError("Budget assumption scenario must be BUDGET.")
    if not (assumptions["period"] == int(config["budget_year"])).all():
        raise ValueError("Budget assumption period does not match budget_year.")


def build_artifacts(
    drivers: pd.DataFrame,
    actual: pd.DataFrame,
    actual_opex: pd.DataFrame,
    config: dict,
) -> dict:
    base_drivers = filter_base_year(
        drivers, int(config["base_year"]), "driver"
    )
    driver_detail = build_budget_driver_detail(base_drivers, actual, config)
    budget_drivers = build_budget_drivers(driver_detail)
    operating_finance = build_budget_operating_finance(driver_detail)
    department_opex, opex_detail = build_budget_department_opex(actual_opex, config)
    opex_total = build_budget_opex_total(department_opex)
    ebitda = build_budget_ebitda(operating_finance, opex_total)
    budget = build_budget_output(
        operating_finance, department_opex, opex_total, ebitda
    )
    assumptions = build_assumptions(config, actual_opex)
    finance_fact, authoritative_actual = build_finance_fact(
        actual, actual_opex, budget
    )
    return {
        "base_drivers": base_drivers,
        "driver_detail": driver_detail,
        "budget_drivers": budget_drivers,
        "operating_finance": operating_finance,
        "department_opex": department_opex,
        "opex_detail": opex_detail,
        "opex_total": opex_total,
        "ebitda": ebitda,
        "budget": budget,
        "assumptions": assumptions,
        "finance_fact": finance_fact,
        "authoritative_actual": authoritative_actual,
    }


def validate_artifacts(artifacts: dict, config: dict) -> dict:
    validate_driver_formulas(artifacts["driver_detail"], config)
    validate_finance_formulas(
        artifacts["operating_finance"],
        artifacts["department_opex"],
        artifacts["opex_total"],
        artifacts["ebitda"],
    )
    validate_opex_growth(artifacts["opex_detail"])
    validate_date_alignment(artifacts["driver_detail"], artifacts["opex_detail"], config)
    validate_grains(artifacts)
    validate_row_coverage(artifacts)
    validate_actual_preserved(artifacts)
    validate_assumptions(artifacts["assumptions"], config)
    if not (artifacts["budget"]["version"] == VERSION_BUDGET).all():
        raise ValueError("Every budget.csv row must have version BUDGET.")

    return {
        "driver_formulas": True,
        "revenue_reconciliation": True,
        "gross_profit_reconciliation": True,
        "opex_growth_assumptions": True,
        "opex_total_reconciliation": True,
        "ebitda_reconciliation": True,
        "canonical_grains_unique": True,
        "date_alignment_2014_to_2015": True,
        "no_accidental_row_loss": True,
        "actual_2014_preserved": True,
        "assumptions_stored_separately": True,
        "budget_version": True,
    }


def validate_determinism(
    drivers: pd.DataFrame,
    actual: pd.DataFrame,
    actual_opex: pd.DataFrame,
    config: dict,
    first: dict,
) -> None:
    second = build_artifacts(drivers, actual, actual_opex, config)
    for name in ["budget_drivers", "budget", "assumptions", "finance_fact"]:
        pd.testing.assert_frame_equal(first[name], second[name], check_exact=True)


def write_outputs(artifacts: dict) -> None:
    BUDGET_PATH.parent.mkdir(parents=True, exist_ok=True)
    artifacts["budget_drivers"].to_csv(
        BUDGET_DRIVER_PATH, index=False, date_format="%Y-%m-%d"
    )
    artifacts["assumptions"].to_csv(ASSUMPTION_PATH, index=False)
    artifacts["budget"].to_csv(BUDGET_PATH, index=False, date_format="%Y-%m-%d")
    artifacts["finance_fact"].to_csv(
        FINANCE_FACT_PATH, index=False, date_format="%Y-%m-%d"
    )


def validate_csv_round_trip(artifacts: dict) -> None:
    budget_drivers = pd.read_csv(BUDGET_DRIVER_PATH, parse_dates=["period_date"])
    assumptions = pd.read_csv(ASSUMPTION_PATH)
    budget = pd.read_csv(BUDGET_PATH, parse_dates=["period_date"])
    finance_fact = pd.read_csv(FINANCE_FACT_PATH, parse_dates=["period_date"])

    expected = {
        "budget_drivers.csv": (
            budget_drivers,
            BUDGET_DRIVER_COLUMNS,
            len(artifacts["budget_drivers"]),
        ),
        "budget_assumptions.csv": (
            assumptions,
            ASSUMPTION_COLUMNS,
            len(artifacts["assumptions"]),
        ),
        "budget.csv": (budget, CANONICAL_COLUMNS, len(artifacts["budget"])),
        "finance_fact.csv": (
            finance_fact,
            CANONICAL_COLUMNS,
            len(artifacts["finance_fact"]),
        ),
    }
    for label, (frame, columns, row_count) in expected.items():
        if list(frame.columns) != columns or len(frame) != row_count:
            raise ValueError(f"{label} failed schema or row-count round-trip.")

    assert_unique(budget_drivers, DRIVER_GRAIN, "budget_drivers.csv")
    assert_unique(budget, FINANCE_FACT_GRAIN, "budget.csv")
    assert_unique(finance_fact, FINANCE_FACT_GRAIN, "finance_fact.csv")

    operating = budget.loc[budget["account"].isin(OPERATING_ACCOUNT_MAPPING.values())]
    department_opex = budget.loc[budget["account"].isin(OPEX_CONFIG_KEYS)]
    opex_total = budget.loc[budget["account"] == "OPEX_TOTAL"]
    ebitda = budget.loc[budget["account"] == "EBITDA"]
    validate_finance_formulas(operating, department_opex, opex_total, ebitda)


def build_comparison_summary(
    authoritative_actual: pd.DataFrame,
    budget: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    accounts = ["REVENUE", "COGS", "GROSS_PROFIT", "OPEX_TOTAL", "EBITDA"]
    actual_base = authoritative_actual.loc[
        (authoritative_actual["period_date"].dt.year == int(config["base_year"]))
        & (authoritative_actual["account"].isin(accounts))
    ]
    actual_totals = actual_base.groupby("account")["amount"].sum()
    budget_totals = budget.loc[budget["account"].isin(accounts)].groupby("account")[
        "amount"
    ].sum()
    result = pd.DataFrame(
        {
            "account": accounts,
            "actual_2014": [actual_totals[account] for account in accounts],
            "budget_2015": [budget_totals[account] for account in accounts],
        }
    )
    result["variance"] = result["budget_2015"] - result["actual_2014"]
    result["variance_pct"] = np.where(
        result["actual_2014"] != 0,
        result["variance"] / result["actual_2014"],
        np.nan,
    )
    return result


def generate_report(
    artifacts: dict,
    validation: dict,
    comparison: pd.DataFrame,
    config: dict,
) -> str:
    budget_config = config["budget"]
    lines = [
        "# Budget Generation Report",
        "",
        "## Pipeline Result",
        "",
        "- Status: passed",
        f"- Base year: {config['base_year']}",
        f"- Budget year: {config['budget_year']}",
        "- Planning method: driver-based deterministic budget",
        f"- Budget driver rows: {len(artifacts['budget_drivers']):,}",
        f"- Budget finance rows: {len(artifacts['budget']):,}",
        f"- Combined finance fact rows: {len(artifacts['finance_fact']):,}",
        "",
        "## Planning Assumptions",
        "",
        f"- Units growth: {float(budget_config['units_growth']['default']):.2%}",
        f"- Price growth: {float(budget_config['price_growth']['default']):.2%}",
        f"- Discount-rate change: {float(budget_config['discount_rate_change']['default']):.2%} points",
        f"- COGS inflation: {float(budget_config['cogs_inflation']['default']):.2%}",
        "",
        artifacts["assumptions"].to_markdown(index=False),
        "",
        "## Validation Checks",
        "",
    ]
    for name, passed in validation.items():
        lines.append(f"- {name}: {'passed' if passed else 'failed'}")
    lines.extend(
        [
            "- deterministic_rebuild: passed",
            "- csv_round_trip_and_formulas: passed",
            "",
            "## Actual 2014 vs Budget 2015",
            "",
            comparison.to_markdown(index=False, floatfmt=('', '.2f', '.2f', '.2f', '.4f')),
            "",
            "## Output Files",
            "",
            f"- `{BUDGET_DRIVER_PATH.name}`: {len(artifacts['budget_drivers']):,} rows",
            f"- `{ASSUMPTION_PATH.name}`: {len(artifacts['assumptions']):,} rows",
            f"- `{BUDGET_PATH.name}`: {len(artifacts['budget']):,} rows",
            f"- `{FINANCE_FACT_PATH.name}`: {len(artifacts['finance_fact']):,} rows",
            "",
            "`finance_fact.csv` is rebuilt from authoritative Actual files plus Budget on every run; Budget rows are never appended in place.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    config = load_config()
    drivers, actual, actual_opex = load_inputs()
    artifacts = build_artifacts(drivers, actual, actual_opex, config)
    validation = validate_artifacts(artifacts, config)
    validate_determinism(drivers, actual, actual_opex, config, artifacts)
    write_outputs(artifacts)
    validate_csv_round_trip(artifacts)
    comparison = build_comparison_summary(
        artifacts["authoritative_actual"], artifacts["budget"], config
    )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        generate_report(artifacts, validation, comparison, config),
        encoding="utf-8",
    )

    print("Budget pipeline completed successfully.")
    print(f"- Budget drivers: {len(artifacts['budget_drivers']):,} -> {BUDGET_DRIVER_PATH}")
    print(f"- Budget assumptions: {len(artifacts['assumptions']):,} -> {ASSUMPTION_PATH}")
    print(f"- Budget finance: {len(artifacts['budget']):,} -> {BUDGET_PATH}")
    print(f"- Combined finance fact: {len(artifacts['finance_fact']):,} -> {FINANCE_FACT_PATH}")
    print(f"Validation report generated: {REPORT_PATH}")


if __name__ == "__main__":
    main()
