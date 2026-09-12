"""Driver and department-OPEX scenario levers."""

from __future__ import annotations

import pandas as pd

from calculation.finance import CANONICAL_COLUMNS
from scenarios.interface import ScenarioValidationError


DRIVER_LEVERS = {
    "units_change_pct": ("units", "multiply"),
    "price_change_pct": ("average_sale_price", "multiply"),
    "discount_rate_change_pp": ("discount_rate", "add"),
    "unit_cogs_change_pct": ("unit_cogs", "multiply"),
}
DRIVER_VALUE_COLUMNS = [
    "units", "average_sale_price", "unit_cogs", "discount_rate",
    "average_manufacturing_price",
]


def apply_driver_levers(
    baseline: pd.DataFrame,
    mask: pd.Series,
    levers: dict,
) -> tuple[pd.DataFrame, dict]:
    result = baseline.copy(deep=True)
    applied = {}
    clipped_discount_rows = 0
    for lever, (column, operation) in DRIVER_LEVERS.items():
        change = float(levers.get(lever, 0.0))
        if change == 0:
            continue
        if operation == "multiply":
            result.loc[mask, column] = result.loc[mask, column].astype(float) * (1 + change)
        else:
            raw = result.loc[mask, column].astype(float) + change
            clipped_discount_rows += int((~raw.between(0, 1)).sum())
            result.loc[mask, column] = raw.clip(0, 1)
        applied[lever] = change
    return result, {
        "applied_driver_levers": applied,
        "matched_driver_rows": int(mask.sum()),
        "discount_rows_clipped": clipped_discount_rows,
    }


def apply_department_opex_levers(
    artifacts: dict[str, pd.DataFrame],
    request: dict,
    source_name: str,
    ebitda_source_name: str,
) -> tuple[dict[str, pd.DataFrame], dict[str, int]]:
    result = {key: value.copy() for key, value in artifacts.items()}
    department = result["department"].copy()
    changes = request["levers"].get("department_opex_change_pct", {}) or {}
    matched = {}
    start = pd.Timestamp(request["period"]["start"])
    end = pd.Timestamp(request["period"]["end"])
    countries = request.get("filters", {}).get("country")
    countries = [countries] if isinstance(countries, str) else countries

    for department_name, change_value in changes.items():
        change = float(change_value)
        mask = department["period_date"].between(start, end)
        if countries is not None:
            mask &= department["country"].isin(countries)
        mask &= department["department"] == department_name
        count = int(mask.sum())
        if count == 0:
            raise ScenarioValidationError(
                f"Department OPEX lever for {department_name} matched zero rows."
            )
        department.loc[mask, "amount"] = (
            department.loc[mask, "amount"].astype(float) * (1 + change)
        )
        matched[department_name] = count

    return recalculate_opex_artifacts(
        result, department, source_name, ebitda_source_name
    ), matched


def recalculate_opex_artifacts(
    artifacts: dict[str, pd.DataFrame],
    department: pd.DataFrame,
    source_name: str,
    ebitda_source_name: str,
) -> dict[str, pd.DataFrame]:
    result = {key: value.copy() for key, value in artifacts.items()}
    opex_total = (
        department.groupby(
            ["period_date", "country", "version", "currency"], as_index=False
        )["amount"]
        .sum()
        .sort_values(["period_date", "country"])
        .reset_index(drop=True)
    )
    opex_total["product"] = pd.NA
    opex_total["segment"] = pd.NA
    opex_total["department"] = pd.NA
    opex_total["account"] = "OPEX_TOTAL"
    opex_total["source"] = source_name
    opex_total = opex_total[CANONICAL_COLUMNS]

    gross_profit = result["gross_profit"]
    ebitda = gross_profit.merge(
        opex_total[["period_date", "country", "amount"]].rename(
            columns={"amount": "opex_total"}
        ),
        on=["period_date", "country"],
        validate="one_to_one",
    )
    if len(ebitda) != len(gross_profit) or len(ebitda) != len(opex_total):
        raise ScenarioValidationError("Scenario OPEX and Gross Profit coverage do not align.")
    ebitda["amount"] = ebitda["gross_profit"] - ebitda["opex_total"]
    ebitda["product"] = pd.NA
    ebitda["segment"] = pd.NA
    ebitda["department"] = pd.NA
    ebitda["account"] = "EBITDA"
    ebitda["version"] = department["version"].iloc[0]
    ebitda["currency"] = department["currency"].iloc[0]
    ebitda["source"] = ebitda_source_name
    ebitda = ebitda[CANONICAL_COLUMNS]

    result["department"] = department.sort_values(
        ["period_date", "country", "department", "account"]
    ).reset_index(drop=True)
    result["opex_total"] = opex_total
    result["ebitda"] = ebitda
    result["output"] = pd.concat(
        [department, opex_total, ebitda], ignore_index=True
    ).sort_values(
        ["period_date", "country", "account", "department"], na_position="last"
    ).reset_index(drop=True)
    return result


def rebase_opex_to_authoritative_baseline(
    generated_baseline: dict[str, pd.DataFrame],
    generated_scenario: dict[str, pd.DataFrame],
    authoritative_baseline_finance: pd.DataFrame,
    source_name: str,
    ebitda_source_name: str,
    tolerance: float,
) -> dict[str, pd.DataFrame]:
    """Apply shared-engine OPEX deltas on top of the selected authoritative baseline."""
    keys = ["period_date", "country", "department", "account"]
    base_generated = generated_baseline["department"][keys + ["amount"]].rename(
        columns={"amount": "generated_baseline_amount"}
    )
    scenario_generated = generated_scenario["department"].copy()
    authoritative = authoritative_baseline_finance.loc[
        authoritative_baseline_finance["account"].str.startswith("OPEX_")
        & (authoritative_baseline_finance["account"] != "OPEX_TOTAL"),
        keys + ["amount"],
    ].rename(columns={"amount": "authoritative_baseline_amount"})
    check = scenario_generated.merge(
        base_generated,
        on=keys,
        validate="one_to_one",
    ).merge(
        authoritative,
        on=keys,
        validate="one_to_one",
    )
    if len(check) != len(scenario_generated) or len(check) != len(authoritative):
        raise ScenarioValidationError("Authoritative and generated OPEX coverage do not align.")
    check["amount"] = (
        check["authoritative_baseline_amount"]
        + check["amount"]
        - check["generated_baseline_amount"]
    )
    if (check["amount"] < -tolerance).any():
        raise ScenarioValidationError("Revenue-driven OPEX delta produced negative department OPEX.")
    check["amount"] = check["amount"].clip(lower=0)
    department = check[CANONICAL_COLUMNS]
    rebased = {key: value.copy() for key, value in generated_scenario.items()}
    return recalculate_opex_artifacts(
        rebased, department, source_name, ebitda_source_name
    )
