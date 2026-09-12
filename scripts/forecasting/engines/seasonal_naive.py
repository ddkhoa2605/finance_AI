"""Deterministic seasonal-naive Units baseline."""

from __future__ import annotations

import numpy as np
import pandas as pd

from forecasting.interface import ForecastEngine


SERIES_KEYS = ["country", "product", "segment"]


class SeasonalNaiveForecastEngine(ForecastEngine):
    name = "seasonal_naive"
    complexity_rank = 0

    def __init__(self) -> None:
        self.training_end: pd.Timestamp | None = None

    def fit(self, history: pd.DataFrame, cutoff_date: pd.Timestamp) -> "SeasonalNaiveForecastEngine":
        train = history.loc[history["period_date"] <= pd.Timestamp(cutoff_date)]
        if train.empty:
            raise ValueError("Seasonal Naive received an empty training set.")
        self.training_end = pd.Timestamp(cutoff_date)
        return self

    @staticmethod
    def _predict_one(history: pd.DataFrame, row) -> float:
        target_date = pd.Timestamp(row.period_date)
        past = history.loc[history["period_date"] < target_date]
        series = past.loc[
            (past["country"] == row.country)
            & (past["product"] == row.product)
            & (past["segment"] == row.segment)
        ].sort_values("period_date")
        prior_date = target_date - pd.DateOffset(years=1)
        prior = series.loc[series["period_date"] == prior_date, "units"]
        if not prior.empty:
            return float(prior.iloc[-1])
        if not series.empty:
            return float(series.iloc[-1]["units"])

        same_month = past.loc[past["period_date"] == prior_date]
        country_product = same_month.loc[
            (same_month["country"] == row.country)
            & (same_month["product"] == row.product),
            "units",
        ]
        if not country_product.empty:
            return float(country_product.median())
        product = same_month.loc[same_month["product"] == row.product, "units"]
        if not product.empty:
            return float(product.median())
        if not same_month.empty:
            return float(same_month["units"].median())
        if not past.empty:
            return float(past["units"].median())
        raise ValueError("Seasonal Naive has no historical fallback observation.")

    def predict(self, scaffold: pd.DataFrame, history: pd.DataFrame) -> pd.Series:
        predictions = [
            self._predict_one(history, row)
            for row in scaffold.itertuples(index=False)
        ]
        result = pd.Series(predictions, index=scaffold.index, dtype=float)
        if result.isna().any() or not np.isfinite(result).all():
            raise ValueError("Seasonal Naive produced invalid predictions.")
        return result.clip(lower=0)

    def get_metadata(self) -> dict:
        return {
            "name": self.name,
            "complexity_rank": self.complexity_rank,
            "training_end": self.training_end.strftime("%Y-%m-%d") if self.training_end is not None else None,
            "fallback_order": [
                "same_series_same_month_last_year",
                "same_series_latest_observation",
                "country_product_same_month_last_year_median",
                "product_same_month_last_year_median",
                "global_same_month_last_year_median",
                "global_historical_median",
            ],
        }

