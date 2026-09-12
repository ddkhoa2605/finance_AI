"""Focused unit tests for deterministic Phase 6 event injection."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from anomalies.injector import (  # noqa: E402
    apply_driver_events,
    apply_opex_events,
    build_event_mask,
    validate_event_config,
    validate_no_direct_overlap,
)
from calculation.finance import CANONICAL_COLUMNS  # noqa: E402


def driver_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "period_date": pd.Timestamp("2014-07-01"),
                "country": "Mexico",
                "product": "Paseo",
                "segment": "Government",
                "version": "ACTUAL",
                "units": 100.0,
                "average_sale_price": 20.0,
                "unit_cogs": 8.0,
                "discount_rate": 0.10,
                "average_manufacturing_price": 7.0,
                "source": "test",
            },
            {
                "period_date": pd.Timestamp("2014-07-01"),
                "country": "Mexico",
                "product": "Paseo",
                "segment": "Enterprise",
                "version": "ACTUAL",
                "units": 50.0,
                "average_sale_price": 30.0,
                "unit_cogs": 12.0,
                "discount_rate": 0.20,
                "average_manufacturing_price": 11.0,
                "source": "test",
            },
        ]
    )


def event(event_id: str = "EVT_TEST", event_type: str = "volume") -> dict:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "period_start": "2014-07-01",
        "period_end": "2014-07-01",
        "country": "Mexico",
        "product": "Paseo",
        "segment": None,
        "operation": "multiply",
        "value": 0.88,
        "root_cause": "test",
        "expected_direction": {"units": "decrease"},
    }


class AnomalyInjectionTests(unittest.TestCase):
    def test_null_segment_means_no_segment_filter(self) -> None:
        frame = driver_frame()
        self.assertEqual(int(build_event_mask(frame, event()).sum()), 2)

    def test_driver_event_is_exact_and_does_not_mutate_input(self) -> None:
        frame = driver_frame()
        original = frame.copy(deep=True)
        result, matches = apply_driver_events(frame, [event()])
        self.assertEqual(matches, {"EVT_TEST": 2})
        self.assertEqual(result["units"].tolist(), [44.0, 88.0])
        pd.testing.assert_frame_equal(frame, original)

    def test_direct_overlap_is_rejected(self) -> None:
        duplicate_scope = event("EVT_OTHER")
        with self.assertRaisesRegex(ValueError, "overlap"):
            validate_no_direct_overlap(driver_frame(), [event(), duplicate_scope])

    def test_zero_match_is_rejected(self) -> None:
        missing = event()
        missing["country"] = "Missing Country"
        with self.assertRaisesRegex(ValueError, "zero driver rows"):
            apply_driver_events(driver_frame(), [missing])

    def test_duplicate_event_ids_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unique"):
            validate_event_config([event(), event()])

    def test_opex_event_recalculates_total_and_ebitda(self) -> None:
        rows = []
        for department, account, amount in [
            ("Marketing", "OPEX_MARKETING", 100.0),
            ("Sales", "OPEX_SALES", 200.0),
        ]:
            rows.append(
                {
                    "period_date": pd.Timestamp("2014-07-01"),
                    "country": "France",
                    "product": pd.NA,
                    "segment": pd.NA,
                    "department": department,
                    "account": account,
                    "version": "ACTUAL_WITH_EVENTS",
                    "currency": "USD",
                    "source": "test",
                    "amount": amount,
                }
            )
        department = pd.DataFrame(rows)[CANONICAL_COLUMNS]
        gross_profit = pd.DataFrame(
            [{"period_date": pd.Timestamp("2014-07-01"), "country": "France", "gross_profit": 1000.0}]
        )
        artifacts = {
            "department": department,
            "gross_profit": gross_profit,
            "department_detail": pd.DataFrame(),
            "opex_total": pd.DataFrame(),
            "ebitda": pd.DataFrame(),
            "output": pd.DataFrame(),
        }
        opex_event = {
            "event_id": "EVT_OPEX",
            "event_type": "opex",
            "period_start": "2014-07-01",
            "period_end": "2014-07-01",
            "country": "France",
            "department": "Marketing",
            "operation": "multiply",
            "value": 1.15,
        }
        result, matches = apply_opex_events(
            artifacts, [opex_event], "test_opex", "test_ebitda"
        )
        self.assertEqual(matches, {"EVT_OPEX": 1})
        marketing = result["department"].loc[
            result["department"]["account"] == "OPEX_MARKETING", "amount"
        ].iloc[0]
        self.assertAlmostEqual(marketing, 115.0)
        self.assertAlmostEqual(result["opex_total"]["amount"].iloc[0], 315.0)
        self.assertAlmostEqual(result["ebitda"]["amount"].iloc[0], 685.0)


if __name__ == "__main__":
    unittest.main()
