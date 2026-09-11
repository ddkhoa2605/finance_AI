from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_PATH = PROJECT_ROOT / "data" / "raw" / "Financial Sample.xlsx"
REPORT_PATH = PROJECT_ROOT / "reports" / "data_profile.md"


def load_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")
    df = pd.read_excel(path)
    return df


def profile_schema(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for column in df.columns:
        rows.append(
            {
                "column": column,
                "dtype": str(df[column].dtype),
                "non_null": int(df[column].notna().sum()),
                "null": int(df[column].isna().sum()),
                "unique": int(df[column].nunique(dropna=True)),
            }
        )
    return pd.DataFrame(rows)


def profile_nulls(df: pd.DataFrame) -> pd.DataFrame:
    null_count = df.isna().sum()
    result = pd.DataFrame(
        {
            "column": df.columns,
            "null_count": null_count.values,
            "null_pct": (null_count.values / len(df) * 100),
        }
    )
    return result


def profile_duplicates(df: pd.DataFrame) -> dict:
    duplicate_count = int(df.duplicated().sum())
    return {
        "duplicate_rows": duplicate_count,
        "duplicate_pct": (
            duplicate_count / len(df) * 100 if len(df) > 0 else 0
        ),
    }


def detect_date_columns(df: pd.DataFrame) -> list[str]:
    date_columns = []
    for column in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[column]):
            date_columns.append(column)
    return date_columns


def normalize_date_for_profiling(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(
            df["Date"],
            errors="coerce",
        )
    return df


def profile_time_range(df: pd.DataFrame) -> dict:
    if "Date" not in df.columns:
        return {
            "min_date": None,
            "max_date": None,
            "invalid_dates": None,
        }

    dates = pd.to_datetime(
        df["Date"],
        errors="coerce",
    )

    return {
        "min_date": dates.min(),
        "max_date": dates.max(),
        "invalid_dates": int(dates.isna().sum()),
    }


def profile_dimensions(df: pd.DataFrame, column: str) -> dict:
    if column not in df.columns:
        return {
            "exists": False,
            "count": 0,
            "values": [],
        }

    values = (
        df[column]
        .dropna()
        .astype(str)
        .sort_values()
        .unique()
        .tolist()
    )

    return {
        "exists": True,
        "count": len(values),
        "values": values,
    }


def profile_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    numeric_df = df.select_dtypes(include=np.number)

    if numeric_df.empty:
        return pd.DataFrame()

    stats = numeric_df.describe().T.reset_index()
    stats = stats.rename(columns={"index": "column"})
    return stats


def profile_negative_values(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    numeric_columns = df.select_dtypes(include=np.number).columns
    for column in numeric_columns:
        negative_count = int((df[column] < 0).sum())
        rows.append(
            {
                "column": column,
                "negative_count": negative_count,
            }
        )
    return pd.DataFrame(rows)


def profile_discount_band(df: pd.DataFrame) -> pd.DataFrame:
    """Count Discount Band values without treating missing values as None."""
    if "Discount Band" not in df.columns:
        return pd.DataFrame(columns=["discount_band", "row_count"])

    return (
        df["Discount Band"]
        .value_counts(dropna=False)
        .rename_axis("discount_band")
        .rename("row_count")
        .reset_index()
    )


def profile_discount_relationship(df: pd.DataFrame) -> pd.DataFrame:
    """Provide a lightweight check that discount bands match discount amounts."""
    required = ["Discount Band", "Discounts", "Gross Sales"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        return pd.DataFrame(
            {"status": ["not_checked"], "missing_columns": [", ".join(missing)]}
        )

    return (
        df.groupby("Discount Band", dropna=False)
        .agg(
            avg_discounts=("Discounts", "mean"),
            total_discounts=("Discounts", "sum"),
            avg_gross_sales=("Gross Sales", "mean"),
        )
        .reset_index()
    )


def profile_dimension_coverage(df: pd.DataFrame) -> pd.DataFrame:
    """Show which Country/Product combinations are represented in the source."""
    required = ["Country", "Product"]
    missing = [column for column in required if column not in df.columns]
    if missing:
        return pd.DataFrame(
            {"status": ["not_checked"], "missing_columns": [", ".join(missing)]}
        )

    return (
        df.groupby(["Country", "Product"])
        .size()
        .reset_index(name="row_count")
        .sort_values(["Country", "Product"])
        .reset_index(drop=True)
    )


def profile_monthly_coverage(df: pd.DataFrame) -> pd.DataFrame:
    """Report all months between the first and last valid Date, including gaps."""
    if "Date" not in df.columns:
        return pd.DataFrame(
            {"status": ["not_checked"], "missing_columns": ["Date"]}
        )

    months = df["Date"].dt.to_period("M")
    monthly_counts = months.value_counts(sort=False).sort_index()
    if monthly_counts.empty:
        return pd.DataFrame(columns=["month", "row_count"])

    complete_months = pd.period_range(
        monthly_counts.index.min(),
        monthly_counts.index.max(),
        freq="M",
    )
    return (
        monthly_counts.reindex(complete_months, fill_value=0)
        .rename_axis("month")
        .rename("row_count")
        .reset_index()
    )


def validate_formula(
    actual: pd.Series, expected: pd.Series, tolerance: float = 0.01
) -> dict:
    differences = actual - expected
    abs_differences = differences.abs()

    valid = abs_differences <= tolerance
    return {
        "rows_checked": int(valid.notna().sum()),
        "rows_passed": int(valid.sum()),
        "rows_failed": int((~valid).sum()),
        "max_abs_difference": (
            float(abs_differences.max()) if not abs_differences.empty else None
        ),
        "mean_abs_difference": (
            float(abs_differences.mean()) if not abs_differences.empty else None
        ),
    }


def validate_sales_formula(df: pd.DataFrame) -> dict:
    # Chuẩn hóa tạm thời tên cột để tránh lỗi khoảng trắng như ' Sales' hay thiếu 's' trong 'Discounts'
    temp_df = df.copy()
    temp_df.columns = temp_df.columns.str.strip()

    required = ["Sales", "Gross Sales", "Discounts"]
    missing = [column for column in required if column not in temp_df.columns]

    if missing:
        return {
            "status": "not_checked",
            "missing_columns": missing,
        }

    expected_sales = temp_df["Gross Sales"] - temp_df["Discounts"]
    result = validate_formula(
        actual=temp_df["Sales"], expected=expected_sales, tolerance=0.01
    )

    result["status"] = "checked"
    return result


def validate_profit_formula(df: pd.DataFrame) -> dict:
    temp_df = df.copy()
    temp_df.columns = temp_df.columns.str.strip()

    required = ["Profit", "Sales", "COGS"]
    missing = [column for column in required if column not in temp_df.columns]

    if missing:
        return {
            "status": "not_checked",
            "missing_columns": missing,
        }

    expected_profit = temp_df["Sales"] - temp_df["COGS"]
    result = validate_formula(
        actual=temp_df["Profit"], expected=expected_profit, tolerance=0.01
    )

    result["status"] = "checked"
    return result


def validate_gross_sales_formula(df: pd.DataFrame) -> dict:
    temp_df = df.copy()
    temp_df.columns = temp_df.columns.str.strip()

    required = ["Gross Sales", "Units Sold", "Sale Price"]
    missing = [column for column in required if column not in temp_df.columns]

    if missing:
        return {
            "status": "not_checked",
            "missing_columns": missing,
        }

    expected_gross = temp_df["Units Sold"] * temp_df["Sale Price"]
    result = validate_formula(
        actual=temp_df["Gross Sales"], expected=expected_gross, tolerance=0.01
    )

    result["status"] = "checked"
    return result


def check_candidate_grain(df: pd.DataFrame, columns: list[str]) -> dict:
    temp_df = df.copy()
    temp_df.columns = temp_df.columns.str.strip()

    existing_columns = [
        column for column in columns if column in temp_df.columns
    ]

    if not existing_columns:
        return {
            "columns": [],
            "unique": False,
        }

    duplicate_count = int(
        temp_df.duplicated(subset=existing_columns, keep=False).sum()
    )

    return {
        "columns": existing_columns,
        "duplicate_rows_at_grain": duplicate_count,
        "unique": duplicate_count == 0,
    }

def profile_cardinality(
    df: pd.DataFrame,
) -> pd.DataFrame:
    rows = []

    for column in df.columns:
        rows.append(
            {
                "column": column,
                "unique_values": int(
                    df[column].nunique(
                        dropna=True
                    )
                ),
            }
        )

    return (
        pd.DataFrame(rows)
        .sort_values(
            "unique_values"
        )
        .reset_index(drop=True)
    )

def dataframe_to_markdown(
    df: pd.DataFrame,
) -> str:
    if df.empty:
        return "_No data available._"

    return df.to_markdown(
        index=False
    )

def generate_report(
    df: pd.DataFrame,
    schema_df: pd.DataFrame,
    null_df: pd.DataFrame,
    numeric_df: pd.DataFrame,
    negative_df: pd.DataFrame,
    dimensions: dict,
    duplicates: dict,
    time_profile: dict,
    grain_result: dict,
    sales_validation: dict,
    profit_validation: dict,
    gross_sales_validation: dict,
    discount_band_df: pd.DataFrame,
    discount_relationship_df: pd.DataFrame,
    dimension_coverage_df: pd.DataFrame,
    monthly_coverage_df: pd.DataFrame,
) -> str:

    lines = []

    lines.append("# Financial Sample Data Profile")
    lines.append("")

    lines.append("## 1. Dataset Overview")
    lines.append("")
    lines.append(f"- Rows: {len(df):,}")
    lines.append(f"- Columns: {len(df.columns):,}")
    lines.append(
        f"- Duplicate rows: "
        f"{duplicates['duplicate_rows']:,}"
    )

    lines.append("")

    lines.append("## 2. Schema")
    lines.append("")
    lines.append(
        dataframe_to_markdown(
            schema_df
        )
    )

    lines.append("")

    lines.append("## 3. Null Analysis")
    lines.append("")
    lines.append(
        dataframe_to_markdown(
            null_df
        )
    )

    lines.append("")

    lines.append("## 4. Time Range")
    lines.append("")
    lines.append(
        f"- Min date: {time_profile['min_date']}"
    )
    lines.append(
        f"- Max date: {time_profile['max_date']}"
    )
    lines.append(
        f"- Invalid dates: "
        f"{time_profile['invalid_dates']}"
    )

    lines.append("")

    lines.append("## 5. Dimensions")

    for name, profile in dimensions.items():
        lines.append("")
        lines.append(f"### {name}")

        if not profile["exists"]:
            lines.append("Column not found.")
            continue

        lines.append(
            f"- Cardinality: "
            f"{profile['count']}"
        )

        lines.append(
            "- Values: "
            + ", ".join(profile["values"])
        )

    lines.append("")

    lines.append("## 6. Numeric Statistics")
    lines.append("")
    lines.append(
        dataframe_to_markdown(
            numeric_df
        )
    )

    lines.append("")

    lines.append("## 7. Negative Values")
    lines.append("")
    lines.append(
        dataframe_to_markdown(
            negative_df
        )
    )

    lines.append("")

    lines.append("## 8. Candidate Grain")
    lines.append("")
    lines.append(
        f"- Columns: "
        f"{grain_result['columns']}"
    )
    lines.append(
        f"- Duplicate rows at candidate grain: "
        f"{grain_result['duplicate_rows_at_grain']}"
    )
    lines.append(
        f"- Unique grain: "
        f"{grain_result['unique']}"
    )

    lines.append("")

    lines.append("## 9. Formula Validation")

    lines.append("")
    lines.append("### Sales = Gross Sales - Discounts")
    lines.append("")
    lines.append(
        f"```text\n"
        f"{sales_validation}\n"
        f"```"
    )

    lines.append("")
    lines.append("### Profit = Sales - COGS")
    lines.append("")
    lines.append(
        f"```text\n"
        f"{profit_validation}\n"
        f"```"
    )

    lines.append("")
    lines.append(
        "### Gross Sales = Units Sold × Sale Price"
    )
    lines.append("")
    lines.append(
        f"```text\n"
        f"{gross_sales_validation}\n"
        f"```"
    )

    lines.append("")
    lines.append("## 10. Discount Band Values")
    lines.append("")
    lines.append(
        dataframe_to_markdown(
            discount_band_df
        )
    )
    lines.append("")
    lines.append(
        "Missing values are reported as-is; they are not mapped to `None`."
    )

    lines.append("")
    lines.append("## 11. Discount Band Sanity Check")
    lines.append("")
    lines.append(
        dataframe_to_markdown(
            discount_relationship_df
        )
    )

    lines.append("")
    lines.append("## 12. Country and Product Coverage")
    lines.append("")
    lines.append(
        dataframe_to_markdown(
            dimension_coverage_df
        )
    )

    lines.append("")
    lines.append("## 13. Monthly Coverage")
    lines.append("")
    lines.append(
        dataframe_to_markdown(
            monthly_coverage_df
        )
    )
    lines.append("")
    lines.append(
        "Months with `row_count` equal to 0 are missing from the historical data."
    )

    return "\n".join(lines)



def main():
    df = load_data(DATA_PATH)

    # These assertions protect only against an unusable source. Data-quality
    # issues such as null values are measured in the report instead of failing.
    assert len(df) > 0, "Dataset contains no rows."
    assert len(df.columns) > 0, "Dataset contains no columns."

    df = normalize_date_for_profiling(
        df
    )

    schema_df = profile_schema(df)

    null_df = profile_nulls(df)

    duplicates = profile_duplicates(df)

    time_profile = profile_time_range(df)

    dimension_columns = [
        "Country",
        "Product",
        "Segment",
        "Discount Band",
    ]

    dimensions = {
        column: profile_dimensions(
            df,
            column,
        )
        for column in dimension_columns
    }

    numeric_df = profile_numeric_columns(
        df
    )

    negative_df = profile_negative_values(
        df
    )

    discount_band_df = profile_discount_band(
        df
    )

    discount_relationship_df = profile_discount_relationship(
        df
    )

    dimension_coverage_df = profile_dimension_coverage(
        df
    )

    monthly_coverage_df = profile_monthly_coverage(
        df
    )

    grain_result = check_candidate_grain(
        df,
        [
            "Date",
            "Country",
            "Segment",
            "Product",
            "Discount Band",
        ],
    )

    sales_validation = (
        validate_sales_formula(df)
    )

    profit_validation = (
        validate_profit_formula(df)
    )

    gross_sales_validation = (
        validate_gross_sales_formula(df)
    )

    report = generate_report(
        df=df,
        schema_df=schema_df,
        null_df=null_df,
        numeric_df=numeric_df,
        negative_df=negative_df,
        dimensions=dimensions,
        duplicates=duplicates,
        time_profile=time_profile,
        grain_result=grain_result,
        sales_validation=sales_validation,
        profit_validation=profit_validation,
        gross_sales_validation=gross_sales_validation,
        discount_band_df=discount_band_df,
        discount_relationship_df=discount_relationship_df,
        dimension_coverage_df=dimension_coverage_df,
        monthly_coverage_df=monthly_coverage_df,
    )

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_PATH.write_text(
        report,
        encoding="utf-8",
    )

    print(
        f"Profile report generated: "
        f"{REPORT_PATH}"
    )


if __name__ == "__main__":
    main()
