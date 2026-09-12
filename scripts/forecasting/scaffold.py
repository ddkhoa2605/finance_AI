"""Forecast scaffold construction and coverage checks."""

from __future__ import annotations

import pandas as pd


KEYS = ["period_date", "country", "product", "segment"]


def create_forecast_scaffold(
    actual_drivers: pd.DataFrame, base_year: int, forecast_year: int
) -> pd.DataFrame:
    base = actual_drivers.loc[
        (actual_drivers["version"] == "ACTUAL")
        & (actual_drivers["period_date"].dt.year == base_year),
        KEYS,
    ].copy()
    if base.empty:
        raise ValueError(f"No ACTUAL driver rows found for scaffold year {base_year}.")
    base["period_date"] = base["period_date"].map(
        lambda value: value.replace(year=forecast_year)
    )
    result = base.sort_values(KEYS).reset_index(drop=True)
    if result.duplicated(KEYS).any():
        raise ValueError("Forecast scaffold grain is not unique.")
    return result


def validate_budget_coverage(scaffold: pd.DataFrame, budget: pd.DataFrame) -> None:
    budget_keys = budget.loc[
        (budget["version"] == "BUDGET")
        & (budget["account"] == "REVENUE")
        & budget["product"].notna()
        & budget["segment"].notna(),
        KEYS,
    ].drop_duplicates()
    left = scaffold.merge(budget_keys, on=KEYS, how="left", indicator=True)
    right = budget_keys.merge(scaffold, on=KEYS, how="left", indicator=True)
    missing_budget = left.loc[left["_merge"] != "both", KEYS]
    extra_budget = right.loc[right["_merge"] != "both", KEYS]
    if not missing_budget.empty or not extra_budget.empty:
        raise ValueError(
            "Forecast scaffold and Budget coverage differ: "
            f"missing_in_budget={len(missing_budget)}, extra_in_budget={len(extra_budget)}."
        )

