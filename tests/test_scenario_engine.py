"""Phase 7 Scenario Engine behavior and safety tests."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from scenarios.engine import LocalScenarioEngine  # noqa: E402
from scenarios.interface import ScenarioValidationError  # noqa: E402
from scenarios.scope import build_scope_mask  # noqa: E402


class ScenarioEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with (PROJECT_ROOT / "config" / "scenarios.yaml").open(encoding="utf-8") as stream:
            cls.config = yaml.safe_load(stream)
        with (PROJECT_ROOT / "config" / "opex.yaml").open(encoding="utf-8") as stream:
            cls.opex_config = yaml.safe_load(stream)
        paths = {
            "ACTUAL": "drivers.csv",
            "BUDGET": "budget_drivers.csv",
            "FORECAST": "forecast_drivers.csv",
        }
        cls.baselines = {}
        for version, filename in paths.items():
            frame = pd.read_csv(
                PROJECT_ROOT / "data" / "processed" / filename,
                parse_dates=["period_date"],
            )
            cls.baselines[version] = frame.loc[frame["version"] == version].copy()
        finance = pd.read_csv(
            PROJECT_ROOT / "data" / "processed" / "finance_fact.csv",
            parse_dates=["period_date"],
        )
        cls.baseline_finance = {
            version: finance.loc[finance["version"] == version].copy()
            for version in paths
        }
        cls.engine = LocalScenarioEngine(
            cls.baselines,
            cls.baseline_finance,
            cls.config,
            cls.opex_config,
        )

    @staticmethod
    def request(version: str, year: int, scenario_id: str = "SCN_TEST") -> dict:
        return {
            "scenario_id": scenario_id,
            "name": f"{version} selection test",
            "base_version": version,
            "period": {"start": f"{year}-01-01", "end": f"{year}-01-01"},
            "filters": {"country": ["Canada"], "product": None, "segment": None},
            "levers": {
                "units_change_pct": 0.0,
                "price_change_pct": 0.0,
                "discount_rate_change_pp": 0.01,
                "unit_cogs_change_pct": 0.0,
                "department_opex_change_pct": {},
            },
        }

    def test_actual_budget_and_forecast_are_selectable(self) -> None:
        for version, year in [("ACTUAL", 2014), ("BUDGET", 2015), ("FORECAST", 2015)]:
            with self.subTest(version=version):
                result = self.engine.run(self.request(version, year, f"SCN_{version}"))
                self.assertEqual(result["request"]["base_version"], version)
                self.assertEqual(set(result["scenario_drivers"]["version"]), {"SCENARIO"})

    def test_missing_base_version_defaults_to_forecast(self) -> None:
        request = self.request("FORECAST", 2015)
        request.pop("base_version")
        result = self.engine.run(request)
        self.assertEqual(result["request"]["base_version"], "FORECAST")

    def test_discount_is_additive_percentage_points_and_scope_isolated(self) -> None:
        request = self.request("FORECAST", 2015)
        result = self.engine.run(request)
        mask = build_scope_mask(result["baseline_drivers"], request)
        expected = (result["baseline_drivers"].loc[mask, "discount_rate"] + 0.01).clip(0, 1)
        pd.testing.assert_series_equal(
            result["scenario_drivers"].loc[mask, "discount_rate"].reset_index(drop=True),
            expected.reset_index(drop=True),
            check_names=False,
        )
        outside_columns = ["units", "average_sale_price", "unit_cogs", "discount_rate"]
        pd.testing.assert_frame_equal(
            result["baseline_drivers"].loc[~mask, outside_columns].reset_index(drop=True),
            result["scenario_drivers"].loc[~mask, outside_columns].reset_index(drop=True),
        )

    def test_zero_match_scope_fails(self) -> None:
        request = self.request("FORECAST", 2015)
        request["filters"]["country"] = ["Vietnam"]
        with self.assertRaisesRegex(ScenarioValidationError, "zero baseline rows"):
            self.engine.run(request)

    def test_opex_lever_rejects_product_filter(self) -> None:
        request = self.request("FORECAST", 2015)
        request["filters"]["product"] = ["Paseo"]
        request["levers"]["discount_rate_change_pp"] = 0.0
        request["levers"]["department_opex_change_pct"] = {"Marketing": -0.1}
        with self.assertRaisesRegex(ScenarioValidationError, "OPEX grain"):
            self.engine.run(request)

    def test_no_implicit_price_elasticity(self) -> None:
        request = self.request("FORECAST", 2015)
        request["levers"]["discount_rate_change_pp"] = 0.0
        request["levers"]["price_change_pct"] = 0.05
        result = self.engine.run(request)
        mask = build_scope_mask(result["baseline_drivers"], request)
        pd.testing.assert_series_equal(
            result["baseline_drivers"].loc[mask, "units"].reset_index(drop=True),
            result["scenario_drivers"].loc[mask, "units"].reset_index(drop=True),
        )


if __name__ == "__main__":
    unittest.main()
