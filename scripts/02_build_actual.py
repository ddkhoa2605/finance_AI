from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]

RAW_PATH = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "Financial Sample.xlsx"
)

PROCESSED_DIR = (
    PROJECT_ROOT
    / "data"
    / "processed"
)

REPORT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "actual_build_report.md"
)

PROJECT_CURRENCY = "USD"

SOURCE_NAME = "microsoft_financial_sample"

VERSION_ACTUAL = "ACTUAL"

def load_source() -> pd.DataFrame:
    """Load the source data from the raw Excel file."""
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"Raw data file not found: {RAW_PATH}")

    df = pd.read_excel(RAW_PATH)
    if df.empty:
        raise ValueError(f"Loaded data is empty from: {RAW_PATH}")

    return df

REQUIRED_COLUMNS = [
    "Segment",
    "Country",
    "Product",
    "Discount Band",
    "Units Sold",
    "Manufacturing Price",
    "Sale Price",
    "Gross Sales",
    "Discounts",
    " Sales",
    "COGS",
    "Profit",
    "Date",
]

def validate_required_columns(
    df: pd.DataFrame,
) -> None:
    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"Missing required columns: {missing}"
        )

def build_staging(
    df: pd.DataFrame,
) -> pd.DataFrame:
    staging = df.copy()

    staging = staging.reset_index(
        drop=True
    )

    staging.insert(
        0,
        "source_row_id",
        staging.index + 1,
    )

    return staging

COLUMN_MAPPING = {
    "Segment": "segment",
    "Country": "country",
    "Product": "product",
    "Discount Band": "discount_band",
    "Units Sold": "units_sold",
    "Manufacturing Price": "manufacturing_price",
    "Sale Price": "sale_price",
    "Gross Sales": "gross_sales",
    "Discounts": "discounts",
    " Sales": "sales",
    "COGS": "cogs",
    "Profit": "profit",
    "Date": "date",
    "Month Number": "month_number",
    "Month Name": "month_name",
    "Year": "year",
}

def normalize_columns(
    df: pd.DataFrame,
) -> pd.DataFrame:
    return df.rename(
        columns=COLUMN_MAPPING
    )

def normalize_date(
    df: pd.DataFrame,
) -> pd.DataFrame:
    df = df.copy()

    df["date"] = pd.to_datetime(
        df["date"],
        errors="raise",
    )

    df["period_date"] = (
        df["date"]
        .dt.to_period("M")
        .dt.to_timestamp()
    )

    return df

def normalize_text_dimensions(
    df: pd.DataFrame,
) -> pd.DataFrame:
    df = df.copy()

    columns = [
        "country",
        "product",
        "segment",
    ]

    for column in columns:
        df[column] = (
            df[column]
            .astype("string")
            .str.strip()
        )

    return df

def normalize_discount_band(
    df: pd.DataFrame,
) -> pd.DataFrame:
    df = df.copy()

    df["discount_band_raw"] = (
        df["discount_band"]
    )

    df["discount_band"] = (
        df["discount_band"]
        .astype("string")
        .str.strip()
        .fillna("NONE")
    )

    return df

def assert_close(
    actual: pd.Series,
    expected: pd.Series,
    name: str,
    tolerance: float = 0.01,
) -> None:
    difference = (
        actual - expected
    ).abs()

    failures = (
        difference > tolerance
    ).sum()

    if failures > 0:
        raise ValueError(
            f"{name} validation failed "
            f"for {failures} rows."
        )

def validate_source_formulas(
    df: pd.DataFrame,
) -> None:

    assert_close(
        df["gross_sales"],
        df["units_sold"]
        * df["sale_price"],
        "Gross Sales",
    )

    assert_close(
        df["sales"],
        df["gross_sales"]
        - df["discounts"],
        "Sales",
    )

    assert_close(
        df["profit"],
        df["sales"]
        - df["cogs"],
        "Profit",
    )

def add_derived_metrics(
    df: pd.DataFrame,
) -> pd.DataFrame:
    df = df.copy()

    df["gross_profit"] = (
        df["sales"]
        - df["cogs"]
    )

    df["discount_rate"] = np.where(
        df["gross_sales"] != 0,
        df["discounts"]
        / df["gross_sales"],
        np.nan,
    )

    return df

def save_staging(
    df: pd.DataFrame,
) -> None:
    PROCESSED_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    path = (
        PROCESSED_DIR
        / "actual_staging.csv"
    )

    df.to_csv(
        path,
        index=False,
    )

CANONICAL_DIMENSIONS = [
    "period_date",
    "country",
    "product",
    "segment",
]

def aggregate_actual(
    df: pd.DataFrame,
) -> pd.DataFrame:

    aggregated = (
        df.groupby(
            CANONICAL_DIMENSIONS,
            dropna=False,
            as_index=False,
        )
        .agg(
            units_sold=(
                "units_sold",
                "sum",
            ),
            gross_sales=(
                "gross_sales",
                "sum",
            ),
            discounts=(
                "discounts",
                "sum",
            ),
            revenue=(
                "sales",
                "sum",
            ),
            cogs=(
                "cogs",
                "sum",
            ),
            source_profit=(
                "profit",
                "sum",
            ),
        )
    )

    aggregated["gross_profit"] = (
        aggregated["revenue"]
        - aggregated["cogs"]
    )

    return aggregated

def validate_aggregated_profit(
    df: pd.DataFrame,
) -> None:

    assert_close(
        actual=df["source_profit"],
        expected=df["gross_profit"],
        name="Aggregated Gross Profit",
    )

ACCOUNT_MAPPING = {
    "gross_sales": "GROSS_SALES",
    "discounts": "DISCOUNT",
    "revenue": "REVENUE",
    "cogs": "COGS",
    "gross_profit": "GROSS_PROFIT",
}

def build_fact_finance(
    aggregated: pd.DataFrame,
) -> pd.DataFrame:

    value_columns = list(
        ACCOUNT_MAPPING.keys()
    )

    fact = aggregated.melt(
        id_vars=CANONICAL_DIMENSIONS,
        value_vars=value_columns,
        var_name="metric",
        value_name="amount",
    )

    fact["account"] = (
        fact["metric"]
        .map(ACCOUNT_MAPPING)
    )

    fact["version"] = (
        VERSION_ACTUAL
    )

    fact["department"] = pd.NA

    fact["currency"] = (
        PROJECT_CURRENCY
    )

    fact["source"] = (
        SOURCE_NAME
    )

    fact = fact[
        [
            "period_date",
            "country",
            "product",
            "segment",
            "department",
            "account",
            "version",
            "amount",
            "currency",
            "source",
        ]
    ]

    return fact

def validate_fact_finance_grain(
    fact: pd.DataFrame,
) -> None:

    grain = [
        "period_date",
        "country",
        "product",
        "segment",
        "account",
        "version",
    ]

    duplicated = (
        fact.duplicated(
            subset=grain,
            keep=False,
        )
    )

    count = int(
        duplicated.sum()
    )

    if count > 0:
        raise ValueError(
            "fact_finance grain is not unique. "
            f"Repeated rows: {count}"
        )

def save_fact_finance(
    fact: pd.DataFrame,
) -> None:

    path = (
        PROCESSED_DIR
        / "actual.csv"
    )

    fact.to_csv(
        path,
        index=False,
    )

def add_driver_components(
    df: pd.DataFrame,
) -> pd.DataFrame:

    df = df.copy()

    df[
        "manufacturing_price_weighted"
    ] = (
        df["manufacturing_price"]
        * df["units_sold"]
    )

    return df

def build_fact_driver(
    df: pd.DataFrame,
) -> pd.DataFrame:

    temp = add_driver_components(
        df
    )

    drivers = (
        temp.groupby(
            CANONICAL_DIMENSIONS,
            dropna=False,
            as_index=False,
        )
        .agg(
            units=(
                "units_sold",
                "sum",
            ),
            gross_sales=(
                "gross_sales",
                "sum",
            ),
            discounts=(
                "discounts",
                "sum",
            ),
            weighted_manufacturing_price=(
                "manufacturing_price_weighted",
                "sum",
            ),
        )
    )

    drivers[
        "average_sale_price"
    ] = np.where(
        drivers["units"] != 0,
        drivers["gross_sales"]
        / drivers["units"],
        np.nan,
    )

    drivers[
        "average_manufacturing_price"
    ] = np.where(
        drivers["units"] != 0,
        drivers[
            "weighted_manufacturing_price"
        ]
        / drivers["units"],
        np.nan,
    )

    drivers[
        "discount_rate"
    ] = np.where(
        drivers["gross_sales"] != 0,
        drivers["discounts"]
        / drivers["gross_sales"],
        np.nan,
    )

    drivers["version"] = (
        VERSION_ACTUAL
    )

    drivers["source"] = (
        SOURCE_NAME
    )

    drivers = drivers[
        [
            "period_date",
            "country",
            "product",
            "segment",
            "version",
            "units",
            "average_sale_price",
            "average_manufacturing_price",
            "discount_rate",
            "source",
        ]
    ]

    return drivers

def validate_driver_grain(
    drivers: pd.DataFrame,
) -> None:

    grain = [
        "period_date",
        "country",
        "product",
        "segment",
        "version",
    ]

    duplicate_count = int(
        drivers.duplicated(
            subset=grain,
            keep=False,
        ).sum()
    )

    if duplicate_count > 0:
        raise ValueError(
            "fact_driver grain is not unique. "
            f"Repeated rows: {duplicate_count}"
        )

def validate_finance_reconciliation(
    staging: pd.DataFrame,
    fact: pd.DataFrame,
) -> dict:

    checks = {}

    mapping = {
        "GROSS_SALES": (
            staging["gross_sales"].sum()
        ),
        "DISCOUNT": (
            staging["discounts"].sum()
        ),
        "REVENUE": (
            staging["sales"].sum()
        ),
        "COGS": (
            staging["cogs"].sum()
        ),
        "GROSS_PROFIT": (
            staging["profit"].sum()
        ),
    }

    for account, raw_total in mapping.items():

        fact_total = (
            fact.loc[
                fact["account"] == account,
                "amount",
            ]
            .sum()
        )

        difference = (
            fact_total
            - raw_total
        )

        checks[account] = {
            "raw_total": float(
                raw_total
            ),
            "fact_total": float(
                fact_total
            ),
            "difference": float(
                difference
            ),
            "passed": (
                abs(difference)
                <= 0.01
            ),
        }

    return checks

def validate_canonical_formulas(
    fact: pd.DataFrame,
) -> None:

    index_columns = [
        "period_date",
        "country",
        "product",
        "segment",
        "version",
    ]

    wide = (
        fact.pivot_table(
            index=index_columns,
            columns="account",
            values="amount",
            aggfunc="sum",
        )
        .reset_index()
    )

    assert_close(
        wide["REVENUE"],
        wide["GROSS_SALES"]
        - wide["DISCOUNT"],
        "Canonical Revenue",
    )

    assert_close(
        wide["GROSS_PROFIT"],
        wide["REVENUE"]
        - wide["COGS"],
        "Canonical Gross Profit",
    )

def validate_driver_reconciliation(
    staging: pd.DataFrame,
    drivers: pd.DataFrame,
) -> None:

    source_units = (
        staging["units_sold"].sum()
    )

    driver_units = (
        drivers["units"].sum()
    )

    if abs(
        source_units
        - driver_units
    ) > 0.01:
        raise ValueError(
            "Units reconciliation failed."
        )

def save_drivers(
    drivers: pd.DataFrame,
) -> None:

    path = (
        PROCESSED_DIR
        / "drivers.csv"
    )

    drivers.to_csv(
        path,
        index=False,
    )



def main():

    print("Loading source...")

    raw = load_source()

    validate_required_columns(
        raw
    )

    print(
        f"Raw rows: {len(raw)}"
    )

    staging = build_staging(
        raw
    )

    staging = normalize_columns(
        staging
    )

    staging = normalize_date(
        staging
    )

    staging = (
        normalize_text_dimensions(
            staging
        )
    )

    staging = (
        normalize_discount_band(
            staging
        )
    )

    validate_source_formulas(
        staging
    )

    staging = add_derived_metrics(
        staging
    )

    save_staging(
        staging
    )

    print(
        f"Staging rows: "
        f"{len(staging)}"
    )

    aggregated = aggregate_actual(
        staging
    )

    validate_aggregated_profit(
        aggregated
    )

    fact_finance = (
        build_fact_finance(
            aggregated
        )
    )

    validate_fact_finance_grain(
        fact_finance
    )

    reconciliation = (
        validate_finance_reconciliation(
            staging,
            fact_finance,
        )
    )

    validate_canonical_formulas(
        fact_finance
    )

    save_fact_finance(
        fact_finance
    )

    fact_driver = (
        build_fact_driver(
            staging
        )
    )

    validate_driver_grain(
        fact_driver
    )

    validate_driver_reconciliation(
        staging,
        fact_driver,
    )

    save_drivers(
        fact_driver
    )

    print(
        f"fact_finance rows: "
        f"{len(fact_finance)}"
    )

    print(
        f"fact_driver rows: "
        f"{len(fact_driver)}"
    )

    print(
        "Phase 2 Actual build completed."
    )


if __name__ == "__main__":
    main()
