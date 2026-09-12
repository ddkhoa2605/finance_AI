"""Generic deterministic driver and OPEX event injection."""

from __future__ import annotations

import numpy as np
import pandas as pd

from anomalies.interface import (
    DRIVER_EVENT_TARGETS,
    DRIVER_KEYS,
    SUPPORTED_EVENT_TYPES,
    SUPPORTED_OPERATIONS,
)
from calculation.finance import CANONICAL_COLUMNS


def build_event_mask(df: pd.DataFrame, event: dict, opex: bool = False) -> pd.Series:
    start = pd.Timestamp(event["period_start"])
    end = pd.Timestamp(event["period_end"])
    mask = df["period_date"].between(start, end)
    for dimension in ["country", "product", "segment"]:
        value = event.get(dimension)
        if value is not None:
            if dimension not in df.columns:
                raise ValueError(f"Event {event['event_id']} targets unavailable dimension {dimension}.")
            mask &= df[dimension] == value
    if opex and event.get("department") is not None:
        mask &= df["department"] == event["department"]
    return mask


def validate_event_config(events: list[dict]) -> None:
    if not events:
        raise ValueError("anomalies.yaml must define at least one event.")
    event_ids = [event.get("event_id") for event in events]
    if any(not event_id for event_id in event_ids) or len(event_ids) != len(set(event_ids)):
        raise ValueError("Event IDs must be non-empty and unique.")
    for event in events:
        event_type = event.get("event_type")
        operation = event.get("operation")
        if event_type not in SUPPORTED_EVENT_TYPES:
            raise ValueError(f"Unsupported event type: {event_type}")
        if operation not in SUPPORTED_OPERATIONS:
            raise ValueError(f"Unsupported event operation: {operation}")
        if pd.Timestamp(event["period_start"]) > pd.Timestamp(event["period_end"]):
            raise ValueError(f"Event {event['event_id']} has an invalid period.")
        if not isinstance(event.get("expected_direction"), dict) or not event["expected_direction"]:
            raise ValueError(f"Event {event['event_id']} must define expected directions.")
        value = float(event["value"])
        if event_type in {"volume", "unit_cogs", "opex"}:
            if operation != "multiply" or value < 0:
                raise ValueError(f"Event {event['event_id']} requires a non-negative multiplier.")
        if event_type == "discount_rate" and operation != "add":
            raise ValueError("Discount-rate events must use additive percentage points.")


def validate_no_direct_overlap(drivers: pd.DataFrame, events: list[dict]) -> None:
    matched_keys: dict[tuple, str] = {}
    for event in events:
        if event["event_type"] == "opex":
            continue
        mask = build_event_mask(drivers, event)
        for key in drivers.loc[mask, DRIVER_KEYS].itertuples(index=False, name=None):
            if key in matched_keys:
                raise ValueError(
                    f"Events {matched_keys[key]} and {event['event_id']} overlap at driver grain {key}."
                )
            matched_keys[key] = event["event_id"]


def _apply_operation(values: pd.Series, operation: str, value: float) -> pd.Series:
    if operation == "multiply":
        return values * value
    if operation == "add":
        return values + value
    raise ValueError(f"Unsupported operation: {operation}")


def apply_driver_events(
    base_drivers: pd.DataFrame, events: list[dict]
) -> tuple[pd.DataFrame, dict[str, int]]:
    result = base_drivers.copy()
    matched_rows: dict[str, int] = {}
    for event in events:
        if event["event_type"] == "opex":
            continue
        target = DRIVER_EVENT_TARGETS[event["event_type"]]
        if target not in result.columns:
            raise ValueError(f"Event target field does not exist: {target}")
        mask = build_event_mask(result, event)
        count = int(mask.sum())
        if count == 0:
            raise ValueError(f"Event {event['event_id']} matches zero driver rows.")
        result.loc[mask, target] = _apply_operation(
            result.loc[mask, target].astype(float),
            event["operation"],
            float(event["value"]),
        )
        matched_rows[event["event_id"]] = count
    if (result[["units", "unit_cogs"]] < 0).any().any():
        raise ValueError("Anomaly injection produced negative Units or Unit COGS.")
    if not result["discount_rate"].between(0, 1).all():
        raise ValueError("Anomaly injection produced Discount Rate outside [0, 1].")
    return result.sort_values(DRIVER_KEYS).reset_index(drop=True), matched_rows


def apply_opex_events(
    opex_artifacts: dict[str, pd.DataFrame],
    events: list[dict],
    source_name: str,
    ebitda_source: str,
) -> tuple[dict[str, pd.DataFrame], dict[str, int]]:
    result = {key: value.copy() for key, value in opex_artifacts.items()}
    department = result["department"].copy()
    matched_rows: dict[str, int] = {}
    for event in events:
        if event["event_type"] != "opex":
            continue
        mask = build_event_mask(department, event, opex=True)
        count = int(mask.sum())
        if count == 0:
            raise ValueError(f"Event {event['event_id']} matches zero department OPEX rows.")
        department.loc[mask, "amount"] = _apply_operation(
            department.loc[mask, "amount"].astype(float),
            event["operation"],
            float(event["value"]),
        )
        matched_rows[event["event_id"]] = count

    opex_total = (
        department.groupby(["period_date", "country", "version", "currency"], as_index=False)["amount"]
        .sum().sort_values(["period_date", "country"]).reset_index(drop=True)
    )
    opex_total["product"] = pd.NA
    opex_total["segment"] = pd.NA
    opex_total["department"] = pd.NA
    opex_total["account"] = "OPEX_TOTAL"
    opex_total["source"] = source_name
    opex_total = opex_total[CANONICAL_COLUMNS]

    gross_profit = result["gross_profit"]
    ebitda = gross_profit.merge(
        opex_total[["period_date", "country", "amount"]].rename(columns={"amount": "opex_total"}),
        on=["period_date", "country"],
        how="inner",
        validate="one_to_one",
    )
    if len(ebitda) != len(gross_profit) or len(ebitda) != len(opex_total):
        raise ValueError("OPEX event caused EBITDA coverage mismatch.")
    ebitda["amount"] = ebitda["gross_profit"] - ebitda["opex_total"]
    ebitda["product"] = pd.NA
    ebitda["segment"] = pd.NA
    ebitda["department"] = pd.NA
    ebitda["account"] = "EBITDA"
    ebitda["version"] = department["version"].iloc[0]
    ebitda["currency"] = department["currency"].iloc[0]
    ebitda["source"] = ebitda_source
    ebitda = ebitda[CANONICAL_COLUMNS]

    result["department"] = department.sort_values(
        ["period_date", "country", "department", "account"]
    ).reset_index(drop=True)
    result["opex_total"] = opex_total
    result["ebitda"] = ebitda
    result["output"] = pd.concat([department, opex_total, ebitda], ignore_index=True).sort_values(
        ["period_date", "country", "account", "department"], na_position="last"
    ).reset_index(drop=True)
    return result, matched_rows
