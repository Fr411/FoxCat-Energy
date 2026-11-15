"""Coupure Internet : tampon local des prix de bourse et repli confort du boiler."""
from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy.const import BOILER_HEAT_45, BOILER_NONE, BOILER_STOP  # noqa: E402
from foxcat_energy.domain.engine.models import BoilerIntent, EnergySnapshot  # noqa: E402
from foxcat_energy.domain.engine.modes.dynamic_boiler_v2 import evaluate_dynamic_boiler_v2  # noqa: E402
from foxcat_energy.domain.pricing import price_buffer as pb  # noqa: E402

UTC = timezone.utc
NOW = datetime(2026, 11, 15, 18, 20, tzinfo=UTC)


def hourly_store(start: datetime, hours: int, price: float = 0.20) -> dict[str, float]:
    return {(start + timedelta(hours=h)).isoformat(): price + h / 100 for h in range(hours)}


class PriceBufferTests(unittest.TestCase):
    def setUp(self):
        # Prix reçus à 14 h : tranches de 14 h aujourd'hui jusqu'à 23 h demain.
        self.store = hourly_store(datetime(2026, 11, 15, 14, 0, tzinfo=UTC), 34)

    def test_current_price_is_the_slot_started_before_now(self):
        self.assertAlmostEqual(pb.current_price(self.store, NOW), 0.24)   # tranche 18 h

    def test_current_price_is_unknown_when_the_buffer_is_stale(self):
        later = NOW + timedelta(days=3)
        self.assertIsNone(pb.current_price(self.store, later))

    def test_next_price_is_first_future_slot(self):
        self.assertAlmostEqual(pb.next_price(self.store, NOW), 0.25)

    def test_covered_until_is_end_of_last_slot(self):
        end = pb.covered_until(self.store, NOW)
        self.assertEqual(end, datetime(2026, 11, 16, 23, 0, tzinfo=UTC) + timedelta(hours=1))

    def test_quarter_hour_series_uses_its_own_step(self):
        store = {(NOW + timedelta(minutes=15 * i)).isoformat(): 0.1 for i in range(4)}
        self.assertEqual(pb.covered_until(store, NOW), NOW + timedelta(minutes=60))

    def test_prune_drops_old_and_far_points(self):
        store = dict(self.store)
        store["2026-11-15T08:00:00+00:00"] = 0.1          # trop ancien (> 3 h de passé)
        store["2026-12-30T00:00:00+00:00"] = 0.1          # au-delà de l'horizon
        self.assertTrue(pb.prune(store, NOW, 36))
        self.assertNotIn("2026-11-15T08:00:00+00:00", store)
        self.assertNotIn("2026-12-30T00:00:00+00:00", store)
        self.assertFalse(pb.prune(store, NOW, 36))

    def test_garbage_is_ignored(self):
        store = {"pas une date": 0.1, NOW.isoformat(): "abc"}
        self.assertIsNone(pb.current_price(store, NOW))
        self.assertIsNone(pb.covered_until({"pas une date": 1}, NOW))


class FeedStatusTests(unittest.TestCase):
    def setUp(self):
        self.store = hourly_store(datetime(2026, 11, 15, 14, 0, tzinfo=UTC), 34)

    def test_live_when_the_provider_answers(self):
        feed = pb.feed_status(uses_market_prices=True, live_ok=True, store=self.store, now=NOW)
        self.assertEqual(feed["state"], pb.FEED_LIVE)

    def test_offline_with_buffer_keeps_running_on_cached_prices(self):
        feed = pb.feed_status(uses_market_prices=True, live_ok=False, store=self.store, now=NOW)
        self.assertEqual(feed["state"], pb.FEED_BUFFER)
        self.assertGreater(feed["hours_left"], 24)

    def test_offline_after_48h_falls_back_to_degraded(self):
        feed = pb.feed_status(
            uses_market_prices=True, live_ok=False, store=self.store, now=NOW + timedelta(hours=48)
        )
        self.assertEqual(feed["state"], pb.FEED_DEGRADED)
        self.assertEqual(feed["hours_left"], 0.0)

    def test_empty_buffer_is_degraded(self):
        feed = pb.feed_status(uses_market_prices=True, live_ok=False, store={}, now=NOW)
        self.assertEqual(feed["state"], pb.FEED_DEGRADED)

    def test_fixed_contract_never_needs_internet(self):
        feed = pb.feed_status(uses_market_prices=False, live_ok=False, store={}, now=NOW)
        self.assertEqual(feed["state"], pb.FEED_LOCAL)


def snapshot(temp: float, *, on: bool = False, export_w: float = 0.0) -> EnergySnapshot:
    return EnergySnapshot(
        timestamp=NOW, pv_w=0.0, house_w=500.0, export_w=export_w, import_w=500.0, grid_net_w=-500.0,
        boiler_temp_c=temp, boiler_safety_temp_c=temp, boiler_power_w=0.0, inverter_power_w=0.0,
        boiler_on=on, boiler_setpoint_c=45.0, machine_active=False,
    )


SETTINGS = {
    "mode": "Dynamique", "price_source": "Dynamique", "tariff_regime": "Dynamique",
    "boiler_temp_normal_c": 45.0, "boiler_temp_start_c": 43.0, "boiler_temp_boost_c": 65.0,
    "boiler_temp_safety_c": 68.0, "boiler_power_w": 1800.0,
}


class BoilerWithoutPricesTests(unittest.TestCase):
    """Sans prix (coupure, tampon épuisé) : l'eau chaude reste assurée, sans BOOST réseau."""

    def run_boiler(self, temp, on=False):
        base = BoilerIntent(BOILER_NONE, "base", "AUCUNE")
        return evaluate_dynamic_boiler_v2(snapshot(temp, on=on), base, SETTINGS, {"decision": {}})

    def test_cold_tank_is_heated_to_comfort(self):
        intent = self.run_boiler(40.0)
        self.assertEqual(intent.action, BOILER_HEAT_45)
        self.assertEqual(intent.origin, "DYNAMIC_REPLI_CONFORT")

    def test_heating_continues_between_restart_and_comfort(self):
        self.assertEqual(self.run_boiler(44.0, on=True).action, BOILER_HEAT_45)

    def test_comfort_reached_stops_the_grid_heating(self):
        self.assertEqual(self.run_boiler(45.5, on=True).action, BOILER_STOP)

    def test_warm_tank_is_left_alone(self):
        self.assertEqual(self.run_boiler(44.0, on=False).action, BOILER_NONE)


if __name__ == "__main__":
    unittest.main()
