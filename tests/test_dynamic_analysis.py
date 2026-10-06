from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


COMPONENT_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT_PATH)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy.economic_optimizer import PricePoint
from foxcat_energy.engine.modes import evaluate_mode
from foxcat_energy.engine.models import EnergySnapshot, SolarForecast
from foxcat_energy.migration import migrate_settings_v171
from foxcat_energy.price_analyzer import (
    AFTER_FAVORABLE_WINDOW,
    IN_FAVORABLE_WINDOW,
    PREDICTIVE,
    REACTIVE,
    analyze_price_curve,
)


class DynamicAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 1, 2, 12, tzinfo=timezone.utc)
        self.settings = {
            "dynamic_favorable_position_pct": 30,
            "dynamic_high_position_pct": 70,
            "dynamic_favorable_max_hours": 2,
        }

    def _hourly(self, start: datetime, prices: list[float]) -> list[PricePoint]:
        return [
            PricePoint(start + timedelta(hours=index), price, "test")
            for index, price in enumerate(prices)
        ]

    def test_analyzer_reports_windows_peaks_and_best_slots(self) -> None:
        points = self._hourly(
            self.now - timedelta(hours=1),
            [0.4, 0.1, 0.8, 0.2, 0.9, 0.3, 0.2, 0.6, 0.1, 0.7, 0.4, 0.3, 0.2] * 3,
        )
        result = analyze_price_curve(
            now=self.now,
            import_points=points,
            settings=self.settings,
            current_buy=0.1,
        )

        self.assertTrue(result["active"])
        self.assertEqual(result["state"], IN_FAVORABLE_WINDOW)
        self.assertIsNotNone(result["next_peak"])
        self.assertIsNotNone(result["best_remaining_today"])
        self.assertIsNotNone(result["best_tomorrow"])
        self.assertLessEqual(result["favorable_selected_hours_today"], 2)

    def test_missing_tomorrow_data_stays_reactive(self) -> None:
        points = self._hourly(self.now - timedelta(minutes=30), [0.2, 0.3, 0.1])
        result = analyze_price_curve(
            now=self.now,
            import_points=points,
            settings=self.settings,
            tomorrow_available=True,
        )

        self.assertEqual(result["mode"], REACTIVE)
        self.assertFalse(result["tomorrow"]["available"])

    def test_valid_tomorrow_data_enables_predictive_mode(self) -> None:
        points = self._hourly(self.now, [0.2] * 25)
        result = analyze_price_curve(
            now=self.now,
            import_points=points,
            settings=self.settings,
            tomorrow_available=True,
        )

        self.assertEqual(result["mode"], PREDICTIVE)
        self.assertTrue(result["tomorrow"]["available"])

    def test_no_future_favorable_window_is_after_state(self) -> None:
        points = self._hourly(self.now, [0.1] * 12)
        result = analyze_price_curve(
            now=self.now + timedelta(hours=1),
            import_points=points,
            settings=self.settings,
        )

        self.assertEqual(result["state"], AFTER_FAVORABLE_WINDOW)

    def test_dynamic_legacy_mode_migrates_to_eco_not_manual(self) -> None:
        migrated, notes = migrate_settings_v171({"mode": "Dynamique"})

        self.assertEqual(migrated["mode"], "Éco")
        self.assertEqual(migrated["price_source"], "Dynamique Day-Ahead")
        self.assertEqual(migrated["legacy_mode_v160"], "Dynamique")
        self.assertTrue(notes)

    def test_comfort_uses_the_eco_boiler_strategy(self) -> None:
        snapshot = EnergySnapshot(
            timestamp=self.now,
            pv_w=0,
            house_w=300,
            export_w=0,
            import_w=300,
            grid_net_w=300,
            boiler_temp_c=45,
            boiler_safety_temp_c=45,
            boiler_power_w=0,
            inverter_power_w=0,
            boiler_on=False,
            boiler_setpoint_c=45,
            machine_active=False,
        )
        settings = {
            "boiler_temp_normal_c": 45,
            "boiler_temp_start_c": 43,
            "boiler_temp_boost_c": 65,
            "boiler_temp_safety_c": 68,
            "boiler_power_w": 1800,
            "boiler_cycle_min_s": 120,
            "boiler_enabled": True,
            "boiler_allow_hc": True,
        }
        comfort = evaluate_mode(
            "Confort", snapshot, snapshot, settings, self.now, 0, "AUCUNE", {}, SolarForecast()
        )

        self.assertIn("Économie énergie", comfort.reason)


if __name__ == "__main__":
    unittest.main()
