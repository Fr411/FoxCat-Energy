"""Décalage de consigne chauffage : logique pure + branchement du coordinateur."""
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

package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy import heating_boost as hb  # noqa: E402

T0 = 10_000.0


def heating_boost_with_guard(base, guard_w):
    from dataclasses import replace
    return replace(base, guard_power_w=guard_w)


def cfg(**overrides):
    base = {"heating_boost_enabled": True, "heating_only_when_empty": False}
    base.update(overrides)
    return hb.HeatingBoostConfig.from_settings(base)


def inputs(**overrides):
    values = {
        "regulation_active": True,
        "snapshot_valid": True,
        "export_w": 0.0,
        "import_w": 0.0,
        "presence": 0,
        "group_power_w": None,
    }
    values.update(overrides)
    return hb.HeatingBoostInputs(**values)


def state(steps=0, changed_at=None):
    return hb.HeatingBoostState(steps=steps, changed_at=changed_at)


def run(config, current, entries, now=T0):
    return hb.evaluate(config, current, entries, now)


class StopConditionTests(unittest.TestCase):
    def test_disabled_returns_zero(self):
        result = run(cfg(heating_boost_enabled=False), state(2, T0 - 1000), inputs(export_w=5000))
        self.assertEqual((result.offset_c, result.steps), (0.0, 0))
        self.assertEqual(result.state, state())

    def test_regulation_inactive_returns_zero(self):
        result = run(cfg(), state(), inputs(export_w=5000, regulation_active=False))
        self.assertEqual(result.offset_c, 0.0)

    def test_invalid_snapshot_returns_zero(self):
        result = run(cfg(), state(2, T0 - 1000), inputs(export_w=5000, snapshot_valid=False))
        self.assertEqual((result.offset_c, result.steps), (0.0, 0))

    def test_occupied_house_with_only_when_empty_returns_zero(self):
        result = run(cfg(heating_only_when_empty=True), state(), inputs(export_w=5000, presence=2))
        self.assertEqual(result.offset_c, 0.0)
        self.assertIn("occupée", result.reason)

    def test_unknown_presence_counts_as_someone_home(self):
        result = run(cfg(heating_only_when_empty=True), state(), inputs(export_w=5000, presence=None))
        self.assertEqual(result.offset_c, 0.0)
        self.assertIn("inconnue", result.reason)

    def test_empty_house_with_only_when_empty_boosts(self):
        result = run(cfg(heating_only_when_empty=True), state(), inputs(export_w=5000, presence=0))
        self.assertGreater(result.offset_c, 0.0)

    def test_presence_is_ignored_when_only_when_empty_is_off(self):
        result = run(cfg(heating_only_when_empty=False), state(), inputs(export_w=5000, presence=3))
        self.assertGreater(result.offset_c, 0.0)


class StepCalculationTests(unittest.TestCase):
    def test_no_surplus_gives_zero(self):
        self.assertEqual(run(cfg(), state(), inputs(export_w=0.0)).offset_c, 0.0)

    def test_surplus_below_reserve_gives_zero(self):
        self.assertEqual(run(cfg(), state(), inputs(export_w=90.0)).steps, 0)

    def test_steps_are_floor_of_surplus_over_step_power(self):
        # 1100 W - 100 W de réserve = 1000 W -> 2 pas de 500 W -> 1,0 °C.
        result = run(cfg(), state(), inputs(export_w=1100.0))
        self.assertEqual((result.steps, result.offset_c, result.surplus_w), (2, 1.0, 1000.0))
        # 1099 W -> 999 W -> 1 pas seulement.
        self.assertEqual(run(cfg(), state(), inputs(export_w=1099.0)).steps, 1)

    def test_offset_is_capped_at_max(self):
        result = run(cfg(), state(), inputs(export_w=9000.0))
        self.assertEqual((result.steps, result.offset_c), (4, 2.0))

    def test_cap_rounds_down_when_max_is_not_a_multiple_of_step(self):
        result = run(cfg(heating_boost_max_c=1.2), state(), inputs(export_w=9000.0))
        self.assertEqual((result.steps, result.offset_c), (2, 1.0))

    def test_group_power_counts_as_surplus(self):
        # Le groupe consomme déjà 1000 W : export 0 + 1000 - 100 = 900 W -> 1 pas.
        result = run(cfg(), state(), inputs(export_w=0.0, group_power_w=1000.0))
        self.assertEqual((result.steps, result.surplus_w), (1, 900.0))

    def test_custom_step_and_power(self):
        config = cfg(heating_boost_step_c=0.25, heating_surplus_per_step_w=200.0, heating_boost_max_c=1.0)
        result = run(config, state(), inputs(export_w=700.0))
        self.assertEqual((result.steps, result.offset_c), (3, 0.75))


class HysteresisTests(unittest.TestCase):
    def test_granted_step_is_kept_down_to_sixty_percent_of_its_threshold(self):
        # 2 pas accordés (seuil 1000 W) : conservés tant que surplus >= 600 W.
        kept = run(cfg(), state(2, T0 - 1000), inputs(export_w=700.0))  # surplus 600 W
        self.assertEqual(kept.steps, 2)
        dropped = run(cfg(), state(2, T0 - 1000), inputs(export_w=699.0))  # surplus 599 W
        self.assertEqual(dropped.steps, 1)

    def test_hysteresis_only_protects_granted_steps(self):
        # Surplus 400 W : 0 pas demandé, mais le pas 1 (seuil 500 W, 60 % = 300 W) est conservé.
        self.assertEqual(run(cfg(), state(1, T0 - 1000), inputs(export_w=500.0)).steps, 1)
        # Sans pas accordé, 400 W ne suffit pas à en obtenir un.
        self.assertEqual(run(cfg(), state(0, T0 - 1000), inputs(export_w=500.0)).steps, 0)

    def test_decrease_by_hysteresis_is_not_delayed_by_hold(self):
        result = run(cfg(), state(2, T0 - 5), inputs(export_w=0.0))
        self.assertEqual(result.steps, 0)


class AntiYoyoTests(unittest.TestCase):
    def test_increase_waits_for_hold_after_last_change(self):
        held = run(cfg(), state(1, T0 - 299), inputs(export_w=5000.0))
        self.assertEqual(held.steps, 1)
        self.assertEqual(held.state.changed_at, T0 - 299)
        released = run(cfg(), state(1, T0 - 300), inputs(export_w=5000.0))
        self.assertEqual(released.steps, 4)
        self.assertEqual(released.state.changed_at, T0)

    def test_first_increase_is_immediate(self):
        self.assertEqual(run(cfg(), state(0, None), inputs(export_w=5000.0)).steps, 4)

    def test_hold_is_configurable(self):
        config = cfg(heating_hold_s=60.0)
        self.assertEqual(run(config, state(1, T0 - 59), inputs(export_w=5000.0)).steps, 1)
        self.assertEqual(run(config, state(1, T0 - 60), inputs(export_w=5000.0)).steps, 4)

    def test_import_forces_immediate_decrease_even_inside_hold(self):
        result = run(cfg(), state(3, T0 - 1), inputs(export_w=0.0, import_w=301.0))
        self.assertEqual(result.steps, 0)
        self.assertIn("import", result.reason)

    def test_import_at_the_limit_does_not_force_the_decrease(self):
        # import 300 W n'est pas > 300 W : retour au comportement d'hystérésis.
        result = run(cfg(), state(1, T0 - 1), inputs(export_w=500.0, import_w=300.0))
        self.assertEqual(result.steps, 1)

    def test_import_bypasses_hysteresis(self):
        # Surplus 400 W conserverait le pas 1 ; l'import > 300 W l'enlève tout de suite.
        result = run(cfg(), state(1, T0 - 1), inputs(export_w=500.0, import_w=400.0))
        self.assertEqual(result.steps, 0)

    def test_change_timestamp_only_moves_when_steps_change(self):
        stable = run(cfg(), state(2, T0 - 1000), inputs(export_w=1100.0))
        self.assertEqual(stable.state, state(2, T0 - 1000))
        changed = run(cfg(), state(2, T0 - 1000), inputs(export_w=0.0))
        self.assertEqual(changed.state, state(0, T0))


class GroupGuardTests(unittest.TestCase):
    def test_guard_power_of_one_group_is_independent_from_the_shared_surplus(self) -> None:
        # Surplus partagé (3 groupes), mais seul le groupe concerné compte pour la garde.
        shared = inputs(export_w=5000.0, group_power_w=3000.0)
        free = run(cfg(), state(1, T0 - 1000), heating_boost_with_guard(shared, 400.0))
        blocked = run(cfg(), state(1, T0 - 1000), heating_boost_with_guard(shared, 2300.0))
        self.assertGreater(free.steps, 1)
        self.assertEqual(blocked.steps, 1)

    def test_no_increase_when_group_is_at_ninety_percent_of_limit(self):
        # 90 % de 2500 W = 2250 W.
        blocked = run(cfg(), state(1, T0 - 1000), inputs(export_w=5000.0, group_power_w=2250.0))
        self.assertEqual(blocked.steps, 1)
        self.assertIn("bloquée", blocked.reason)
        allowed = run(cfg(), state(1, T0 - 1000), inputs(export_w=5000.0, group_power_w=2249.0))
        self.assertEqual(allowed.steps, 4)

    def test_guard_never_blocks_a_decrease(self):
        # Groupe à 2400 W (>= 2250 W) mais surplus réduit par une grande réserve :
        # 0 + 2400 - 1000 = 1400 W -> 2 pas demandés < 3 accordés, import > 300 W.
        config = cfg(heating_surplus_reserve_w=1000.0)
        result = run(config, state(3, T0 - 1), inputs(export_w=0.0, import_w=500.0, group_power_w=2400.0))
        self.assertEqual(result.steps, 2)

    def test_guard_uses_configured_limit(self):
        config = cfg(heating_group_limit_w=1000.0)
        result = run(config, state(0), inputs(export_w=5000.0, group_power_w=900.0))
        self.assertEqual(result.steps, 0)

    def test_missing_group_sensor_disables_the_guard(self):
        self.assertEqual(run(cfg(), state(), inputs(export_w=5000.0, group_power_w=None)).steps, 4)


class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        config = hb.HeatingBoostConfig.from_settings({})
        self.assertFalse(config.enabled)
        self.assertTrue(config.only_when_empty)
        self.assertEqual(
            (config.max_c, config.step_c, config.surplus_per_step_w, config.reserve_w),
            (2.0, 0.5, 500.0, 100.0),
        )
        self.assertEqual((config.hold_s, config.import_max_w, config.group_limit_w), (300.0, 300.0, 2500.0))
        self.assertEqual(config.presence_entity, "zone.home")
        self.assertEqual(config.group_power_sensor, "")
        self.assertEqual(config.max_steps, 4)

    def test_default_settings_match_the_module_defaults(self):
        from foxcat_energy.const import DEFAULT_SETTINGS

        for key, value in hb.DEFAULTS.items():
            self.assertEqual(DEFAULT_SETTINGS[key], value, key)

    def test_settings_take_precedence_over_config(self):
        config = hb.HeatingBoostConfig.from_settings(
            {"heating_boost_max_c": 1.0},
            {"heating_boost_max_c": 3.0, "heating_presence_entity": "person.moi"},
        )
        self.assertEqual(config.max_c, 1.0)
        self.assertEqual(config.presence_entity, "person.moi")

    def test_empty_presence_entity_falls_back_to_zone_home(self):
        config = hb.HeatingBoostConfig.from_settings({}, {"heating_presence_entity": ""})
        self.assertEqual(config.presence_entity, "zone.home")

    def test_invalid_values_fall_back_or_are_clamped(self):
        config = hb.HeatingBoostConfig.from_settings(
            {
                "heating_boost_max_c": "abc",
                "heating_boost_step_c": float("nan"),
                "heating_hold_s": -5,
                "heating_surplus_per_step_w": 0,
                "heating_boost_enabled": "yes",
            }
        )
        self.assertEqual(config.max_c, 2.0)
        self.assertEqual(config.step_c, 0.5)
        self.assertEqual(config.hold_s, 0.0)
        self.assertEqual(config.surplus_per_step_w, 50.0)
        self.assertFalse(config.enabled)  # seul le booléen True active la fonction


class PresenceParsingTests(unittest.TestCase):
    def test_counts_and_text_states(self):
        for raw, expected in (
            ("0", 0), ("2", 2), ("2.0", 2), ("home", 1), ("not_home", 0),
            ("on", 1), ("off", 0), ("HOME", 1), (" 3 ", 3),
        ):
            self.assertEqual(hb.parse_presence(raw), expected, raw)

    def test_unknown_states_return_none(self):
        for raw in (None, "unknown", "unavailable", "", "none", "zone_inconnue", "nan", True):
            self.assertIsNone(hb.parse_presence(raw), repr(raw))


@unittest.skipUnless(HAS_HOME_ASSISTANT, "Home Assistant non installé")
class CoordinatorWiringTests(unittest.TestCase):
    """Le coordinateur lit les entités, appelle la logique pure et n'écrit rien."""

    def setUp(self):
        from foxcat_energy.runtime import coordinator as rc

        self.rc = rc
        self.states = {}
        fake = MagicMock()
        fake.settings = {
            "heating_boost_enabled": True,
            "heating_only_when_empty": True,
            "regulation_active": True,
        }
        fake.config = {"heating_group_power_sensor": "sensor.clim_w"}
        fake._heating_boost_state = hb.HeatingBoostState()
        fake.hass.states.get = lambda entity_id: self.states.get(entity_id)
        fake._heating_presence = lambda entity_id: rc.FoxCatEnergyCoordinator._heating_presence(fake, entity_id)
        fake._optional_float_state = lambda entity_id: rc.FoxCatEnergyCoordinator._optional_float_state(fake, entity_id)
        self.fake = fake

    def evaluate(self, export_w=2000.0, import_w=0.0, valid=True):
        snapshot = SimpleNamespace(valid=valid, export_w=export_w, import_w=import_w)
        self.rc.FoxCatEnergyCoordinator._evaluate_heating_boost(self.fake, snapshot)
        return self.fake.heating_boost_view

    def test_empty_house_publishes_an_offset(self):
        self.states["zone.home"] = SimpleNamespace(state="0")
        view = self.evaluate()
        self.assertEqual(view["offset_c"], 1.5)
        self.assertEqual(view["steps"], 3)

    def test_occupied_house_publishes_zero(self):
        self.states["zone.home"] = SimpleNamespace(state="2")
        self.assertEqual(self.evaluate()["offset_c"], 0.0)

    def test_missing_or_unavailable_presence_counts_as_occupied(self):
        self.assertEqual(self.evaluate()["offset_c"], 0.0)
        self.states["zone.home"] = SimpleNamespace(state="unavailable")
        self.assertEqual(self.evaluate()["offset_c"], 0.0)

    def test_group_power_sensor_is_added_to_the_surplus(self):
        self.states["zone.home"] = SimpleNamespace(state="0")
        self.states["sensor.clim_w"] = SimpleNamespace(state="1000")
        view = self.evaluate(export_w=0.0)
        self.assertEqual((view["steps"], view["surplus_w"]), (1, 900.0))

    def test_unavailable_group_sensor_is_ignored(self):
        self.states["zone.home"] = SimpleNamespace(state="0")
        self.states["sensor.clim_w"] = SimpleNamespace(state="unavailable")
        self.assertEqual(self.evaluate(export_w=1100.0)["steps"], 2)

    def test_state_is_kept_between_evaluations(self):
        self.states["zone.home"] = SimpleNamespace(state="0")
        self.evaluate(export_w=1100.0)
        self.assertEqual(self.fake._heating_boost_state.steps, 2)
        self.assertIsNotNone(self.fake._heating_boost_state.changed_at)

    def test_invalid_snapshot_and_disabled_function_publish_zero(self):
        self.states["zone.home"] = SimpleNamespace(state="0")
        self.assertEqual(self.evaluate(valid=False)["offset_c"], 0.0)
        self.fake.settings["heating_boost_enabled"] = False
        self.assertEqual(self.evaluate()["offset_c"], 0.0)

    def test_never_writes_to_any_entity(self):
        self.states["zone.home"] = SimpleNamespace(state="0")
        self.evaluate()
        self.fake.hass.services.async_call.assert_not_called()
        self.fake.hass.states.async_set.assert_not_called()
        self.fake.hass.async_create_task.assert_not_called()


class AppliedOffsetTests(unittest.TestCase):
    def test_clamp_applied(self):
        for raw, expected in ((None, 0.0), ("abc", 0.0), (-1, 0.0), (1.234, 1.23), (9, 5.0), (float("nan"), 0.0), (True, 0.0)):
            self.assertEqual(hb.clamp_applied(raw), expected, repr(raw))

    def test_applied_offset_is_not_a_setting(self):
        """Profils et « Réinitialiser » ne doivent jamais toucher le décalage appliqué."""
        from foxcat_energy.const import DEFAULT_SETTINGS, NUMBER_DEFINITIONS, SWITCH_DEFINITIONS

        for definitions in (DEFAULT_SETTINGS, NUMBER_DEFINITIONS, SWITCH_DEFINITIONS):
            self.assertNotIn("heating_applied_c", definitions)


@unittest.skipUnless(HAS_HOME_ASSISTANT, "Home Assistant non installé")
class HeatingEntitiesTests(unittest.TestCase):
    def setUp(self):
        from foxcat_energy.runtime import coordinator as rc

        self.rc = rc

    def fake(self, applied=0.0):
        fake = MagicMock()
        fake.heating_applied_c = applied
        fake.entry.entry_id = "abc"
        fake.settings = {}
        fake.config = {}
        fake._async_save = AsyncMock()
        fake._build_data = lambda *a: {}
        return fake

    def test_setting_the_applied_offset_clamps_saves_and_refreshes(self):
        fake = self.fake()
        asyncio.run(self.rc.FoxCatEnergyCoordinator.async_set_heating_applied(fake, 9))
        self.assertEqual(fake.heating_applied_c, 5.0)
        fake._async_save.assert_awaited_once()
        fake.async_set_updated_data.assert_called_once()

    def test_applied_offset_is_part_of_the_saved_state_and_the_published_data(self):
        import inspect

        source = inspect.getsource(self.rc.FoxCatEnergyCoordinator)
        self.assertIn('"heating_applied_c": self.heating_applied_c', source)
        self.assertIn('stored.get("heating_applied_c")', source)
        self.assertIn('"applied_c": self.heating_applied_c', source)

    def test_applied_number_entity_reads_and_writes_through_the_coordinator(self):
        from foxcat_energy.number import FoxCatHeatingAppliedNumber

        fake = self.fake(applied=1.5)
        entity = FoxCatHeatingAppliedNumber(fake)
        self.assertEqual(entity.native_value, 1.5)
        self.assertEqual(entity.unique_id, "abc_heating_applied_c")
        self.assertEqual((entity.native_min_value, entity.native_max_value), (0.0, 5.0))
        fake.async_set_heating_applied = AsyncMock()
        asyncio.run(entity.async_set_native_value(1.0))
        fake.async_set_heating_applied.assert_awaited_once_with(1.0)

    def test_every_heating_entity_listed_in_the_menu_is_really_created(self):
        """La liste affichée à l'utilisateur ne doit jamais citer une entité qui n'existe pas."""
        from foxcat_energy import binary_sensor, config_flow, number, sensor

        created = {}

        class Capture:
            def __init__(self, domain):
                self.domain = domain

            def __call__(self, entities):
                for entity in list(entities):
                    created[entity.unique_id.split("_", 1)[1]] = self.domain

        fake = self.fake()
        fake.data = {}
        fake.settings = {"developer_mode": False}
        hass = MagicMock()
        hass.data = {"foxcat_energy": {"abc": fake}}
        for module, domain in ((sensor, "sensor"), (binary_sensor, "binary_sensor"), (number, "number")):
            asyncio.run(module.async_setup_entry(hass, SimpleNamespace(entry_id="abc"), Capture(domain)))
        from foxcat_energy import switch

        asyncio.run(switch.async_setup_entry(hass, SimpleNamespace(entry_id="abc"), Capture("switch")))
        for _title, items in config_flow._heating_entity_groups():
            for key, label in items:
                self.assertIn(key, created, f"{label} ({key}) n'est créée par aucune plateforme")

    def test_binary_sensor_and_sensors_read_the_published_view(self):
        from foxcat_energy import binary_sensor, sensor

        found = {}

        class Capture:
            def __call__(self, entities):
                for entity in list(entities):
                    found[entity.unique_id.split("_", 1)[1]] = entity

        fake = self.fake()
        fake.settings = {"developer_mode": False}
        hass = MagicMock()
        hass.data = {"foxcat_energy": {"abc": fake}}
        asyncio.run(sensor.async_setup_entry(hass, SimpleNamespace(entry_id="abc"), Capture()))
        asyncio.run(binary_sensor.async_setup_entry(hass, SimpleNamespace(entry_id="abc"), Capture()))
        fake.data = {"heating_boost": {"offset_c": 1.5, "steps": 3, "surplus_w": 1650.0, "reason": "ok"}}
        self.assertEqual(found["chauffage_decalage_consigne"].native_value, 1.5)
        self.assertEqual(found["chauffage_pas_accordes"].native_value, 3)
        self.assertEqual(found["chauffage_surplus_calcule"].native_value, 1650.0)
        self.assertEqual(found["chauffage_statut"].native_value, "ok")
        self.assertTrue(found["chauffage_decalage_actif"].is_on)
        fake.data = {"heating_boost": {"offset_c": 0.0, "steps": 0, "surplus_w": None, "reason": "off"}}
        self.assertFalse(found["chauffage_decalage_actif"].is_on)
        self.assertIsNone(found["chauffage_surplus_calcule"].native_value)


if __name__ == "__main__":
    unittest.main()
