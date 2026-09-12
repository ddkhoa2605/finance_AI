"""Request and result validations for the local Scenario Engine."""

from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

from calculation.finance import OPERATING_ACCOUNTS, validate_operating_finance
from calculation.opex import validate_opex_artifacts
from scenarios.interface import ScenarioValidationError
from scenarios.levers import DRIVER_LEVERS, DRIVER_VALUE_COLUMNS
from scenarios.scope import FILTER_DIMENSIONS, build_scope_mask, normalize_filter


SCENARIO_ID_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_]*$")


def validate_request(
    request: dict,
    supported_baselines: set[str],
    department_names: set[str],
) -> None:
    required = {"scenario_id", "name", "base_version", "period", "filters", "levers"}
    missing = sorted(required.difference(request))
    if missing:
        raise ScenarioValidationError(f"Scenario request is missing fields: {missing}")
    if not SCENARIO_ID_PATTERN.fullmatch(str(request["scenario_id"])):
        raise ScenarioValidationError("scenario_id must contain only uppercase letters, numbers, and underscores.")
    if not str(request["name"]).strip():
        raise ScenarioValidationError("Scenario name cannot be empty.")
    if request["base_version"] not in supported_baselines:
        raise ScenarioValidationError(
            f"Unsupported base_version {request['base_version']}; expected {sorted(supported_baselines)}."
        )
    if set(request["period"]) != {"start", "end"}:
        raise ScenarioValidationError("Scenario period must contain exactly start and end.")
    start = pd.Timestamp(request["period"]["start"])
    end = pd.Timestamp(request["period"]["end"])
    if start > end:
        raise ScenarioValidationError("Scenario period start must not be after end.")

    unknown_filters = set(request["filters"]).difference(FILTER_DIMENSIONS)
    if unknown_filters:
        raise ScenarioValidationError(f"Unsupported scenario filters: {sorted(unknown_filters)}")
    for dimension in FILTER_DIMENSIONS:
        normalize_filter(request["filters"].get(dimension))

    allowed_levers = set(DRIVER_LEVERS) | {"department_opex_change_pct"}
    unknown_levers = set(request["levers"]).difference(allowed_levers)
    if unknown_levers:
        raise ScenarioValidationError(f"Unsupported scenario levers: {sorted(unknown_levers)}")
    nonzero = False
    for lever in DRIVER_LEVERS:
        value = request["levers"].get(lever, 0.0)
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ScenarioValidationError(f"{lever} must be a finite number.")
        if lever != "discount_rate_change_pp" and float(value) < -1:
            raise ScenarioValidationError(f"{lever} cannot reduce its driver below zero.")
        nonzero |= float(value) != 0

    department_changes = request["levers"].get("department_opex_change_pct", {}) or {}
    if not isinstance(department_changes, dict):
        raise ScenarioValidationError("department_opex_change_pct must be a mapping.")
    unknown_departments = set(department_changes).difference(department_names)
    if unknown_departments:
        raise ScenarioValidationError(
            f"Unknown OPEX departments: {sorted(unknown_departments)}"
        )
    for department, value in department_changes.items():
        if not isinstance(value, (int, float)) or not math.isfinite(float(value)):
            raise ScenarioValidationError(f"OPEX change for {department} must be finite.")
        if float(value) < -1:
            raise ScenarioValidationError(f"OPEX change for {department} cannot be below -100%.")
        nonzero |= float(value) != 0
    if department_changes and (
        request["filters"].get("product") is not None
        or request["filters"].get("segment") is not None
    ):
        raise ScenarioValidationError(
            "Department OPEX levers cannot use Product or Segment filters because OPEX grain is country-month-department."
        )
    if not nonzero:
        raise ScenarioValidationError("Scenario must contain at least one non-zero lever.")


def validate_scope_and_driver_magnitude(result: dict, tolerance: float) -> None:
    baseline = result["baseline_drivers"]
    scenario = result["scenario_drivers"]
    request = result["request"]
    mask = build_scope_mask(baseline, request)
    if int(mask.sum()) == 0:
        raise ScenarioValidationError("Scenario scope matched zero baseline rows.")

    if not np.allclose(
        baseline.loc[~mask, DRIVER_VALUE_COLUMNS].astype(float),
        scenario.loc[~mask, DRIVER_VALUE_COLUMNS].astype(float),
        atol=tolerance,
        rtol=0,
        equal_nan=True,
    ):
        raise ScenarioValidationError("Rows outside the scenario scope were modified.")

    targeted_columns = {
        column
        for lever, (column, _) in DRIVER_LEVERS.items()
        if float(request["levers"].get(lever, 0.0)) != 0
    }
    unchanged_columns = [
        column for column in DRIVER_VALUE_COLUMNS if column not in targeted_columns
    ]
    if not np.allclose(
        baseline.loc[mask, unchanged_columns].astype(float),
        scenario.loc[mask, unchanged_columns].astype(float),
        atol=tolerance,
        rtol=0,
        equal_nan=True,
    ):
        raise ScenarioValidationError("A driver without an explicit lever changed inside scope.")

    for lever, (column, operation) in DRIVER_LEVERS.items():
        change = float(request["levers"].get(lever, 0.0))
        if change == 0:
            continue
        before = baseline.loc[mask, column].astype(float)
        expected = before * (1 + change) if operation == "multiply" else (before + change).clip(0, 1)
        if not np.allclose(
            scenario.loc[mask, column].astype(float), expected, atol=tolerance, rtol=0
        ):
            raise ScenarioValidationError(f"Scenario lever magnitude failed for {lever}.")


def validate_department_opex_magnitude(result: dict, tolerance: float) -> None:
    request = result["request"]
    changes = request["levers"].get("department_opex_change_pct", {}) or {}
    before = result["scenario_opex_before_levers"]["department"]
    after = result["scenario_opex"]["department"]
    countries = normalize_filter(request["filters"].get("country"))
    start = pd.Timestamp(request["period"]["start"])
    end = pd.Timestamp(request["period"]["end"])
    keys = ["period_date", "country", "department", "account"]

    for department, change in changes.items():
        mask_before = before["period_date"].between(start, end) & (
            before["department"] == department
        )
        mask_after = after["period_date"].between(start, end) & (
            after["department"] == department
        )
        if countries is not None:
            mask_before &= before["country"].isin(countries)
            mask_after &= after["country"].isin(countries)
        check = before.loc[mask_before, keys + ["amount"]].merge(
            after.loc[mask_after, keys + ["amount"]],
            on=keys,
            suffixes=("_before", "_after"),
            validate="one_to_one",
        )
        if check.empty or not np.allclose(
            check["amount_after"], check["amount_before"] * (1 + float(change)),
            atol=tolerance,
            rtol=0,
        ):
            raise ScenarioValidationError(
                f"Department OPEX lever magnitude failed for {department}."
            )


def validate_result(result: dict, opex_config: dict, tolerance: float) -> None:
    drivers = result["scenario_drivers"]
    finance = result["scenario_finance"]
    driver_grain = ["period_date", "country", "product", "segment", "version"]
    finance_grain = [
        "period_date", "country", "product", "segment", "department", "account", "version"
    ]
    if drivers.duplicated(driver_grain).any():
        raise ScenarioValidationError("Scenario driver grain is not unique.")
    if finance.duplicated(finance_grain).any():
        raise ScenarioValidationError("Scenario finance grain is not unique.")
    if (drivers[["units", "average_sale_price", "unit_cogs"]] < 0).any().any():
        raise ScenarioValidationError("Scenario contains a negative driver.")
    if not drivers["discount_rate"].between(0, 1).all():
        raise ScenarioValidationError("Scenario Discount Rate is outside [0, 1].")

    validate_scope_and_driver_magnitude(result, tolerance)
    validate_operating_finance(result["scenario_operating"], tolerance)
    validate_opex_artifacts(result["scenario_opex"], opex_config, tolerance)
    validate_department_opex_magnitude(result, tolerance)
    if set(result["scenario_operating"]["account"]) != set(OPERATING_ACCOUNTS):
        raise ScenarioValidationError("Scenario operating account coverage is incomplete.")

    department = result["scenario_opex"]["department"]
    expected_departments = len(opex_config["departments"])
    coverage = department.groupby(["period_date", "country"])["account"].nunique()
    if not (coverage == expected_departments).all():
        raise ScenarioValidationError("OPEX department coverage is incomplete.")

    expected_finance_rows = (
        len(drivers) * len(OPERATING_ACCOUNTS)
        + len(coverage) * (expected_departments + 2)
    )
    if len(finance) != expected_finance_rows:
        raise ScenarioValidationError("Scenario finance row coverage mismatch.")


def validate_expected_directions(
    comparison: pd.DataFrame,
    expected_directions: dict,
    tolerance: float,
) -> None:
    indexed = comparison.set_index("metric")
    unknown = set(expected_directions).difference(indexed.index)
    if unknown:
        raise ScenarioValidationError(
            f"Expected-direction metrics are unavailable: {sorted(unknown)}"
        )
    failures = []
    for metric, expected in expected_directions.items():
        delta = float(indexed.loc[metric, "impact"])
        actual = (
            "unchanged"
            if abs(delta) <= tolerance
            else ("increase" if delta > 0 else "decrease")
        )
        if actual != expected:
            failures.append(f"{metric}: expected {expected}, actual {actual}")
    if failures:
        raise ScenarioValidationError(
            "Scenario causal-direction validation failed: " + "; ".join(failures)
        )
