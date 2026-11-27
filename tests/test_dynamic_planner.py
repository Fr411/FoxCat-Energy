"""Planificateur dynamique : créneaux les moins chers, bandes, stabilité, sécurités."""
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

from foxcat_energy.const import DEFAULT_SETTINGS  # noqa: E402
from foxcat_energy.domain.engine.models import EnergySnapshot  # noqa: E402
from foxcat_energy.domain.loads.machines import MachineDefinition  # noqa: E402
from foxcat_energy.domain.pricing.dynamic_planner import (  # noqa: E402
    BAND_NEGATIVE, BAND_PEAK, BAND_VERY_LOW, CONTINUE, SAFETY_OVERRIDE, START_NOW, USER_CONTROL, WAIT,
    build_dynamic_plan, build_slots, classify,
)
from foxcat_energy.domain.pricing.economic_optimizer import PricePoint  # noqa: E402

UTC = timezone.utc
DAY = datetime(2026, 11, 16, 0, 0, tzinfo=UTC)
SETTINGS = dict(DEFAULT_SETTINGS, mode="Éco")


def snap(now, export_w=0.0):
    return EnergySnapshot(
        timestamp=now, pv_w=0.0, house_w=500.0, export_w=export_w, import_w=500.0, grid_net_w=-500.0,
        boiler_temp_c=50.0, boiler_safety_temp_c=50.0, boiler_power_w=0.0, inverter_power_w=0.0,
        boiler_on=False, boiler_setpoint_c=45.0, machine_active=False,
    )


def curve(prices, step_min=60):
    return [PricePoint(DAY + timedelta(minutes=i * step_min), p, "T") for i, p in enumerate(prices)]


def machine(**kw):
    base = dict(
        machine_id="wash", name="Lave-linge", switch_entity="switch.x", on_1="00:00", off_1="23:59",
        on_2="00:00", off_2="00:00", cycle_duration_minutes=120.0, nominal_power_w=2000.0,
    )
    base.update(kw)
    return MachineDefinition(**base)


def plan(now, prices, machines=None, **kw):
    args = dict(
        now=now, snapshot=snap(now), settings=SETTINGS, dynamic_active=True, import_points=curve(prices),
        export_points=[], machines=machines or [machine()], learning={}, cycles={},
    )
    args.update(kw)
    return build_dynamic_plan(**args)


# Nuit creuse 0-5 h, jour moyen, pic 17-20 h
PRICES = [0.10] * 6 + [0.20] * 11 + [0.40] * 3 + [0.22] * 4 + [0.12] * 24


class DynamicPlannerTests(unittest.TestCase):
    def test_inactive_outside_dynamic(self):
        result = plan(DAY, PRICES, dynamic_active=False)
        self.assertFalse(result["active"])

    def test_waits_for_cheap_night(self):
        result = plan(DAY + timedelta(hours=12), PRICES)
        entry = result["machines"]["wash"]
        self.assertEqual(entry["decision"], WAIT)
        self.assertFalse(entry["allow_start_now"])
        self.assertTrue(entry["planned_start"].startswith("2026-11-17T00:00"))
        self.assertGreater(entry["expected_saving_eur"], 0.03)

    def test_starts_now_when_already_cheapest(self):
        entry = plan(DAY + timedelta(hours=1), PRICES)["machines"]["wash"]
        self.assertEqual(entry["decision"], START_NOW)
        self.assertTrue(entry["allow_start_now"])

    def test_small_saving_does_not_delay(self):
        flat = [0.20] * 12 + [0.199] * 24
        entry = plan(DAY + timedelta(hours=10), flat)["machines"]["wash"]
        self.assertEqual(entry["decision"], START_NOW)

    def test_negative_price_starts_immediately(self):
        prices = [0.2] * 5 + [-0.05] * 2 + [0.2] * 30
        result = plan(DAY + timedelta(hours=5), prices, machines=[machine(on_1="00:00", off_1="23:59")])
        self.assertEqual(result["current_band"], BAND_NEGATIVE)
        self.assertEqual(result["machines"]["wash"]["decision"], START_NOW)

    def test_deadline_is_respected(self):
        m = machine(deadline="16:00")
        entry = plan(DAY + timedelta(hours=12), PRICES, machines=[m])["machines"]["wash"]
        start = datetime.fromisoformat(entry["planned_start"])
        self.assertLessEqual(start + timedelta(hours=2), DAY + timedelta(hours=16))

    def test_cycle_must_fit_in_user_window(self):
        m = machine(on_1="21:30", off_1="07:00", on_2="00:00", off_2="00:00")
        entry = plan(DAY + timedelta(hours=12), PRICES, machines=[m])["machines"]["wash"]
        start = datetime.fromisoformat(entry["planned_start"])
        self.assertGreaterEqual(start, DAY + timedelta(days=1))
        self.assertLess(start, DAY + timedelta(days=1, hours=5))

    def test_protected_cycle_continues(self):
        cycles = {"wash": {"protected": True, "expected_end_at": (DAY + timedelta(hours=14)).isoformat()}}
        entry = plan(DAY + timedelta(hours=12), PRICES, cycles=cycles)["machines"]["wash"]
        self.assertEqual(entry["decision"], CONTINUE)
        self.assertTrue(entry["allow_start_now"])

    def test_peak_shaving_blocks_everything(self):
        result = plan(DAY + timedelta(hours=1), PRICES, peak_shaving_active=True)
        self.assertEqual(result["machines"]["wash"]["decision"], SAFETY_OVERRIDE)
        self.assertFalse(result["machines"]["wash"]["allow_start_now"])

    def test_manual_mode_only_recommends(self):
        entry = plan(DAY + timedelta(hours=12), PRICES, settings=dict(SETTINGS, mode="Manuel"))["machines"]["wash"]
        self.assertEqual(entry["decision"], USER_CONTROL)
        self.assertFalse(entry["allow_start_now"])

    def test_two_machines_respect_parallel_power(self):
        a = machine(machine_id="a", name="A", priority=60, nominal_power_w=3000.0)
        b = machine(machine_id="b", name="B", priority=40, nominal_power_w=3000.0)
        settings = dict(SETTINGS, planner_max_parallel_power_w=4000.0, planner_grid_import_limit_w=4000.0)
        result = plan(DAY + timedelta(hours=12), PRICES, machines=[a, b], settings=settings)
        sa, sb = (datetime.fromisoformat(result["machines"][k]["planned_start"]) for k in "ab")
        self.assertGreaterEqual(abs(sa - sb), timedelta(hours=2))

    def test_plan_is_stable_when_alternative_is_barely_better(self):
        first = plan(DAY + timedelta(hours=12), PRICES)
        previous = first["state"]
        tweaked = list(PRICES)
        tweaked[1] = 0.0999  # alternative presque identique, pas de raison de bouger
        again = plan(DAY + timedelta(hours=12), tweaked, previous=previous)
        self.assertEqual(again["machines"]["wash"]["planned_start"], first["machines"]["wash"]["planned_start"])

    def test_interruptible_picks_cheapest_slots(self):
        m = machine(interruptible=True, cycle_duration_minutes=180.0)
        prices = [0.30, 0.10, 0.30, 0.10, 0.30, 0.10] + [0.30] * 30
        entry = plan(DAY, prices, machines=[m])["machines"]["wash"]
        self.assertEqual(len(entry["segments"]), 3)
        self.assertEqual(entry["decision"], WAIT)  # 00:00 est à 0,30 : on attend 01:00
        entry = plan(DAY + timedelta(hours=1), prices, machines=[m])["machines"]["wash"]
        self.assertEqual(entry["decision"], START_NOW)

    def test_bands_and_ranks(self):
        slots = build_slots(curve(PRICES), DAY, DAY + timedelta(hours=36))
        self.assertEqual(slots[0].band, BAND_VERY_LOW)
        self.assertEqual(slots[12].band, "NORMAL")
        self.assertEqual(slots[18].band, BAND_PEAK)
        self.assertEqual(classify(-0.01, 90.0), BAND_NEGATIVE)

    def test_missing_prices_waits(self):
        result = plan(DAY, [])
        self.assertTrue(result["active"])
        self.assertFalse(result["ready"])

    def test_fifteen_minute_curve(self):
        pts = [0.20] * 40 + [0.10] * 8 + [0.20] * 48
        result = plan(DAY + timedelta(hours=8), pts, import_points=curve(pts, 15))
        entry = result["machines"]["wash"]
        self.assertEqual(entry["decision"], WAIT)
        self.assertTrue(entry["planned_start"].startswith("2026-11-16T10:00"))


if __name__ == "__main__":
    unittest.main()
