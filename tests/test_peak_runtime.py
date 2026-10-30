"""Écrêtage : vérifie le coordinateur réellement chargé, ignoré si HA n'est pas installé."""
import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
HAS_HOME_ASSISTANT = importlib.util.find_spec("homeassistant") is not None

if HAS_HOME_ASSISTANT:
    package = types.ModuleType("foxcat_energy")
    package.__path__ = [str(COMPONENT)]
    sys.modules.setdefault("foxcat_energy", package)
    from foxcat_energy.runtime import coordinator as rc

    Coordinator = rc.FoxCatEnergyCoordinator


def run(coroutine):
    return asyncio.run(coroutine)


def snapshot(house_w=1000.0, import_w=None, valid=True, boiler_on=False):
    return SimpleNamespace(
        valid=valid,
        house_w=house_w,
        import_w=house_w if import_w is None else import_w,
        pv_w=0.0,
        boiler_on=boiler_on,
    )


def coordinator(mode="Éco", active=False, **settings):
    fake = MagicMock()
    fake.settings = {"high_load_shed_enabled": True, "mode": mode, "regulation_active": True, **settings}
    fake.config = {}
    fake.load_shed_state = {"active": active}
    fake.v2h_state = {}
    fake._high_load_high_frames = 0
    fake._high_load_low_frames = 0
    fake._pri_task = None
    fake._peak_config = lambda: Coordinator._peak_config(fake)
    fake._activate_high_load_shed = lambda *args: Coordinator._activate_high_load_shed(fake, *args)
    fake._evaluate_v2h = AsyncMock()
    fake.async_reconcile_machines = AsyncMock()
    fake.async_command_boiler = AsyncMock()
    return fake


def evaluate(fake, *snapshots):
    for item in snapshots:
        run(Coordinator._evaluate_high_load(fake, item))


@unittest.skipUnless(HAS_HOME_ASSISTANT, "Home Assistant non installé")
class TriggerTests(unittest.TestCase):
    def test_defaults_match_historic_behaviour(self) -> None:
        fake = coordinator(main_breaker_current_a=25)
        evaluate(fake, snapshot(5174.0))
        self.assertFalse(fake.load_shed_state["active"])
        evaluate(fake, snapshot(5175.0))
        self.assertTrue(fake.load_shed_state["active"])
        fake._queue_pri_target.assert_called_once()
        evaluate(fake, *[snapshot(3000.0)] * 4)
        self.assertTrue(fake.load_shed_state["active"])
        evaluate(fake, snapshot(3000.0))
        self.assertFalse(fake.load_shed_state["active"])

    def test_trigger_ratio_and_phases_move_the_threshold(self) -> None:
        fake = coordinator(main_breaker_current_a=25, peak_trigger_ratio_pct=80, peak_phases=3)
        evaluate(fake, snapshot(13799.0))
        self.assertFalse(fake.load_shed_state["active"])
        evaluate(fake, snapshot(13800.0))
        self.assertTrue(fake.load_shed_state["active"])

    def test_grid_import_basis_ignores_load_covered_by_solar(self) -> None:
        fake = coordinator(main_breaker_current_a=25, peak_measure_basis="grid_import")
        evaluate(fake, snapshot(8000.0, import_w=2000.0))
        self.assertFalse(fake.load_shed_state["active"])
        evaluate(fake, snapshot(8000.0, import_w=6000.0))
        self.assertTrue(fake.load_shed_state["active"])
        self.assertEqual(fake.load_shed_state["basis"], "grid_import")

    def test_confirm_and_release_frames_are_configurable(self) -> None:
        fake = coordinator(main_breaker_current_a=25, peak_confirm_frames=3, peak_release_frames=2)
        evaluate(fake, snapshot(6000.0), snapshot(6000.0))
        self.assertFalse(fake.load_shed_state["active"])
        evaluate(fake, snapshot(6000.0))
        self.assertTrue(fake.load_shed_state["active"])
        evaluate(fake, snapshot(1000.0))
        self.assertTrue(fake.load_shed_state["active"])
        evaluate(fake, snapshot(1000.0))
        self.assertFalse(fake.load_shed_state["active"])

    def test_disabled_inverter_release_leaves_inverter_alone(self) -> None:
        fake = coordinator(main_breaker_current_a=25, peak_release_inverter=False)
        evaluate(fake, snapshot(6000.0))
        self.assertTrue(fake.load_shed_state["active"])
        fake._queue_pri_target.assert_not_called()

    def test_boiler_is_kept_when_shedding_it_is_disabled(self) -> None:
        fake = coordinator(main_breaker_current_a=25, peak_shed_boiler=False)
        evaluate(fake, snapshot(6000.0, boiler_on=True))
        fake.async_command_boiler.assert_not_called()
        fake = coordinator(main_breaker_current_a=25)
        evaluate(fake, snapshot(6000.0, boiler_on=True))
        fake.async_command_boiler.assert_called_once()


@unittest.skipUnless(HAS_HOME_ASSISTANT, "Home Assistant non installé")
class V2HTests(unittest.TestCase):
    def evaluate(self, item, *, active=True, **settings):
        fake = coordinator(active=active, main_breaker_current_a=25, **settings)
        fake.config = {
            rc.CONF_EV_V2H_ENABLED: True,
            rc.CONF_EV_V2H_SWITCH: "switch.v2h",
            rc.CONF_EV_SOC_SENSOR: "sensor.soc",
        }
        fake._optional_float_state.return_value = 80.0
        fake.prices.return_value = {"status": "NORMAL"}
        fake.hass.states.get.return_value = SimpleNamespace(state="off")
        fake.hass.services.async_call = AsyncMock()
        run(Coordinator._evaluate_v2h(fake, item))
        return fake

    def test_active_shed_discharges_down_to_the_configured_target(self) -> None:
        fake = self.evaluate(snapshot(6000.0), peak_v2h_target_ratio_pct=70)
        self.assertTrue(fake.v2h_state["active"])
        self.assertAlmostEqual(fake.v2h_state["target_power_w"], 6000.0 - 5750.0 * 0.7)
        fake.hass.services.async_call.assert_awaited_once()

    def test_assist_can_be_disabled(self) -> None:
        fake = self.evaluate(snapshot(6000.0), peak_v2h_assist=False)
        self.assertFalse(fake.v2h_state["active"])
        fake.hass.services.async_call.assert_not_awaited()

    def test_no_discharge_while_the_shed_is_not_active(self) -> None:
        self.assertFalse(self.evaluate(snapshot(6000.0), active=False).v2h_state["active"])

    def test_grid_import_basis_reaches_the_decision(self) -> None:
        fake = self.evaluate(snapshot(8000.0, import_w=6000.0), peak_measure_basis="grid_import")
        self.assertAlmostEqual(fake.v2h_state["target_power_w"], 6000.0 - 5750.0 * 0.8)


@unittest.skipUnless(HAS_HOME_ASSISTANT, "Home Assistant non installé")
class MachineTests(unittest.TestCase):
    def reconcile(self, *, sheddable=True, socket="off", allow=False, cycle=False, **settings):
        fake = coordinator(active=True, **settings)
        fake.machines = [SimpleNamespace(
            machine_id="m", name="M", switch_entity="switch.m", setting_key="auto_m",
            automatic_default=True, sheddable=sheddable,
        )]
        fake.machine_cycle_manager.is_protected.return_value = cycle
        fake._economic_view.return_value = {"planner": {"machines": {"m": {"allow_start_now": allow}}}}
        fake.hass.states.get.return_value = SimpleNamespace(state=socket)
        fake.hass.services.async_call = AsyncMock()
        original = rc.machine_allowed
        rc.machine_allowed = lambda *_: True
        try:
            run(Coordinator.async_reconcile_machines(fake))
        finally:
            rc.machine_allowed = original
        return fake.hass.services.async_call.await_args.args[1]

    def test_sheddable_machine_is_cut(self) -> None:
        self.assertEqual(self.reconcile(socket="on"), "turn_off")

    def test_protected_cycle_is_never_cut(self) -> None:
        self.assertEqual(self.reconcile(socket="on", cycle=True), "turn_on")

    def test_non_sheddable_running_machine_keeps_running(self) -> None:
        self.assertEqual(self.reconcile(sheddable=False, socket="on"), "turn_on")

    def test_non_sheddable_idle_machine_does_not_start_when_planner_blocks(self) -> None:
        self.assertEqual(self.reconcile(sheddable=False, socket="off"), "turn_off")

    def test_disabled_shedding_keeps_running_machines(self) -> None:
        self.assertEqual(self.reconcile(socket="on", peak_shed_machines=False), "turn_on")

    def test_sheddable_machine_cannot_restart_even_if_the_planner_allows_it(self) -> None:
        self.assertEqual(self.reconcile(allow=True), "turn_off")


if __name__ == "__main__":
    unittest.main()
