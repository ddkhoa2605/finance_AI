"""Common interface for Units forecasting candidates."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class ForecastEngine(ABC):
    name: str
    complexity_rank: int

    @abstractmethod
    def fit(self, history: pd.DataFrame, cutoff_date: pd.Timestamp) -> "ForecastEngine":
        """Fit only to observations on or before cutoff_date."""

    @abstractmethod
    def predict(self, scaffold: pd.DataFrame, history: pd.DataFrame) -> pd.Series:
        """Predict one complete month batch."""

    @abstractmethod
    def get_metadata(self) -> dict:
        """Return deterministic model metadata."""

