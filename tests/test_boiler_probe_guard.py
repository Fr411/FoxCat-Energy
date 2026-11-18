"""Sonde du boiler indisponible : chauffe interdite, reprise après retour stable."""
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

from foxcat_energy.const import BOILER_BOOST_65, BOILER_HEAT_45, BOILER_NONE, BOILER_STOP  # noqa: E402
from foxcat_energy.domain.engine import boiler_probe as bp  # noqa: E402

T0 = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


class GuardTests(unittest.TestCase):
    def test_healthy_probe_never_blocks(self):
        guard = bp.BoilerProbeGuard()
        for t in (0, 30, 60):
            self.assertIsNone(guard.observe(True, at(t)))
        self.assertFalse(guard.blocked)

    def test_probe_loss_blocks_immediately_without_delay(self):
        guard = bp.BoilerProbeGuard()
        self.assertEqual(guard.observe(False, at(0)), bp.TRANSITION_BLOCKED)
        self.assertTrue(guard.blocked)
        self.assertIsNone(guard.observe(False, at(30)))     # pas de transition répétée

    def test_release_only_after_a_stable_minute(self):
        guard = bp.BoilerProbeGuard(recover_after_s=60.0)
        guard.observe(False, at(0))
        self.assertIsNone(guard.observe(True, at(10)))
        self.assertTrue(guard.blocked)
        self.assertIsNone(guard.observe(True, at(69)))
        self.assertTrue(guard.blocked)
        self.assertEqual(guard.observe(True, at(71)), bp.TRANSITION_RELEASED)
        self.assertFalse(guard.blocked)

    def test_piege_unstable_probe_restarts_the_countdown(self):
        guard = bp.BoilerProbeGuard(recover_after_s=60.0)
        guard.observe(False, at(0))
        guard.observe(True, at(10))
        guard.observe(False, at(50))                         # rechute
        self.assertIsNone(guard.observe(True, at(60)))
        self.assertIsNone(guard.observe(True, at(110)))      # 50 s seulement depuis la rechute
        self.assertTrue(guard.blocked)
        self.assertEqual(guard.observe(True, at(121)), bp.TRANSITION_RELEASED)

    def test_second_loss_after_release_blocks_again(self):
        guard = bp.BoilerProbeGuard(recover_after_s=0.0)
        guard.observe(False, at(0))
        guard.observe(True, at(1))
        self.assertFalse(guard.blocked)
        self.assertEqual(guard.observe(False, at(2)), bp.TRANSITION_BLOCKED)


class ActionTests(unittest.TestCase):
    def test_every_heating_action_is_recognised_and_stop_is_never_blocked(self):
        self.assertTrue(bp.is_heating_action(BOILER_HEAT_45))
        self.assertTrue(bp.is_heating_action(BOILER_BOOST_65))
        self.assertFalse(bp.is_heating_action(BOILER_STOP))
        self.assertFalse(bp.is_heating_action(BOILER_NONE))


if __name__ == "__main__":
    unittest.main()
