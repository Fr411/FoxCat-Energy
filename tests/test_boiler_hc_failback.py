from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path

COMPONENT_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT_PATH)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy.const import BOILER_HEAT_45, BOILER_NONE, DEFAULT_SETTINGS, MODE_ECO, TARIFF_TOU
from foxcat_energy.domain.engine.modes.ecs_solar import evaluate_ecs_solar
from foxcat_energy.domain.engine.models import EnergySnapshot
from foxcat_energy.domain.engine.modes.common import ecs_last_departure
from foxcat_energy.domain.engine.modes.eco import evaluate_eco


def snap(temp, on=False):
    return EnergySnapshot(
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc), pv_w=0, house_w=300, export_w=0,
        import_w=300, grid_net_w=-300, boiler_temp_c=temp, boiler_safety_temp_c=temp,
        boiler_power_w=1800, inverter_power_w=4000, boiler_on=on, boiler_setpoint_c=45,
        machine_active=False,
    )


def at(h, m=0):
    return datetime(2026, 1, 1, h, m)


class HcFailbackTests(unittest.TestCase):
    def settings(self, **kw):
        s = dict(DEFAULT_SETTINGS)
        s.update(mode=MODE_ECO, tariff_regime=TARIFF_TOU, **kw)
        return s

    def test_margin_moves_failback_earlier(self):
        s = self.settings()
        t = at(5, 0)
        late = ecs_last_departure(snap(43), dict(s, boiler_failback_margin_min=0), t)
        early = ecs_last_departure(snap(43), dict(s, boiler_failback_margin_min=180), t)
        self.assertFalse(late)
        self.assertTrue(early)

    def test_eco_option_off_heats_immediately(self):
        s = self.settings(boiler_hc_wait_failback=False)
        self.assertEqual(evaluate_eco(snap(41), snap(41), s, at(23, 0), 0.0, "NONE").action, BOILER_HEAT_45)

    def test_ecs_initial_night_charge_waits(self):
        r = evaluate_ecs_solar(snap(41), snap(41), self.settings(), at(23, 5), 0.0, "NONE")
        self.assertEqual(r.action, BOILER_NONE)
        s = self.settings(boiler_hc_wait_failback=False)
        self.assertEqual(evaluate_ecs_solar(snap(41), snap(41), s, at(23, 5), 0.0, "NONE").action, BOILER_HEAT_45)

    def test_ecs_night_failback_heats(self):
        r = evaluate_ecs_solar(snap(41), snap(41), self.settings(), at(6, 15), 0.0, "NONE")
        self.assertEqual(r.action, BOILER_HEAT_45)

    def test_eco_waits_then_heats(self):
        args = (snap(41), snap(41), self.settings(), at(23, 0), 0.0, "NONE")
        self.assertEqual(evaluate_eco(*args).action, BOILER_NONE)
        args = (snap(41), snap(41), self.settings(), at(6, 15), 0.0, "NONE")
        self.assertEqual(evaluate_eco(*args).action, BOILER_HEAT_45)


if __name__ == "__main__":
    unittest.main()
