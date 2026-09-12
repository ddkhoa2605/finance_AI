"""Explainable Scenario-versus-Baseline comparisons."""

from __future__ import annotations

import pandas as pd

from scenarios.scope import build_scope_mask, describe_scope


DRIVER_METRICS = ["units", "average_sale_price", "unit_cogs", "discount_rate"]


def _driver_value(frame: pd.DataFrame, mask: pd.Series, metric: str) -> float:
    selected = frame.loc[mask]
    if metric == "units":
        return float(selected["units"].sum())
    if metric in {"average_sale_price", "unit_cogs"}:
        units = selected["units"].sum()
        return float((selected[metric] * selected["units"]).sum() / units)
    gross_sales = selected["units"] * selected["average_sale_price"]
    return float((selected["discount_rate"] * gross_sales).sum() / gross_sales.sum())


def build_comparison(result: dict) -> pd.DataFrame:
    request = result["request"]
    baseline_drivers = result["baseline_drivers"]
    scenario_drivers = result["scenario_drivers"]
    baseline_mask = build_scope_mask(baseline_drivers, request)
    scenario_mask = build_scope_mask(scenario_drivers, request)
    rows = []

    for metric in DRIVER_METRICS:
        before = _driver_value(baseline_drivers, baseline_mask, metric)
        after = _driver_value(scenario_drivers, scenario_mask, metric)
        rows.append(
            {
                "metric_type": "driver",
                "metric": metric,
                "comparison_scope": "direct_driver_scope",
                "unit": "rate" if metric == "discount_rate" else ("units" if metric == "units" else "USD_per_unit"),
                "baseline_value": before,
                "scenario_value": after,
            }
        )

    start = pd.Timestamp(request["period"]["start"])
    end = pd.Timestamp(request["period"]["end"])
    baseline_finance = result["baseline_finance"]
    scenario_finance = result["scenario_finance"]
    for account in sorted(scenario_finance["account"].unique()):
        before = float(
            baseline_finance.loc[
                baseline_finance["period_date"].between(start, end)
                & (baseline_finance["account"] == account),
                "amount",
            ].sum()
        )
        after = float(
            scenario_finance.loc[
                scenario_finance["period_date"].between(start, end)
                & (scenario_finance["account"] == account),
                "amount",
            ].sum()
        )
        rows.append(
            {
                "metric_type": "finance",
                "metric": account,
                "comparison_scope": "company_period",
                "unit": "USD",
                "baseline_value": before,
                "scenario_value": after,
            }
        )

    comparison = pd.DataFrame(rows)
    comparison["impact"] = comparison["scenario_value"] - comparison["baseline_value"]
    comparison["impact_pct"] = comparison.apply(
        lambda row: row["impact"] / abs(row["baseline_value"])
        if row["baseline_value"] != 0 else None,
        axis=1,
    )
    comparison.insert(0, "scenario_id", request["scenario_id"])
    comparison.insert(1, "scenario_name", request["name"])
    comparison.insert(2, "base_version", request["base_version"])
    comparison.insert(3, "period_start", start.strftime("%Y-%m-%d"))
    comparison.insert(4, "period_end", end.strftime("%Y-%m-%d"))
    comparison.insert(5, "scope", describe_scope(request))
    return comparison.sort_values(["metric_type", "metric"]).reset_index(drop=True)
