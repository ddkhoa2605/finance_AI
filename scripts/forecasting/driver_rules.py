"""Deterministic rules for ASP, Unit COGS, and Discount Rate."""

from __future__ import annotations

import numpy as np
import pandas as pd


KEYS = ["country", "product", "segment"]


def _weighted_recent(values: pd.Series, weights: list[float]) -> float:
    values = values.dropna().astype(float).tail(len(weights))
    if values.empty:
        return np.nan
    selected_weights = np.asarray(weights[-len(values):], dtype=float)
    selected_weights = selected_weights / selected_weights.sum()
    return float(np.dot(values.to_numpy(), selected_weights))


def _aggregate_ratio(history: pd.DataFrame, metric: str) -> float:
    if history.empty:
        return np.nan
    if metric == "average_sale_price":
        denominator = history["units"].sum()
        return float((history["units"] * history["average_sale_price"]).sum() / denominator) if denominator else np.nan
    if metric == "unit_cogs":
        denominator = history["units"].sum()
        return float((history["units"] * history["unit_cogs"]).sum() / denominator) if denominator else np.nan
    if metric == "discount_rate":
        gross_sales = history["units"] * history["average_sale_price"]
        denominator = gross_sales.sum()
        return float((gross_sales * history["discount_rate"]).sum() / denominator) if denominator else np.nan
    raise ValueError(f"Unsupported driver rule metric: {metric}")


def _forecast_metric(
    history: pd.DataFrame,
    row,
    metric: str,
    weights: list[float],
    factor: float,
) -> tuple[float, str]:
    target_date = pd.Timestamp(row.period_date)
    prior_date = target_date - pd.DateOffset(years=1)
    exact = history.loc[
        (history["period_date"] == prior_date)
        & (history["country"] == row.country)
        & (history["product"] == row.product)
        & (history["segment"] == row.segment),
        metric,
    ]
    if not exact.empty and pd.notna(exact.iloc[-1]):
        return float(exact.iloc[-1]) * factor, "same_grain_same_month_previous_year"

    series = history.loc[
        (history["period_date"] < target_date)
        & (history["country"] == row.country)
        & (history["product"] == row.product)
        & (history["segment"] == row.segment)
    ].sort_values("period_date")
    recent = _weighted_recent(series[metric], weights)
    if pd.notna(recent):
        return recent * factor, "same_grain_weighted_trailing_three"

    levels = [
        ({"country": row.country, "product": row.product}, "country_product"),
        ({"product": row.product}, "product"),
        ({}, "global"),
    ]
    for filters, label in levels:
        subset = history.loc[history["period_date"] < target_date]
        for column, value in filters.items():
            subset = subset.loc[subset[column] == value]
        if subset.empty:
            continue
        recent_dates = sorted(subset["period_date"].unique())[-3:]
        value = _aggregate_ratio(subset.loc[subset["period_date"].isin(recent_dates)], metric)
        if pd.notna(value):
            return value * factor, label
    raise ValueError(f"No historical fallback for {metric}.")


def apply_driver_rules(
    history: pd.DataFrame,
    scaffold: pd.DataFrame,
    config: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    weights = [float(value) for value in config["trailing_weights"]]
    rows = []
    usage = []
    settings = {
        "average_sale_price": float(config["pricing_factor"]),
        "unit_cogs": float(config["cost_factor"]),
        "discount_rate": 1.0,
    }
    for row in scaffold.itertuples(index=False):
        result = {column: getattr(row, column) for column in ["period_date"] + KEYS}
        for metric, factor in settings.items():
            value, fallback = _forecast_metric(history, row, metric, weights, factor)
            result[metric] = value
            usage.append({"metric": metric, "fallback_level": fallback})
        result["discount_rate"] = float(np.clip(result["discount_rate"], 0, 1))
        rows.append(result)
    usage_frame = (
        pd.DataFrame(usage).groupby(["metric", "fallback_level"], as_index=False)
        .size().rename(columns={"size": "row_count"})
    )
    return pd.DataFrame(rows), usage_frame

