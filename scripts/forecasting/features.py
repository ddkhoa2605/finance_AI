"""Leakage-safe Units feature construction."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


SERIES_KEYS = ["country", "product", "segment"]
CATEGORICAL_FEATURES = SERIES_KEYS
NUMERIC_FEATURES = [
    "month",
    "quarter",
    "month_sin",
    "month_cos",
    "time_index",
    "units_obs_1",
    "units_obs_2",
    "units_obs_3",
    "units_rolling_mean_3",
    "units_rolling_std_3",
    "months_since_last_observation",
    "country_product_recent_median",
    "product_recent_median",
    "units_same_month_last_year",
    "units_lag_12_missing",
]
FEATURE_COLUMNS = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def _month_distance(later: pd.Timestamp, earlier: pd.Timestamp) -> int:
    return (later.year - earlier.year) * 12 + later.month - earlier.month


def _recent_period_median(
    history: pd.DataFrame,
    target_date: pd.Timestamp,
    filters: dict[str, str],
    periods: int = 3,
) -> float:
    subset = history.loc[history["period_date"] < target_date]
    for column, value in filters.items():
        subset = subset.loc[subset[column] == value]
    if subset.empty:
        return np.nan
    recent_dates = sorted(subset["period_date"].unique())[-periods:]
    return float(subset.loc[subset["period_date"].isin(recent_dates), "units"].median())


def build_feature_frame(
    history: pd.DataFrame,
    targets: pd.DataFrame,
    origin_date: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Build features using observations strictly before every target month."""
    required_history = set(SERIES_KEYS + ["period_date", "units"])
    required_targets = set(SERIES_KEYS + ["period_date"])
    if required_history.difference(history.columns):
        raise ValueError("Units history does not satisfy the feature contract.")
    if required_targets.difference(targets.columns):
        raise ValueError("Prediction scaffold does not satisfy the feature contract.")

    history = history.copy()
    targets = targets.copy()
    history["period_date"] = pd.to_datetime(history["period_date"])
    targets["period_date"] = pd.to_datetime(targets["period_date"])
    if origin_date is None:
        origin_date = min(history["period_date"].min(), targets["period_date"].min())
    origin_date = pd.Timestamp(origin_date)

    rows = []
    for target in targets.sort_values(["period_date"] + SERIES_KEYS).itertuples(index=False):
        target_date = pd.Timestamp(target.period_date)
        past = history.loc[history["period_date"] < target_date]
        series = past.loc[
            (past["country"] == target.country)
            & (past["product"] == target.product)
            & (past["segment"] == target.segment)
        ].sort_values("period_date")
        recent = series.tail(3)
        observations = list(recent["units"].astype(float))[::-1]
        observations += [np.nan] * (3 - len(observations))
        last_date = series["period_date"].max() if not series.empty else pd.NaT

        prior_year_date = target_date - pd.DateOffset(years=1)
        prior_year = series.loc[series["period_date"] == prior_year_date, "units"]
        lag_12 = float(prior_year.iloc[-1]) if not prior_year.empty else np.nan
        month = target_date.month
        rows.append(
            {
                "period_date": target_date,
                "country": target.country,
                "product": target.product,
                "segment": target.segment,
                "month": month,
                "quarter": int((month - 1) // 3 + 1),
                "month_sin": math.sin(2 * math.pi * month / 12),
                "month_cos": math.cos(2 * math.pi * month / 12),
                "time_index": _month_distance(target_date, origin_date),
                "units_obs_1": observations[0],
                "units_obs_2": observations[1],
                "units_obs_3": observations[2],
                "units_rolling_mean_3": float(recent["units"].mean()) if not recent.empty else np.nan,
                "units_rolling_std_3": float(recent["units"].std(ddof=0)) if not recent.empty else np.nan,
                "months_since_last_observation": (
                    _month_distance(target_date, pd.Timestamp(last_date))
                    if pd.notna(last_date) else np.nan
                ),
                "country_product_recent_median": _recent_period_median(
                    past,
                    target_date,
                    {"country": target.country, "product": target.product},
                ),
                "product_recent_median": _recent_period_median(
                    past, target_date, {"product": target.product}
                ),
                "units_same_month_last_year": lag_12,
                "units_lag_12_missing": int(pd.isna(lag_12)),
            }
        )
    result = pd.DataFrame(rows)
    if len(result) != len(targets):
        raise ValueError("Feature builder changed target row coverage.")
    return result


def build_training_matrix(history: pd.DataFrame, cutoff_date: pd.Timestamp) -> tuple[pd.DataFrame, pd.Series]:
    train = history.loc[history["period_date"] <= pd.Timestamp(cutoff_date)].copy()
    train = train.sort_values(["period_date"] + SERIES_KEYS).reset_index(drop=True)
    features = build_feature_frame(train, train[SERIES_KEYS + ["period_date"]])
    return features[FEATURE_COLUMNS], train["units"].astype(float).reset_index(drop=True)

