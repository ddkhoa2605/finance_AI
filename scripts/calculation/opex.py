"""Shared deterministic OPEX and EBITDA calculations."""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from calculation.finance import CANONICAL_COLUMNS


def _keyed_noise(
    seed: int,
    period_date: pd.Timestamp,
    country: str,
    department_account: str,
    noise_config: dict,
) -> float:
    key = (
        f"{int(seed)}|{pd.Timestamp(period_date).strftime('%Y-%m-%d')}|"
        f"{country}|{department_account}"
    )
    digest = hashlib.sha256(key.encode("utf-8")).digest()
    local_seed = int.from_bytes(digest[:8], byteorder="big", signed=False)
    rng = np.random.default_rng(local_seed)
    value = rng.normal(
        loc=float(noise_config["loc"]),
        scale=float(noise_config["scale"]),
    )
    return float(
        np.clip(value, noise_config["minimum"], noise_config["maximum"])
    )


def _country_month_metric(finance: pd.DataFrame, account: str, name: str) -> pd.DataFrame:
    result = finance.loc[finance["account"] == account].sort_values(
        ["period_date", "country", "product", "segment", "account"],
        na_position="last",
    )
    if result.empty:
        raise ValueError(f"Finance input contains no {account} rows.")
    return (
        result.groupby(["period_date", "country"], as_index=False)["amount"]
        .sum()
        .rename(columns={"amount": name})
        .sort_values(["period_date", "country"])
        .reset_index(drop=True)
    )


def generate_opex(
    finance: pd.DataFrame,
    config: dict,
    version: str,
    source_name: str,
    ebitda_source: str,
    currency: str = "USD",
) -> dict[str, pd.DataFrame]:
    """Generate department OPEX, OPEX Total, and EBITDA from canonical finance."""
    revenue = _country_month_metric(finance, "REVENUE", "revenue")
    monthly_total = revenue.groupby("period_date")["revenue"].transform("sum")
    if (monthly_total <= 0).any():
        raise ValueError("Cannot allocate fixed OPEX for non-positive monthly revenue.")
    revenue["revenue_share"] = revenue["revenue"] / monthly_total

    frames = []
    noise_config = config["controlled_noise"]
    for department_key, department in config["departments"].items():
        detail = revenue.copy()
        detail["department_key"] = department_key
        detail["department"] = department["display_name"]
        detail["account"] = department["account"]
        detail["fixed_component"] = (
            float(department["fixed_monthly"]) * detail["revenue_share"]
        )
        detail["variable_component"] = (
            detail["revenue"] * float(department["revenue_ratio"])
        )
        detail["base_amount"] = detail["fixed_component"] + detail["variable_component"]
        detail["seasonality_factor"] = detail["period_date"].dt.month.map(
            config["seasonality"]
        )
        detail["country_factor"] = detail["country"].map(
            config["country_coefficients"]
        )
        if detail[["seasonality_factor", "country_factor"]].isna().any().any():
            raise ValueError("Missing OPEX seasonality or country coefficient.")
        detail["noise"] = [
            _keyed_noise(
                config["random_seed"], row.period_date, row.country, row.account,
                noise_config,
            )
            for row in detail.itertuples(index=False)
        ]
        detail["noise_factor"] = 1 + detail["noise"]
        detail["amount"] = (
            detail["base_amount"]
            * detail["seasonality_factor"]
            * detail["country_factor"]
            * detail["noise_factor"]
        )
        frames.append(detail)

    department_detail = pd.concat(frames, ignore_index=True).sort_values(
        ["period_date", "country", "department", "account"]
    ).reset_index(drop=True)
    department = department_detail.copy()
    department["product"] = pd.NA
    department["segment"] = pd.NA
    department["version"] = version
    department["currency"] = currency
    department["source"] = source_name
    department = department[CANONICAL_COLUMNS]

    opex_total = (
        department_detail.groupby(["period_date", "country"], as_index=False)["amount"]
        .sum()
        .sort_values(["period_date", "country"])
        .reset_index(drop=True)
    )
    opex_total["product"] = pd.NA
    opex_total["segment"] = pd.NA
    opex_total["department"] = pd.NA
    opex_total["account"] = "OPEX_TOTAL"
    opex_total["version"] = version
    opex_total["currency"] = currency
    opex_total["source"] = source_name
    opex_total = opex_total[CANONICAL_COLUMNS]

    gross_profit = _country_month_metric(finance, "GROSS_PROFIT", "gross_profit")
    ebitda = gross_profit.merge(
        opex_total[["period_date", "country", "amount"]].rename(
            columns={"amount": "opex_total"}
        ),
        on=["period_date", "country"],
        how="inner",
        validate="one_to_one",
    )
    if len(ebitda) != len(gross_profit) or len(ebitda) != len(opex_total):
        raise ValueError("Gross Profit and OPEX coverage do not align.")
    ebitda["amount"] = ebitda["gross_profit"] - ebitda["opex_total"]
    ebitda["product"] = pd.NA
    ebitda["segment"] = pd.NA
    ebitda["department"] = pd.NA
    ebitda["account"] = "EBITDA"
    ebitda["version"] = version
    ebitda["currency"] = currency
    ebitda["source"] = ebitda_source
    ebitda = ebitda[CANONICAL_COLUMNS]

    output = pd.concat([department, opex_total, ebitda], ignore_index=True).sort_values(
        ["period_date", "country", "account", "department"], na_position="last"
    ).reset_index(drop=True)
    return {
        "revenue": revenue,
        "department_detail": department_detail,
        "department": department,
        "opex_total": opex_total,
        "gross_profit": gross_profit,
        "ebitda": ebitda,
        "output": output,
    }


def validate_opex_artifacts(
    artifacts: dict[str, pd.DataFrame], config: dict, tolerance: float = 0.01
) -> None:
    detail = artifacts["department_detail"]
    department = artifacts["department"]
    opex_total = artifacts["opex_total"]
    ebitda = artifacts["ebitda"]
    if (department["amount"] < 0).any():
        raise ValueError("Department OPEX cannot be negative.")
    bounds = config["controlled_noise"]
    if not detail["noise"].between(bounds["minimum"], bounds["maximum"]).all():
        raise ValueError("Controlled OPEX noise exceeded configured bounds.")
    expected = (
        detail["base_amount"]
        * detail["seasonality_factor"]
        * detail["country_factor"]
        * detail["noise_factor"]
    )
    if not np.allclose(detail["amount"], expected, atol=tolerance):
        raise ValueError("Adjusted OPEX formula validation failed.")
    fixed_check = detail.groupby(
        ["period_date", "department_key"], as_index=False
    )["fixed_component"].sum()
    fixed_check["expected"] = fixed_check["department_key"].map(
        {
            key: float(value["fixed_monthly"])
            for key, value in config["departments"].items()
        }
    )
    if fixed_check["expected"].isna().any() or not np.allclose(
        fixed_check["fixed_component"], fixed_check["expected"], atol=tolerance
    ):
        raise ValueError("Fixed OPEX allocation reconciliation failed.")
    department_sum = department.groupby(["period_date", "country"])["amount"].sum()
    total = opex_total.set_index(["period_date", "country"])["amount"]
    if not np.allclose(department_sum.sort_index(), total.sort_index(), atol=tolerance):
        raise ValueError("OPEX Total reconciliation failed.")
    check = artifacts["gross_profit"].merge(
        opex_total[["period_date", "country", "amount"]].rename(
            columns={"amount": "opex_total"}
        ), on=["period_date", "country"], validate="one_to_one"
    ).merge(
        ebitda[["period_date", "country", "amount"]].rename(
            columns={"amount": "ebitda"}
        ), on=["period_date", "country"], validate="one_to_one"
    )
    if not np.allclose(
        check["gross_profit"] - check["opex_total"], check["ebitda"], atol=tolerance
    ):
        raise ValueError("EBITDA reconciliation failed.")


def assert_noise_order_independent(
    finance: pd.DataFrame,
    config: dict,
    version: str,
    source_name: str,
    ebitda_source: str,
) -> None:
    first = generate_opex(finance, config, version, source_name, ebitda_source)
    shuffled = finance.sample(frac=1, random_state=913).reset_index(drop=True)
    second = generate_opex(shuffled, config, version, source_name, ebitda_source)
    pd.testing.assert_frame_equal(first["output"], second["output"], check_exact=True)
