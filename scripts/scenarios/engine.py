"""Local deterministic implementation of the Scenario Engine."""

from __future__ import annotations

import copy

import pandas as pd

from calculation.finance import reconstruct_operating_finance
from calculation.opex import generate_opex
from scenarios.comparison import build_comparison
from scenarios.interface import ScenarioEngine, ScenarioValidationError
from scenarios.levers import (
    apply_department_opex_levers,
    apply_driver_levers,
    rebase_opex_to_authoritative_baseline,
)
from scenarios.scope import build_scope_mask
from scenarios.validator import (
    validate_expected_directions,
    validate_request,
    validate_result,
)


DRIVER_SORT = ["period_date", "country", "product", "segment"]
FINANCE_SORT = [
    "period_date", "country", "product", "segment", "department", "account", "version"
]


class LocalScenarioEngine(ScenarioEngine):
    """Run auditable what-if scenarios from canonical baseline drivers."""

    def __init__(
        self,
        baseline_drivers: dict[str, pd.DataFrame],
        baseline_finance: dict[str, pd.DataFrame],
        scenario_config: dict,
        opex_config: dict,
    ) -> None:
        self._baseline_drivers = {
            version: frame.copy(deep=True).sort_values(DRIVER_SORT).reset_index(drop=True)
            for version, frame in baseline_drivers.items()
        }
        self._baseline_finance = {
            version: frame.copy(deep=True).sort_values(
                FINANCE_SORT, na_position="last"
            ).reset_index(drop=True)
            for version, frame in baseline_finance.items()
        }
        if set(self._baseline_drivers) != set(self._baseline_finance):
            raise ScenarioValidationError("Baseline driver and finance version coverage differ.")
        self._scenario_config = copy.deepcopy(scenario_config)
        self._opex_config = copy.deepcopy(opex_config)
        self._department_names = {
            details["display_name"] for details in opex_config["departments"].values()
        }

    def _normalize_request(self, request: dict) -> dict:
        normalized = copy.deepcopy(request)
        normalized.setdefault(
            "base_version", self._scenario_config["default_base_version"]
        )
        return normalized

    def validate(self, request: dict) -> None:
        request = self._normalize_request(request)
        validate_request(
            request,
            set(self._baseline_drivers),
            self._department_names,
        )
        baseline = self._baseline_drivers[request["base_version"]]
        if int(build_scope_mask(baseline, request).sum()) == 0:
            raise ScenarioValidationError("Scenario scope matched zero baseline rows.")

    def _build_finance(
        self,
        drivers: pd.DataFrame,
        version: str,
        finance_source: str,
        opex_source: str,
        ebitda_source: str,
    ) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, pd.DataFrame]]:
        operating = reconstruct_operating_finance(
            drivers,
            version=version,
            source=finance_source,
        )
        opex = generate_opex(
            operating,
            self._opex_config,
            version=version,
            source_name=opex_source,
            ebitda_source=ebitda_source,
        )
        finance = pd.concat([operating, opex["output"]], ignore_index=True).sort_values(
            FINANCE_SORT, na_position="last"
        ).reset_index(drop=True)
        return operating, finance, opex

    def run(self, request: dict) -> dict:
        request = self._normalize_request(request)
        self.validate(request)
        baseline_drivers = self._baseline_drivers[request["base_version"]].copy(deep=True)
        pristine_baseline = baseline_drivers.copy(deep=True)
        baseline_operating, _, generated_baseline_opex = self._build_finance(
            baseline_drivers,
            request["base_version"],
            "scenario_baseline_reconstruction",
            "scenario_baseline_opex",
            "scenario_baseline_ebitda",
        )
        baseline_finance = self._baseline_finance[request["base_version"]].copy(deep=True)

        mask = build_scope_mask(baseline_drivers, request)
        scenario_drivers, lever_metadata = apply_driver_levers(
            baseline_drivers,
            mask,
            request["levers"],
        )
        scenario_drivers["version"] = self._scenario_config["output_version"]
        scenario_drivers["source"] = self._scenario_config["source_name"]
        scenario_drivers = scenario_drivers.sort_values(DRIVER_SORT).reset_index(drop=True)

        scenario_operating = reconstruct_operating_finance(
            scenario_drivers,
            version=self._scenario_config["output_version"],
            source=self._scenario_config["source_name"],
        )
        generated_scenario_opex = generate_opex(
            scenario_operating,
            self._opex_config,
            version=self._scenario_config["output_version"],
            source_name=self._scenario_config["opex_source_name"],
            ebitda_source=self._scenario_config["ebitda_source_name"],
        )
        opex_before_levers = rebase_opex_to_authoritative_baseline(
            generated_baseline_opex,
            generated_scenario_opex,
            baseline_finance,
            self._scenario_config["opex_source_name"],
            self._scenario_config["ebitda_source_name"],
            float(self._scenario_config["tolerance"]),
        )
        scenario_opex, opex_matches = apply_department_opex_levers(
            opex_before_levers,
            request,
            self._scenario_config["opex_source_name"],
            self._scenario_config["ebitda_source_name"],
        )
        scenario_finance = pd.concat(
            [scenario_operating, scenario_opex["output"]], ignore_index=True
        ).sort_values(FINANCE_SORT, na_position="last").reset_index(drop=True)

        result = {
            "request": request,
            "baseline_drivers": baseline_drivers,
            "baseline_operating": baseline_operating,
            "baseline_opex": generated_baseline_opex,
            "baseline_finance": baseline_finance,
            "scenario_drivers": scenario_drivers,
            "scenario_operating": scenario_operating,
            "scenario_opex_before_levers": opex_before_levers,
            "scenario_opex": scenario_opex,
            "scenario_finance": scenario_finance,
            "metadata": {
                **lever_metadata,
                "matched_department_opex_rows": opex_matches,
            },
        }
        validate_result(
            result,
            self._opex_config,
            float(self._scenario_config["tolerance"]),
        )
        pd.testing.assert_frame_equal(pristine_baseline, baseline_drivers, check_exact=True)
        result["comparison"] = build_comparison(result)
        validate_expected_directions(
            result["comparison"],
            request.get("expected_direction", {}),
            float(self._scenario_config["tolerance"]),
        )
        return result

    def get_metadata(self) -> dict:
        return {
            "engine": "LocalScenarioEngine",
            "deterministic": True,
            "supported_baselines": sorted(self._baseline_drivers),
            "default_base_version": self._scenario_config["default_base_version"],
            "supported_filters": ["period", "country", "product", "segment", "department"],
            "supported_levers": [
                "units_change_pct",
                "price_change_pct",
                "discount_rate_change_pp",
                "unit_cogs_change_pct",
                "department_opex_change_pct",
            ],
            "department_names": sorted(self._department_names),
            "finance_reconstruction": "scripts/calculation/finance.py",
            "opex_reconstruction": "scripts/calculation/opex.py",
        }
