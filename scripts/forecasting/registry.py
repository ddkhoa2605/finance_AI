"""Deterministic model artifact and lineage registry."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import pandas as pd
import sklearn
import xgboost


def combined_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: str(item)):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def save_registry(
    directory: Path,
    models: dict,
    champion: str,
    evaluation: pd.DataFrame,
    decisions: list[dict],
    config: dict,
    prediction_input_hash: str,
    evaluation_context_hash: str,
) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    for name, model in models.items():
        artifact = (
            model.pipeline
            if getattr(model, "pipeline", None) is not None
            else {"name": name, "metadata": model.get_metadata()}
        )
        joblib.dump(artifact, directory / f"{name}.joblib")
        if name == "xgboost":
            model.save_native_model(directory / "xgboost.json")

    overall = evaluation.loc[
        (evaluation["fold"] == "ALL") & (evaluation["scope"] == "overall")
    ]
    metrics = {}
    for row in overall.itertuples(index=False):
        metrics.setdefault(row.model, {})[row.evaluation_type] = {
            key: float(getattr(row, key))
            for key in [
                "mae", "rmse", "wape", "smape", "macro_wape",
                "median_series_wape", "prediction_coverage",
            ]
        }
    registry = {
        "champion": champion,
        "selection_metric": "recursive_wape",
        "secondary_metric": "one_step_wape",
        "simplicity_tolerance": float(config["champion"]["simplicity_tolerance"]),
        "training_end": str(config["training_end"]),
        "forecast_year": int(config["forecast_year"]),
        "final_refit": True,
        "library_versions": {
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "xgboost": xgboost.__version__,
            "joblib": joblib.__version__,
        },
        "models": {name: model.get_metadata() for name, model in models.items()},
        "metrics": metrics,
        "selection_decisions": decisions,
        "prediction_input_hash": prediction_input_hash,
        "evaluation_context_hash": evaluation_context_hash,
        "budget_role": "coverage_validation_and_comparison_only",
    }
    (directory / "model_registry.json").write_text(
        json.dumps(registry, indent=2, sort_keys=True), encoding="utf-8"
    )
    return registry
