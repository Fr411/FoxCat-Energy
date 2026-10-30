"""Menu de configuration : pilote le vrai flux Home Assistant, ignoré si HA n'est pas installé."""
import asyncio
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
HAS_HOME_ASSISTANT = importlib.util.find_spec("homeassistant") is not None

if HAS_HOME_ASSISTANT:
    package = types.ModuleType("foxcat_energy")
    package.__path__ = [str(COMPONENT)]
    sys.modules.setdefault("foxcat_energy", package)
    import voluptuous_serialize
    from homeassistant.data_entry_flow import FlowResultType, section
    from homeassistant.helpers import config_validation as cv

    from foxcat_energy import config_flow as cf
    from foxcat_energy.const import EQUIPMENT_MENU_STEPS, OFFICIAL_MENU_STEPS


def run(coroutine):
    return asyncio.run(coroutine)


def labels_of(step: dict) -> set[str]:
    keys = set(step.get("data", {}))
    for group in step.get("sections", {}).values():
        keys |= set(group.get("data", {}))
    return keys


def form_keys(schema) -> tuple[set[str], set[str]]:
    """Return (field keys including those nested in sections, section names)."""
    fields: set[str] = set()
    sections: set[str] = set()
    for marker, value in schema.schema.items():
        if isinstance(value, section):
            sections.add(marker.schema)
            fields |= {inner.schema for inner in value.schema.schema}
        else:
            fields.add(marker.schema)
    return fields, sections


@unittest.skipUnless(HAS_HOME_ASSISTANT, "Home Assistant non installé")
class OptionsMenuTests(unittest.TestCase):
    def setUp(self) -> None:
        self.translations = {
            name: json.loads((COMPONENT / name).read_text(encoding="utf-8"))
            for name in ("strings.json", "translations/fr.json")
        }

    def flow(self, data=None, options=None, settings=None):
        entry = SimpleNamespace(entry_id="abc", data=data or {}, options=options or {})

        class Flow(cf.FoxCatEnergyOptionsFlow):
            config_entry = entry

        flow = Flow()
        flow.hass = MagicMock()
        coordinators = {} if settings is None else {"abc": SimpleNamespace(settings=settings)}
        flow.hass.data = {cf.DOMAIN: coordinators}
        return flow

    def check_form(self, flow_step, result, step: dict) -> None:
        self.assertEqual(result["type"], FlowResultType.FORM, flow_step)
        fields, sections = form_keys(result["data_schema"])
        self.assertEqual(labels_of(step), fields, flow_step)
        self.assertEqual(set(step.get("sections", {})), sections, flow_step)
        # Le frontend ne reçoit que ce que ce sérialiseur sait produire.
        voluptuous_serialize.convert(result["data_schema"], custom_serializer=cv.custom_serializer)

    def test_translation_files_are_identical(self) -> None:
        self.assertEqual(self.translations["strings.json"], self.translations["translations/fr.json"])

    def test_every_menu_entry_has_a_label(self) -> None:
        flow = self.flow()
        for name, translations in self.translations.items():
            steps = translations["options"]["step"]
            self.assertEqual(set(steps["init"]["menu_options"]), set(OFFICIAL_MENU_STEPS), name)
            self.assertEqual(set(steps["equipment"]["menu_options"]), set(EQUIPMENT_MENU_STEPS), name)
            for menu in ("init", "equipment", "pricing"):
                for option in steps[menu]["menu_options"]:
                    self.assertTrue(hasattr(flow, f"async_step_{option}"), option)

    def test_every_form_field_is_labelled_and_serialisable(self) -> None:
        steps = self.translations["translations/fr.json"]["options"]["step"]
        flow = self.flow(options={"grid_signed_sensor": "sensor.grid"})
        for name in ("sources", "boiler", "pri", "hphc", "ia", "pricing_dynamic", "battery_ev", "peak_shaving"):
            result = run(getattr(flow, f"async_step_{name}")())
            self.check_form(name, result, steps[name])
        self.check_form("machine_add", run(flow.async_step_machine_add()), steps["machine_add"])

    def test_wizard_forms_are_labelled_and_serialisable(self) -> None:
        steps = self.translations["translations/fr.json"]["config"]["step"]
        flow = cf.FoxCatEnergyConfigFlow()
        for name in ("core", "boiler", "pri", "machines", "pricing", "ia"):
            result = run(getattr(flow, f"async_step_{name}")())
            self.check_form(name, result, steps[name])

    def test_wizard_titles_carry_no_step_counter(self) -> None:
        for step in self.translations["translations/fr.json"]["config"]["step"].values():
            self.assertNotIn("/7", step["title"])

    def test_sections_are_stored_flat(self) -> None:
        flow = self.flow()
        run(flow.async_step_boiler({
            "boiler_climate": "climate.b",
            "thermal_model": {"boiler_volume": 300.0},
        }))
        self.assertEqual(flow._pending_options["boiler_volume"], 300.0)
        self.assertNotIn("thermal_model", flow._pending_options)

    def test_saved_values_are_prefilled_inside_sections(self) -> None:
        flow = self.flow(options={"boiler_volume": 300.0})
        result = run(flow.async_step_boiler())
        inner = next(value for value in result["data_schema"].schema.values() if isinstance(value, section))
        marker = next(item for item in inner.schema.schema if item.schema == "boiler_volume")
        self.assertEqual(marker.description, {"suggested_value": 300.0})

    def test_emptied_entity_is_really_cleared(self) -> None:
        flow = self.flow(data={"inverter_power_sensor": "sensor.inverter"})
        run(flow.async_step_pri({
            "pri_l1": "switch.a", "pri_l2": "switch.b", "pri_l3": "switch.c", "pri_l4": "switch.d",
        }))
        self.assertEqual(flow._pending_options["inverter_power_sensor"], "")

    def test_untouched_empty_entity_is_not_written(self) -> None:
        flow = self.flow()
        run(flow.async_step_pri({
            "pri_l1": "switch.a", "pri_l2": "switch.b", "pri_l3": "switch.c", "pri_l4": "switch.d",
        }))
        self.assertNotIn("inverter_power_sensor", flow._pending_options)

    def test_status_shows_live_tariff_and_pending_changes(self) -> None:
        flow = self.flow(settings={"tariff_regime": "Dynamique", "high_load_shed_enabled": True})
        status = run(flow.async_step_init())["description_placeholders"]["status"]
        self.assertIn("Dynamique", status)
        self.assertIn("Écrêtage : activé", status)
        self.assertNotIn("⚠️", status)
        run(flow.async_step_boiler({"boiler_climate": "climate.b", "thermal_model": {}}))
        self.assertIn("⚠️", run(flow.async_step_init())["description_placeholders"]["status"])

    def test_no_machine_hides_edit_and_never_aborts(self) -> None:
        flow = self.flow(options={"boiler_volume": 300.0, cf.CONF_MACHINES_V13: []})
        menu = run(flow.async_step_machines())
        self.assertEqual(menu["menu_options"], ["machine_add", "equipment"])
        self.assertEqual(menu["description_placeholders"]["machines"], "aucune")
        for step in (flow.async_step_machine_edit(), flow.async_step_machine_remove()):
            self.assertEqual(run(step)["type"], FlowResultType.MENU)

    def test_machine_sections_round_trip_and_keep_input_on_error(self) -> None:
        flow = self.flow(options={cf.CONF_MACHINES_V13: []})
        invalid = run(flow.async_step_machine_add({
            "name": "Pompe", "machine_type": "switch",
            "automation": {"automatic": False}, "cycle": {}, "measurements": {},
        }))
        self.assertEqual(invalid["errors"], {"base": "invalid_machine_config"})
        name = next(item for item in invalid["data_schema"].schema if item.schema == "name")
        self.assertEqual(name.default(), "Pompe")
        run(flow.async_step_machine_add({
            "name": "Pompe", "machine_type": "switch", "switch": "switch.pompe",
            "automation": {"automatic": False}, "cycle": {"cycle_end_w": 7.0}, "measurements": {},
        }))
        record = flow._pending_options[cf.CONF_MACHINES_V13][0]
        self.assertFalse(record["automatic"])
        self.assertEqual(record["cycle_end_w"], 7.0)

    def test_peak_validation_reads_values_inside_sections(self) -> None:
        flow = self.flow()
        result = run(flow.async_step_peak_shaving({
            "high_load_shed_enabled": True,
            "connection": {},
            "thresholds": {"high_load_trigger_w": 3000, "high_load_release_w": 4000},
            "measurements": {},
            "not_applied": {},
        }))
        self.assertEqual(result["errors"], {"base": "peak_release_not_below_trigger"})
        self.assertEqual(flow._pending_options, {})

    def test_finish_saves_everything_pending(self) -> None:
        flow = self.flow(options={"boiler_volume": 250.0})
        run(flow.async_step_boiler({"thermal_model": {"boiler_volume": 300.0}}))
        result = run(flow.async_step_finish())
        self.assertEqual(result["type"], FlowResultType.CREATE_ENTRY)
        self.assertEqual(result["data"]["boiler_volume"], 300.0)


if __name__ == "__main__":
    unittest.main()
