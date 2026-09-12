"""Global Ridge Units forecasting model."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from forecasting.features import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    build_feature_frame,
    build_training_matrix,
)
from forecasting.interface import ForecastEngine


class RidgeForecastEngine(ForecastEngine):
    name = "ridge"
    complexity_rank = 1

    def __init__(self, alpha: float = 10.0) -> None:
        self.alpha = float(alpha)
        self.training_end: pd.Timestamp | None = None
        self.pipeline: Pipeline | None = None

    def fit(self, history: pd.DataFrame, cutoff_date: pd.Timestamp) -> "RidgeForecastEngine":
        x_train, y_train = build_training_matrix(history, cutoff_date)
        preprocessor = ColumnTransformer(
            transformers=[
                (
                    "categorical",
                    OneHotEncoder(handle_unknown="ignore"),
                    CATEGORICAL_FEATURES,
                ),
                (
                    "numeric",
                    Pipeline(
                        [
                            (
                                "imputer",
                                SimpleImputer(
                                    strategy="median",
                                    add_indicator=True,
                                    keep_empty_features=True,
                                ),
                            ),
                            ("scaler", StandardScaler()),
                        ]
                    ),
                    NUMERIC_FEATURES,
                ),
            ]
        )
        self.pipeline = Pipeline(
            [("preprocessor", preprocessor), ("model", Ridge(alpha=self.alpha))]
        )
        self.pipeline.fit(x_train, np.log1p(y_train))
        self.training_end = pd.Timestamp(cutoff_date)
        return self

    def predict(self, scaffold: pd.DataFrame, history: pd.DataFrame) -> pd.Series:
        if self.pipeline is None:
            raise ValueError("Ridge model must be fit before prediction.")
        features = build_feature_frame(history, scaffold)[FEATURE_COLUMNS]
        values = np.expm1(self.pipeline.predict(features))
        result = pd.Series(values, index=scaffold.index, dtype=float).clip(lower=0)
        if result.isna().any() or not np.isfinite(result).all():
            raise ValueError("Ridge produced invalid predictions.")
        return result

    def get_metadata(self) -> dict:
        return {
            "name": self.name,
            "complexity_rank": self.complexity_rank,
            "training_end": self.training_end.strftime("%Y-%m-%d") if self.training_end is not None else None,
            "parameters": {"alpha": self.alpha, "target_transform": "log1p"},
            "features": FEATURE_COLUMNS,
        }
