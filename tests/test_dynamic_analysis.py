from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace


COMPONENT_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT_PATH)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy.domain.pricing.economic_optimizer import PricePoint
from foxcat_energy.runtime.inverter_core import (
    InverterCore,
    NETWORK_BILLED_EXPORT,
    NETWORK_COMPENSATION,
    NETWORK_UNVALUED_EXPORT,
    NETWORK_ZERO_INJECTION,
)
from foxcat_energy.domain.engine.modes import evaluate_mode
from foxcat_energy.domain.engine.models import EnergySnapshot, SolarForecast
from foxcat_energy.runtime.migration import migrate_settings_v171
from foxcat_energy.domain.pricing.price_analyzer import (
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

    def test_network_policy_controls_inverter_export_behavior(self) -> None:
        inverter = InverterCore()
        snapshot = SimpleNamespace(pv_w=4000, export_w=1500, import_w=0)

        compensation = inverter.decide(
            snapshot, 100, {}, NETWORK_COMPENSATION
        )
        remunerated_export = inverter.decide(
            snapshot, 100, {}, NETWORK_BILLED_EXPORT,
            dynamic_export_value_eur_kwh=0.1,
        )
        unvalued_export = inverter.decide(
            snapshot, 100, {}, NETWORK_UNVALUED_EXPORT,
        )
        zero_injection = inverter.decide(
            snapshot, 100, {}, NETWORK_ZERO_INJECTION,
        )

        self.assertEqual(compensation.target_level, 100)
        self.assertEqual(remunerated_export.target_level, 100)
        self.assertLess(unvalued_export.target_level, 100)
        self.assertLess(zero_injection.target_level, 100)


if __name__ == "__main__":
    unittest.main()


class QuarterHourDayAheadTests(unittest.TestCase):
    """A-16 : des prix au quart d'heure ne doivent pas être réduits à leur dernier point."""

    def _points(self, hours: int = 6):
        from datetime import timedelta
        from foxcat_energy.domain.pricing.economic_optimizer import PricePoint

        base = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
        prices = []
        for hour in range(hours):
            prices.extend([0.10 + hour * 0.01, 0.12 + hour * 0.01, 0.30 + hour * 0.01, 0.50 + hour * 0.01])
        return base, [PricePoint(base + timedelta(minutes=15 * i), p, "TEST") for i, p in enumerate(prices)]

    def test_each_hour_is_the_average_of_its_quarter_hours(self):
        from foxcat_energy.domain.pricing.economic_optimizer import _dynamic_day_ahead_points

        base, points = self._points(2)
        hourly = _dynamic_day_ahead_points(points, base)
        self.assertEqual([p.at.hour for p in hourly], [12, 13])
        self.assertAlmostEqual(hourly[0].price, (0.10 + 0.12 + 0.30 + 0.50) / 4)
        self.assertAlmostEqual(hourly[1].price, (0.11 + 0.13 + 0.31 + 0.51) / 4)

    def test_hourly_points_are_unchanged_and_duplicates_collapse(self):
        from foxcat_energy.domain.pricing.economic_optimizer import PricePoint, _dynamic_day_ahead_points

        base = datetime(2026, 11, 15, 12, 0, tzinfo=timezone.utc)
        points = [PricePoint(base, 0.2, "A"), PricePoint(base, 0.4, "B"), PricePoint(base.replace(hour=13), 0.3, "A")]
        hourly = _dynamic_day_ahead_points(points, base)
        self.assertEqual([round(p.price, 3) for p in hourly], [0.4, 0.3])

    def test_consecutive_window_uses_hourly_averages(self):
        from foxcat_energy.domain.pricing.economic_optimizer import _best_consecutive_dynamic_window

        base, points = self._points(6)
        start, end, avg = _best_consecutive_dynamic_window(points, base, 2.0)
        self.assertEqual(start, base)
        self.assertAlmostEqual(avg, ((0.10 + 0.12 + 0.30 + 0.50) / 4 + (0.11 + 0.13 + 0.31 + 0.51) / 4) / 2)

    def test_market_curve_is_built_from_hourly_averages(self):
        from foxcat_energy.domain.pricing.economic_optimizer import evaluate_market

        base, points = self._points(8)
        snapshot = SimpleNamespace(export_w=0.0, import_w=300.0, pv_w=0.0, house_w=300.0)
        prices = {"regime": "Dynamique", "active_buy": 0.30, "export_value": 0.0}
        decision = evaluate_market(
            now=base, snapshot=snapshot, prices=prices, settings={"predictive_pricing_enabled": True},
            import_points=points,
        )
        # Moyennes horaires : 0,255 (12 h, remplacée par le prix courant 0,30) puis 0,265 (13 h) à 0,325 (19 h).
        # Avec le seul dernier quart d'heure de chaque heure, la courbe aurait valu 0,51 à 0,57 €/kWh.
        self.assertAlmostEqual(decision.dynamic_price_min_eur_kwh, 0.265)
        self.assertAlmostEqual(decision.dynamic_price_max_eur_kwh, 0.325)
        self.assertAlmostEqual(decision.dynamic_curve_position_pct, (0.30 - 0.265) / (0.325 - 0.265) * 100.0)


class PriModeTests(unittest.TestCase):
    """A-01 : le PRI doit travailler en Confort comme en Éco, et jamais en Manuel."""

    def test_pri_runs_in_every_automatic_mode_but_not_in_manual(self):
        from foxcat_energy.runtime.inverter_core import pri_mode_allowed

        self.assertTrue(pri_mode_allowed("Éco"))
        self.assertTrue(pri_mode_allowed("Confort"))
        self.assertFalse(pri_mode_allowed("Manuel"))

    def test_zero_injection_policy_reduces_the_inverter_in_comfort_mode_inputs(self):
        # Le moteur ne dépend pas du mode : avec la garde corrigée, Confort obtient la même réduction qu'Éco.
        snapshot = SimpleNamespace(pv_w=3000.0, import_w=0.0, export_w=1200.0, house_w=1800.0)
        settings = {"inverter_power_w": 4000.0}
        decision = InverterCore().decide(snapshot, 100, settings, NETWORK_ZERO_INJECTION, {})
        self.assertLess(decision.target_level, 100)
        self.assertEqual(decision.action, "REDUCTION")

    def test_coordinator_uses_the_shared_mode_rule(self):
        # runtime/coordinator.py exige Home Assistant : on vérifie la source plutôt que de l'importer.
        source = (Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy" / "runtime" / "coordinator.py").read_text(encoding="utf-8")
        guard = source[source.index("def _pri_guard"):source.index("def _rrcr_code")]
        end_solar = source[source.index("async def _check_end_solar"):source.index("async def _watchdog")]
        self.assertIn("pri_mode_allowed(self.settings.get(\"mode\"))", guard)
        self.assertIn("pri_mode_allowed(mode)", end_solar)
        self.assertNotIn("MODE_ZERO", guard + end_solar)
        set_mode = source[source.index("async def async_set_mode"):source.index("async def async_set_pri_manual_level")]
        self.assertIn("async_release_pri_100", set_mode)
