"""Deterministic scenario lineage registry."""

from __future__ import annotations

import hashlib
import json

import pandas as pd


def canonical_hash(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def dataframe_hash(frame: pd.DataFrame) -> str:
    payload = frame.to_csv(index=False, lineterminator="\n").encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def build_registry(
    results: list[dict],
    engine_metadata: dict,
    config_hash: str,
    baseline_lineage: dict[str, dict],
) -> dict:
    scenarios = {}
    for result in results:
        request = result["request"]
        scenario_id = request["scenario_id"]
        if scenario_id in scenarios:
            raise ValueError(f"Duplicate scenario ID in registry: {scenario_id}")
        key_impacts = result["comparison"].loc[
            result["comparison"]["metric"].isin(
                ["REVENUE", "GROSS_PROFIT", "OPEX_TOTAL", "EBITDA"]
            ),
            ["metric", "impact", "impact_pct"],
        ]
        scenarios[scenario_id] = {
            "name": request["name"],
            "base_version": request["base_version"],
            "period": {
                "start": pd.Timestamp(request["period"]["start"]).strftime("%Y-%m-%d"),
                "end": pd.Timestamp(request["period"]["end"]).strftime("%Y-%m-%d"),
            },
            "filters": request["filters"],
            "levers": request["levers"],
            "expected_direction": request.get("expected_direction", {}),
            "request_hash": canonical_hash(request),
            "baseline_lineage": baseline_lineage[request["base_version"]],
            "matched_driver_rows": result["metadata"]["matched_driver_rows"],
            "matched_department_opex_rows": result["metadata"][
                "matched_department_opex_rows"
            ],
            "discount_rows_clipped": result["metadata"]["discount_rows_clipped"],
            "scenario_driver_rows": len(result["scenario_drivers"]),
            "scenario_finance_rows": len(result["scenario_finance"]),
            "driver_output_hash": dataframe_hash(result["scenario_drivers"]),
            "finance_output_hash": dataframe_hash(result["scenario_finance"]),
            "comparison_output_hash": dataframe_hash(result["comparison"]),
            "key_financial_impacts": {
                row.metric: {
                    "amount": float(row.impact),
                    "percent_of_absolute_baseline": (
                        None if pd.isna(row.impact_pct) else float(row.impact_pct)
                    ),
                }
                for row in key_impacts.itertuples(index=False)
            },
            "validation_status": "passed",
        }
    return {
        "registry_version": "scenario_registry_v1",
        "engine": engine_metadata,
        "scenario_config_hash": config_hash,
        "scenarios": scenarios,
    }
