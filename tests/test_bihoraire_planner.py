"""Planificateur bi-horaire : cycles complets placés en heures creuses."""
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
from foxcat_energy.domain.pricing.bihoraire_planner import build_bihoraire_plan  # noqa: E402
from foxcat_energy.domain.pricing.dynamic_planner import CONTINUE, SAFETY_OVERRIDE, START_NOW, USER_CONTROL, WAIT  # noqa: E402

DAY = datetime(2026, 11, 16, 0, 0, tzinfo=timezone.utc)
# HP 07-11 et 17-22 (défaut) : HC 11-17 et 22-07.
SETTINGS = dict(DEFAULT_SETTINGS, mode="Éco")


def snap(export_w=0.0):
    return EnergySnapshot(
        timestamp=DAY, pv_w=0.0, house_w=500.0, export_w=export_w, import_w=500.0, grid_net_w=-500.0,
        boiler_temp_c=50.0, boiler_safety_temp_c=50.0, boiler_power_w=0.0, inverter_power_w=0.0,
        boiler_on=False, boiler_setpoint_c=45.0, machine_active=False,
    )


def machine(**kw):
    base = dict(machine_id="wash", name="Lave-linge", switch_entity="switch.x", on_1="06:00", off_1="05:00",
                on_2="00:00", off_2="00:00", cycle_duration_minutes=120.0, nominal_power_w=2000.0)
    base.update(kw)
    return MachineDefinition(**base)


def plan(hour, minute=0, machines=None, hp=0.35, hc=0.25, **kw):
    now = DAY + timedelta(hours=hour, minutes=minute)
    args = dict(now=now, snapshot=snap(), settings=SETTINGS, bihoraire_active=True, hp_price=hp, hc_price=hc,
                export_points=[], machines=machines or [machine()], learning={}, cycles={})
    args.update(kw)
    return build_bihoraire_plan(**args)


class BihorairePlannerTests(unittest.TestCase):
    def test_inactive_outside_bihoraire(self):
        self.assertFalse(plan(8, bihoraire_active=False)["active"])

    def test_missing_price_not_ready(self):
        result = plan(8, hc=None)
        self.assertTrue(result["active"])
        self.assertFalse(result["ready"])

    def test_waits_for_hc_during_hp(self):
        result = plan(8)
        entry = result["machines"]["wash"]
        self.assertEqual(result["period"], "HP")
        self.assertEqual(entry["decision"], WAIT)
        self.assertTrue(entry["planned_start"].startswith("2026-11-16T11:00"))
        self.assertEqual(entry["planned_band"], "HC")
        self.assertEqual(result["next_hc"]["start"][:16], "2026-11-16T11:00")

    def test_starts_now_in_hc_when_cycle_fits(self):
        entry = plan(12)["machines"]["wash"]
        self.assertEqual(entry["decision"], START_NOW)
        self.assertTrue(entry["allow_start_now"])

    def test_cycle_overflowing_into_hp_waits_for_next_hc(self):
        # 16:30 : le cycle de 2 h finirait à 18:30 (1 h 30 en HP) → mieux vaut attendre 22:00.
        entry = plan(16, 30)["machines"]["wash"]
        self.assertEqual(entry["decision"], WAIT)
        self.assertTrue(entry["planned_start"].startswith("2026-11-16T22:00"))

    def test_tiny_spread_never_delays(self):
        entry = plan(8, hp=0.251, hc=0.25)["machines"]["wash"]
        self.assertEqual(entry["decision"], START_NOW)

    def test_equal_prices_note(self):
        self.assertIn("note", plan(8, hp=0.25, hc=0.25))

    def test_window_and_deadline_respected(self):
        m = machine(on_1="22:00", off_1="07:00", on_2="00:00", off_2="00:00", deadline="06:00")
        entry = plan(12, machines=[m])["machines"]["wash"]
        self.assertEqual(entry["decision"], WAIT)
        start = datetime.fromisoformat(entry["planned_start"])
        self.assertGreaterEqual(start, DAY + timedelta(hours=22))
        self.assertLessEqual(start + timedelta(hours=2), DAY + timedelta(days=1, hours=6))

    def test_protected_cycle_continues(self):
        cycles = {"wash": {"protected": True, "expected_end_at": (DAY + timedelta(hours=9)).isoformat()}}
        entry = plan(8, cycles=cycles)["machines"]["wash"]
        self.assertEqual(entry["decision"], CONTINUE)
        self.assertTrue(entry["allow_start_now"])

    def test_peak_shaving_and_manual(self):
        self.assertEqual(plan(12, peak_shaving_active=True)["machines"]["wash"]["decision"], SAFETY_OVERRIDE)
        manual = plan(8, settings=dict(SETTINGS, mode="Manuel"))["machines"]["wash"]
        self.assertEqual(manual["decision"], USER_CONTROL)
        self.assertFalse(manual["allow_start_now"])

    def test_periods_listed(self):
        periods = plan(8)["periods"]
        self.assertEqual([p["period"] for p in periods[:3]], ["HP", "HC", "HP"])


if __name__ == "__main__":
    unittest.main()
