"""Décalage de consigne : calcul à chaque trame seulement si la fonction est activée (ou à rétablir)."""
from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy import heating_boost as hb  # noqa: E402

CFG = hb.HeatingBoostConfig(enabled=True, only_when_empty=False)


def inputs(**kwargs):
    base = dict(regulation_active=True, snapshot_valid=True, export_w=0.0, import_w=0.0, presence=0)
    base.update(kwargs)
    return hb.HeatingBoostInputs(**base)


class NeedsRunTests(unittest.TestCase):
    def test_enabled_function_runs_on_every_frame(self):
        self.assertTrue(hb.needs_run(enabled=True, steps=0, last_enabled=True))

    def test_piege_disabled_and_idle_does_nothing(self):
        self.assertFalse(hb.needs_run(enabled=False, steps=0, last_enabled=False))

    def test_disabling_while_an_offset_is_granted_still_runs_to_return_to_zero(self):
        self.assertTrue(hb.needs_run(enabled=False, steps=2, last_enabled=True))

    def test_disabling_with_a_remembered_setpoint_runs_to_restore_it(self):
        self.assertTrue(hb.needs_run(enabled=False, steps=0, has_tracks=True))

    def test_a_system_still_holding_steps_keeps_running(self):
        self.assertTrue(hb.needs_run(enabled=False, steps=0, system_steps=(0, 1)))

    def test_the_switch_itself_triggers_one_run_to_refresh_the_status(self):
        self.assertTrue(hb.needs_run(enabled=False, steps=0, last_enabled=True))   # vient d'être coupée
        self.assertTrue(hb.needs_run(enabled=True, steps=0, last_enabled=False))   # vient d'être activée

    def test_after_the_last_run_a_disabled_function_goes_back_to_sleep(self):
        self.assertFalse(hb.needs_run(enabled=False, steps=0, system_steps=(0, 0), has_tracks=False, last_enabled=False))


class FrameByFrameTests(unittest.TestCase):
    """Le calcul est pur : appelé à chaque trame, il suit le surplus sans retard."""

    def test_offset_follows_the_surplus_frame_after_frame(self):
        cfg = hb.HeatingBoostConfig(enabled=True, only_when_empty=False, hold_s=0.0, surplus_per_step_w=500.0, step_c=1.0, max_c=2.0)
        state, now = hb.HeatingBoostState(), 1000.0
        trace = []
        for export_w in (0.0, 700.0, 1300.0, 1300.0, 400.0):
            result = hb.evaluate(cfg, state, inputs(export_w=export_w), now)
            state, now = result.state, now + 30.0
            trace.append(result.steps)
        self.assertEqual(trace, [0, 1, 2, 2, 1])      # 400 W : surplus 300 W = 60 % du seuil, le premier pas est conservé

    def test_import_spike_drops_the_offset_on_the_very_next_frame(self):
        cfg = hb.HeatingBoostConfig(enabled=True, only_when_empty=False, hold_s=0.0, surplus_per_step_w=500.0, step_c=1.0)
        state = hb.evaluate(cfg, hb.HeatingBoostState(), inputs(export_w=1200.0), 1000.0).state
        self.assertEqual(state.steps, 2)
        result = hb.evaluate(cfg, state, inputs(export_w=0.0, import_w=900.0), 1030.0)
        self.assertEqual(result.steps, 0)
        self.assertIn("baisse immédiate", result.reason)


class StatusMessageTests(unittest.TestCase):
    def test_piege_no_immediate_drop_message_when_the_offset_is_already_zero(self):
        result = hb.evaluate(CFG, hb.HeatingBoostState(), inputs(import_w=314.0), 1000.0)
        self.assertEqual(result.steps, 0)
        self.assertNotIn("baisse immédiate", result.reason)
        self.assertIn("pas d'augmentation", result.reason)

    def test_real_drop_keeps_its_message(self):
        cfg = hb.HeatingBoostConfig(enabled=True, only_when_empty=False, hold_s=0.0, surplus_per_step_w=500.0)
        state = hb.evaluate(cfg, hb.HeatingBoostState(), inputs(export_w=700.0), 1000.0).state
        result = hb.evaluate(cfg, state, inputs(export_w=0.0, import_w=400.0), 1030.0)
        self.assertIn("baisse immédiate", result.reason)


if __name__ == "__main__":
    unittest.main()
