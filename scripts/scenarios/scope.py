"""Scenario scope parsing and row selection."""

from __future__ import annotations

import pandas as pd

from scenarios.interface import ScenarioValidationError


FILTER_DIMENSIONS = ["country", "product", "segment"]


def normalize_filter(value) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and value and all(isinstance(item, str) for item in value):
        return value
    raise ScenarioValidationError("Scenario filters must be null, a string, or a non-empty string list.")


def build_scope_mask(drivers: pd.DataFrame, request: dict) -> pd.Series:
    start = pd.Timestamp(request["period"]["start"])
    end = pd.Timestamp(request["period"]["end"])
    mask = drivers["period_date"].between(start, end)
    filters = request.get("filters", {})
    for dimension in FILTER_DIMENSIONS:
        values = normalize_filter(filters.get(dimension))
        if values is not None:
            mask &= drivers[dimension].isin(values)
    return mask


def describe_scope(request: dict) -> str:
    filters = request.get("filters", {})
    parts = [
        f"period={pd.Timestamp(request['period']['start']).strftime('%Y-%m-%d')}.."
        f"{pd.Timestamp(request['period']['end']).strftime('%Y-%m-%d')}"
    ]
    for dimension in FILTER_DIMENSIONS:
        values = normalize_filter(filters.get(dimension))
        parts.append(f"{dimension}={'ALL' if values is None else '|'.join(values)}")
    return ", ".join(parts)
