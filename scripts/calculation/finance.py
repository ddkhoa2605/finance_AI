"""Canonical driver-to-finance reconstruction."""

from __future__ import annotations

import numpy as np
import pandas as pd


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
OPERATING_ACCOUNTS = [
    "GROSS_SALES",
    "DISCOUNT",
    "REVENUE",
    "COGS",
    "GROSS_PROFIT",
]
OPERATING_GRAIN = [
    "period_date",
    "country",
    "product",
    "segment",
    "account",
    "version",
]


def reconstruct_operating_finance(
    drivers: pd.DataFrame,
    version: str,
    source: str,
    currency: str = "USD",
) -> pd.DataFrame:
    """Build the five canonical operating accounts from forecast drivers."""
    required = {
        "period_date",
        "country",
        "product",
        "segment",
        "units",
        "average_sale_price",
        "unit_cogs",
        "discount_rate",
    }
    missing = sorted(required.difference(drivers.columns))
    if missing:
        raise ValueError(f"Driver frame is missing columns: {missing}")

    detail = drivers.copy()
    detail["GROSS_SALES"] = detail["units"] * detail["average_sale_price"]
    detail["DISCOUNT"] = detail["GROSS_SALES"] * detail["discount_rate"]
    detail["REVENUE"] = detail["GROSS_SALES"] - detail["DISCOUNT"]
    detail["COGS"] = detail["units"] * detail["unit_cogs"]
    detail["GROSS_PROFIT"] = detail["REVENUE"] - detail["COGS"]

    id_columns = ["period_date", "country", "product", "segment"]
    result = detail.melt(
        id_vars=id_columns,
        value_vars=OPERATING_ACCOUNTS,
        var_name="account",
        value_name="amount",
    )
    result["department"] = pd.NA
    result["version"] = version
    result["currency"] = currency
    result["source"] = source
    return result[CANONICAL_COLUMNS].sort_values(
        id_columns + ["account"]
    ).reset_index(drop=True)


def validate_operating_finance(
    finance: pd.DataFrame, tolerance: float = 0.01
) -> None:
    """Validate canonical grain and operating-account equations."""
    if finance.empty:
        raise ValueError("Operating finance output is empty.")
    if finance.duplicated(OPERATING_GRAIN).any():
        raise ValueError("Operating finance canonical grain is not unique.")
    keys = ["period_date", "country", "product", "segment", "version"]
    wide = finance.pivot(index=keys, columns="account", values="amount")
    if set(OPERATING_ACCOUNTS).difference(wide.columns):
        raise ValueError("Operating finance is missing one or more required accounts.")
    if not np.allclose(
        wide["GROSS_SALES"] - wide["DISCOUNT"],
        wide["REVENUE"],
        atol=tolerance,
    ):
        raise ValueError("Revenue reconciliation failed.")
    if not np.allclose(
        wide["REVENUE"] - wide["COGS"],
        wide["GROSS_PROFIT"],
        atol=tolerance,
    ):
        raise ValueError("Gross Profit reconciliation failed.")

