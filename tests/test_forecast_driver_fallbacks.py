"""Synthetic coverage tests for every Phase 5 driver-rule fallback level."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from forecasting.driver_rules import apply_driver_rules  # noqa: E402


TARGET = pd.DataFrame(
    [
        {
            "period_date": pd.Timestamp("2025-06-01"),
            "country": "Canada",
            "product": "Paseo",
            "segment": "Enterprise",
        }
    ]
)
CONFIG = {
    "trailing_weights": [0.2, 0.3, 0.5],
    "pricing_factor": 1.0,
    "cost_factor": 1.0,
}


def history_row(
    date: str,
    country: str = "Canada",
    product: str = "Paseo",
    segment: str = "Enterprise",
    units: float = 100.0,
    asp: float = 20.0,
    unit_cogs: float = 8.0,
    discount_rate: float = 0.1,
) -> dict:
    return {
        "period_date": pd.Timestamp(date),
        "country": country,
        "product": product,
        "segment": segment,
        "units": units,
        "average_sale_price": asp,
        "unit_cogs": unit_cogs,
        "discount_rate": discount_rate,
    }


class DriverFallbackTests(unittest.TestCase):
    def assert_fallback(self, rows: list[dict], expected_level: str) -> pd.DataFrame:
        forecast, usage = apply_driver_rules(pd.DataFrame(rows), TARGET, CONFIG)
        self.assertEqual(len(forecast), 1)
        self.assertEqual(set(usage["fallback_level"]), {expected_level})
        self.assertEqual(set(usage["row_count"]), {1})
        self.assertEqual(
            set(usage["metric"]),
            {"average_sale_price", "unit_cogs", "discount_rate"},
        )
        return forecast

    def test_same_grain_same_month_previous_year(self) -> None:
        forecast = self.assert_fallback(
            [history_row("2024-06-01", asp=25.0, unit_cogs=9.0, discount_rate=0.12)],
            "same_grain_same_month_previous_year",
        )
        self.assertAlmostEqual(forecast.iloc[0]["average_sale_price"], 25.0)
        self.assertAlmostEqual(forecast.iloc[0]["unit_cogs"], 9.0)
        self.assertAlmostEqual(forecast.iloc[0]["discount_rate"], 0.12)

    def test_same_grain_weighted_trailing_three(self) -> None:
        forecast = self.assert_fallback(
            [
                history_row("2024-10-01", asp=10.0, unit_cogs=1.0, discount_rate=0.1),
                history_row("2024-11-01", asp=20.0, unit_cogs=2.0, discount_rate=0.2),
                history_row("2024-12-01", asp=30.0, unit_cogs=3.0, discount_rate=0.3),
            ],
            "same_grain_weighted_trailing_three",
        )
        self.assertAlmostEqual(forecast.iloc[0]["average_sale_price"], 23.0)
        self.assertAlmostEqual(forecast.iloc[0]["unit_cogs"], 2.3)
        self.assertAlmostEqual(forecast.iloc[0]["discount_rate"], 0.23)

    def test_country_product_fallback(self) -> None:
        self.assert_fallback(
            [history_row("2024-12-01", segment="Government")],
            "country_product",
        )

    def test_product_fallback(self) -> None:
        self.assert_fallback(
            [history_row("2024-12-01", country="France", segment="Government")],
            "product",
        )

    def test_global_fallback(self) -> None:
        self.assert_fallback(
            [
                history_row(
                    "2024-12-01",
                    country="France",
                    product="VTT",
                    segment="Government",
                )
            ],
            "global",
        )


if __name__ == "__main__":
    unittest.main()
