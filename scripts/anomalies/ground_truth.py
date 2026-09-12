"""Event impact measurement and Phase 12 ground-truth generation."""

from __future__ import annotations

import pandas as pd

from anomalies.injector import build_event_mask
from anomalies.validators import observed_direction


DRIVER_METRICS = {"units", "average_sale_price", "unit_cogs", "discount_rate"}
ACCOUNT_MAPPING = {
    "gross_sales": "GROSS_SALES",
    "discount": "DISCOUNT",
    "revenue": "REVENUE",
    "cogs": "COGS",
    "gross_profit": "GROSS_PROFIT",
    "opex_marketing": "OPEX_MARKETING",
    "opex_total": "OPEX_TOTAL",
    "ebitda": "EBITDA",
}


def _driver_metric_value(drivers: pd.DataFrame, event: dict, metric: str) -> float:
    selected = drivers.loc[build_event_mask(drivers, event)]
    if selected.empty:
        raise ValueError(f"Cannot measure {metric}; event {event['event_id']} has no driver rows.")
    if metric == "units":
        return float(selected["units"].sum())
    if metric in {"average_sale_price", "unit_cogs"}:
        denominator = selected["units"].sum()
        return float((selected["units"] * selected[metric]).sum() / denominator)
    if metric == "discount_rate":
        gross_sales = selected["units"] * selected["average_sale_price"]
        return float((gross_sales * selected["discount_rate"]).sum() / gross_sales.sum())
    raise ValueError(f"Unsupported driver metric: {metric}")


def _finance_metric_value(finance: pd.DataFrame, event: dict, metric: str) -> float:
    account = ACCOUNT_MAPPING[metric]
    selected = finance.loc[
        finance["period_date"].between(
            pd.Timestamp(event["period_start"]), pd.Timestamp(event["period_end"])
        )
        & (finance["account"] == account)
    ]
    if event.get("country") is not None:
        selected = selected.loc[selected["country"] == event["country"]]
    if account in {"GROSS_SALES", "DISCOUNT", "REVENUE", "COGS", "GROSS_PROFIT"}:
        if event.get("product") is not None:
            selected = selected.loc[selected["product"] == event["product"]]
        if event.get("segment") is not None:
            selected = selected.loc[selected["segment"] == event["segment"]]
    if metric == "opex_marketing" and event.get("department") is not None:
        selected = selected.loc[selected["department"] == event["department"]]
    if selected.empty:
        raise ValueError(f"Cannot measure {metric}; event {event['event_id']} has no finance rows.")
    return float(selected["amount"].sum())


def metric_value(bundle: dict, event: dict, metric: str) -> float:
    if metric in DRIVER_METRICS:
        return _driver_metric_value(bundle["drivers"], event, metric)
    return _finance_metric_value(bundle["finance"], event, metric)


def build_event_impacts(
    events: list[dict],
    baseline: dict,
    isolated_scenarios: dict[str, dict],
    matched_rows: dict[str, int],
    tolerance: float,
) -> pd.DataFrame:
    rows = []
    for event in events:
        scenario = isolated_scenarios[event["event_id"]]
        for metric, expected in event["expected_direction"].items():
            before = metric_value(baseline, event, metric)
            after = metric_value(scenario, event, metric)
            delta = after - before
            actual = observed_direction(delta, tolerance)
            rows.append(
                {
                    "event_id": event["event_id"],
                    "event_type": event["event_type"],
                    "metric": metric,
                    "period_start": pd.Timestamp(event["period_start"]).strftime("%Y-%m-%d"),
                    "period_end": pd.Timestamp(event["period_end"]).strftime("%Y-%m-%d"),
                    "country": event.get("country"),
                    "product": event.get("product"),
                    "segment": event.get("segment"),
                    "department": event.get("department"),
                    "before": before,
                    "after": after,
                    "delta": delta,
                    "delta_pct": delta / abs(before) if before != 0 else None,
                    "expected_direction": expected,
                    "actual_direction": actual,
                    "direction_pass": actual == expected,
                    "matched_rows": int(matched_rows[event["event_id"]]),
                }
            )
    return pd.DataFrame(rows).sort_values(["event_id", "metric"]).reset_index(drop=True)


def build_events_ground_truth(
    events: list[dict],
    impacts: pd.DataFrame,
    matched_rows: dict[str, int],
    baseline_hashes: dict,
    benchmark_version: str,
) -> dict:
    output_events = []
    for event in events:
        event_impacts = impacts.loc[impacts["event_id"] == event["event_id"]]
        filters = {
            key: event[key]
            for key in ["country", "product", "segment", "department"]
            if event.get(key) is not None
        }
        output_events.append(
            {
                "event_id": event["event_id"],
                "event_type": event["event_type"],
                "period_start": pd.Timestamp(event["period_start"]).strftime("%Y-%m-%d"),
                "period_end": pd.Timestamp(event["period_end"]).strftime("%Y-%m-%d"),
                "filters": filters,
                "operation": {"type": event["operation"], "value": float(event["value"])},
                "root_cause": event["root_cause"],
                "description": event["description"],
                "matched_rows": int(matched_rows[event["event_id"]]),
                "expected_affected_metrics": event_impacts.loc[
                    event_impacts["expected_direction"] != "unchanged", "metric"
                ].tolist(),
                "expected_unaffected_primary_metrics": event_impacts.loc[
                    event_impacts["expected_direction"] == "unchanged", "metric"
                ].tolist(),
                "expected_direction": event["expected_direction"],
                "observed_impacts": [
                    {
                        "metric": row.metric,
                        "before": float(row.before),
                        "after": float(row.after),
                        "delta": float(row.delta),
                        "delta_pct": None if pd.isna(row.delta_pct) else float(row.delta_pct),
                        "direction": row.actual_direction,
                    }
                    for row in event_impacts.itertuples(index=False)
                ],
            }
        )
    return {
        "benchmark_name": "controlled_anomaly_benchmark_v1",
        "benchmark_version": benchmark_version,
        "baseline_hashes": baseline_hashes,
        "events_are_cumulative": True,
        "direct_event_scopes_overlap": False,
        "attribution_method": "isolated_event_vs_baseline",
        "events": output_events,
    }
