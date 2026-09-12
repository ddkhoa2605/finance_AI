"""Time-based one-step and recursive forecast evaluation."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

from forecasting.interface import ForecastEngine


KEYS = ["period_date", "country", "product", "segment"]
SERIES_KEYS = ["country", "product", "segment"]


def _metric_row(
    actual: pd.DataFrame,
    model: str,
    evaluation_type: str,
    fold: str,
    scope: str = "overall",
    country: str | None = None,
) -> dict:
    valid = actual.loc[actual["prediction"].notna()].copy()
    errors = valid["units"] - valid["prediction"]
    abs_errors = errors.abs()
    denominator = valid["units"].abs().sum()
    smape_denominator = valid["units"].abs() + valid["prediction"].abs()
    smape_terms = np.where(
        smape_denominator > 0,
        2 * abs_errors / smape_denominator,
        0.0,
    )
    by_series = valid.assign(abs_error=abs_errors).groupby(SERIES_KEYS).agg(
        absolute_error=("abs_error", "sum"), actual_units=("units", lambda x: x.abs().sum())
    )
    series_wape = (
        by_series.loc[by_series["actual_units"] > 0, "absolute_error"]
        / by_series.loc[by_series["actual_units"] > 0, "actual_units"]
    )
    return {
        "model": model,
        "evaluation_type": evaluation_type,
        "fold": fold,
        "scope": scope,
        "country": country,
        "n_targets": int(len(actual)),
        "n_predictions": int(len(valid)),
        "prediction_coverage": float(len(valid) / len(actual)) if len(actual) else 0.0,
        "mae": float(abs_errors.mean()),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "wape": float(abs_errors.sum() / denominator) if denominator else 0.0,
        "smape": float(np.mean(smape_terms)),
        "macro_wape": float(series_wape.mean()) if len(series_wape) else 0.0,
        "median_series_wape": float(series_wape.median()) if len(series_wape) else 0.0,
    }


def _scored_batch(
    model: ForecastEngine,
    history: pd.DataFrame,
    actual_month: pd.DataFrame,
) -> pd.DataFrame:
    actual = actual_month[KEYS + ["units"]].sort_values(KEYS).reset_index(drop=True)
    scaffold = actual[KEYS].copy()
    actual["prediction"] = model.predict(scaffold, history).to_numpy()
    return actual


def evaluate_models(
    engine_factories: dict[str, Callable[[], ForecastEngine]],
    actual_history: pd.DataFrame,
    validation_months: list[pd.Timestamp],
) -> tuple[pd.DataFrame, dict[str, dict]]:
    records: list[dict] = []
    prediction_sets: dict[str, dict] = {}
    ordered_months = [pd.Timestamp(month) for month in validation_months]
    recursive_cutoff = ordered_months[0] - pd.DateOffset(months=1)

    for name, factory in engine_factories.items():
        one_step_batches = []
        for month in ordered_months:
            cutoff = month - pd.DateOffset(months=1)
            model = factory().fit(actual_history, cutoff)
            target = actual_history.loc[actual_history["period_date"] == month]
            scored = _scored_batch(model, actual_history.loc[actual_history["period_date"] <= cutoff], target)
            one_step_batches.append(scored)
            records.append(_metric_row(scored, name, "one_step", month.strftime("%Y-%m")))
        one_step_all = pd.concat(one_step_batches, ignore_index=True)
        records.append(_metric_row(one_step_all, name, "one_step", "ALL"))

        model = factory().fit(actual_history, recursive_cutoff)
        recursive_history = actual_history.loc[
            actual_history["period_date"] <= recursive_cutoff,
            KEYS + ["units"],
        ].copy()
        recursive_batches = []
        for month in ordered_months:
            target = actual_history.loc[actual_history["period_date"] == month]
            scored = _scored_batch(model, recursive_history, target)
            recursive_batches.append(scored)
            records.append(_metric_row(scored, name, "recursive", month.strftime("%Y-%m")))
            appended = scored[KEYS].copy()
            appended["units"] = scored["prediction"]
            recursive_history = pd.concat([recursive_history, appended], ignore_index=True)

        recursive_all = pd.concat(recursive_batches, ignore_index=True)
        records.append(_metric_row(recursive_all, name, "recursive", "ALL"))
        for country, country_rows in recursive_all.groupby("country"):
            records.append(
                _metric_row(
                    country_rows,
                    name,
                    "recursive",
                    "ALL",
                    scope="country",
                    country=str(country),
                )
            )
        prediction_sets[name] = {
            "one_step": one_step_all,
            "recursive": recursive_all,
        }

    evaluation = pd.DataFrame(records)
    if (evaluation["prediction_coverage"] != 1.0).any():
        raise ValueError("A forecast candidate failed the 100% prediction coverage rule.")
    metric_columns = ["mae", "rmse", "wape", "smape", "macro_wape", "median_series_wape"]
    if not np.isfinite(evaluation[metric_columns].to_numpy()).all():
        raise ValueError("Model evaluation contains a non-finite metric.")
    return evaluation, prediction_sets


def select_champion(evaluation: pd.DataFrame, simplicity_tolerance: float) -> tuple[str, list[dict]]:
    overall = evaluation.loc[
        (evaluation["evaluation_type"] == "recursive")
        & (evaluation["fold"] == "ALL")
        & (evaluation["scope"] == "overall")
    ].set_index("model")
    order = ["seasonal_naive", "ridge", "xgboost"]
    if set(order).difference(overall.index):
        raise ValueError("Champion selection is missing a candidate model.")
    champion = order[0]
    decisions = []
    for candidate in order[1:]:
        incumbent_wape = float(overall.loc[champion, "wape"])
        candidate_wape = float(overall.loc[candidate, "wape"])
        improvement = incumbent_wape - candidate_wape
        replace = improvement >= simplicity_tolerance
        decisions.append(
            {
                "incumbent": champion,
                "candidate": candidate,
                "recursive_wape_improvement": improvement,
                "required_improvement": simplicity_tolerance,
                "candidate_selected": replace,
            }
        )
        if replace:
            champion = candidate
    return champion, decisions

