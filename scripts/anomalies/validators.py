"""Validation helpers for the controlled-event benchmark."""

from __future__ import annotations

import numpy as np
import pandas as pd

from anomalies.injector import build_event_mask
from calculation.finance import OPERATING_ACCOUNTS, validate_operating_finance
from calculation.opex import validate_opex_artifacts


def observed_direction(delta: float, tolerance: float) -> str:
    if abs(delta) <= tolerance:
        return "unchanged"
    return "increase" if delta > 0 else "decrease"


def validate_impact_directions(impacts: pd.DataFrame) -> None:
    failed = impacts.loc[~impacts["direction_pass"]]
    if not failed.empty:
        details = failed[["event_id", "metric", "expected_direction", "actual_direction"]]
        raise ValueError(
            "Expected event direction validation failed:\n"
            + details.to_string(index=False)
        )


def validate_exact_event_operations(
    baseline: dict,
    isolated_scenarios: dict[str, dict],
    events: list[dict],
    tolerance: float,
) -> None:
    """Prove that every direct target received exactly the configured operation."""
    driver_targets = {
        "volume": "units",
        "unit_cogs": "unit_cogs",
        "discount_rate": "discount_rate",
    }
    driver_keys = ["period_date", "country", "product", "segment"]
    for event in events:
        scenario = isolated_scenarios[event["event_id"]]
        if event["event_type"] in driver_targets:
            target = driver_targets[event["event_type"]]
            before = baseline["drivers"].loc[
                build_event_mask(baseline["drivers"], event), driver_keys + [target]
            ]
            after = scenario["drivers"].loc[
                build_event_mask(scenario["drivers"], event), driver_keys + [target]
            ]
            check = before.merge(
                after,
                on=driver_keys,
                suffixes=("_before", "_after"),
                validate="one_to_one",
            )
        else:
            keys = ["period_date", "country", "department", "account"]
            before_frame = baseline["opex"]["department"]
            after_frame = scenario["opex"]["department"]
            before = before_frame.loc[
                build_event_mask(before_frame, event, opex=True), keys + ["amount"]
            ]
            after = after_frame.loc[
                build_event_mask(after_frame, event, opex=True), keys + ["amount"]
            ]
            check = before.merge(
                after,
                on=keys,
                suffixes=("_before", "_after"),
                validate="one_to_one",
            ).rename(
                columns={"amount_before": "target_before", "amount_after": "target_after"}
            )
            target = "target"

        if check.empty or len(check) != len(before) or len(check) != len(after):
            raise ValueError(f"Event {event['event_id']} direct-target coverage mismatch.")
        before_values = check[f"{target}_before"].astype(float)
        expected = (
            before_values * float(event["value"])
            if event["operation"] == "multiply"
            else before_values + float(event["value"])
        )
        if not np.allclose(
            check[f"{target}_after"].astype(float), expected, atol=tolerance, rtol=0
        ):
            raise ValueError(
                f"Event {event['event_id']} did not apply its configured operation exactly."
            )


def validate_benchmark(
    drivers: pd.DataFrame,
    operating: pd.DataFrame,
    opex: dict[str, pd.DataFrame],
    finance_fact: pd.DataFrame,
    config: dict,
) -> None:
    driver_grain = ["period_date", "country", "product", "segment", "version"]
    finance_grain = [
        "period_date", "country", "product", "segment", "department",
        "account", "version",
    ]
    if drivers.duplicated(driver_grain).any():
        raise ValueError("Anomaly driver grain is not unique.")
    if finance_fact.duplicated(finance_grain).any():
        raise ValueError("Anomaly finance grain is not unique.")
    if (drivers[["units", "average_sale_price", "unit_cogs"]] < 0).any().any():
        raise ValueError("Anomaly drivers contain a negative value.")
    if not drivers["discount_rate"].between(0, 1).all():
        raise ValueError("Anomaly Discount Rate is outside [0, 1].")
    validate_operating_finance(operating, float(config["tolerance"]))
    validate_opex_artifacts(opex, config["opex_config"], float(config["tolerance"]))
    if set(operating["account"]) != set(OPERATING_ACCOUNTS):
        raise ValueError("Anomaly operating finance account coverage is incomplete.")


def validate_baseline_reconstruction(
    reconstructed_operating: pd.DataFrame,
    authoritative_actual: pd.DataFrame,
    reconstructed_opex: pd.DataFrame,
    authoritative_opex: pd.DataFrame,
    tolerance: float,
) -> None:
    keys = ["period_date", "country", "product", "segment", "account"]
    expected_operating = authoritative_actual.loc[
        authoritative_actual["account"].isin(OPERATING_ACCOUNTS), keys + ["amount"]
    ]
    check = reconstructed_operating[keys + ["amount"]].merge(
        expected_operating,
        on=keys,
        how="outer",
        suffixes=("_reconstructed", "_authoritative"),
        validate="one_to_one",
    )
    if check.isna().any().any() or not np.allclose(
        check["amount_reconstructed"], check["amount_authoritative"], atol=tolerance
    ):
        raise ValueError("Baseline driver-to-finance reconstruction does not match Actual.")

    opex_keys = ["period_date", "country", "department", "account"]
    expected_opex = authoritative_opex[opex_keys + ["amount"]]
    opex_check = reconstructed_opex[opex_keys + ["amount"]].merge(
        expected_opex,
        on=opex_keys,
        how="outer",
        suffixes=("_reconstructed", "_authoritative"),
        validate="one_to_one",
        indicator=True,
    )
    if (opex_check["_merge"] != "both").any() or opex_check[
        ["amount_reconstructed", "amount_authoritative"]
    ].isna().any().any() or not np.allclose(
        opex_check["amount_reconstructed"], opex_check["amount_authoritative"], atol=tolerance
    ):
        raise ValueError("Baseline OPEX reconstruction does not match authoritative OPEX.")
