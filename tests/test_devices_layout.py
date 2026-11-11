"""Classement des appareils : même découpage que le menu, sans casser les entity_id."""
import asyncio
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
HAS_HOME_ASSISTANT = importlib.util.find_spec("homeassistant") is not None

package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy import devices_layout as layout  # noqa: E402


class LayoutRulesTests(unittest.TestCase):
    def test_every_legacy_device_maps_to_a_known_device(self):
        for legacy, target in layout.LEGACY_TO_DEVICE.items():
            self.assertIn(target, layout.DEVICE_NAMES, legacy)

    def test_names_are_unique_and_prefixed(self):
        names = list(layout.DEVICE_NAMES.values())
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(name.startswith("FoxCat Energy – ") for name in names))

    def test_hub_is_a_known_device(self):
        self.assertIn(layout.HUB_DEVICE, layout.DEVICE_NAMES)

    def test_obsolete_devices_are_exactly_the_legacy_ones_that_disappear(self):
        self.assertEqual(
            set(layout.OBSOLETE_DEVICES),
            {"energy", "metronome", "accounting", "inverter", "user_functions", "solar", "ems", "energy_bus", "diagnostic"},
        )
        self.assertFalse(set(layout.OBSOLETE_DEVICES) & set(layout.DEVICE_NAMES))

    def test_dedicated_devices(self):
        cases = {
            ("heating_boost_enabled", "ems"): "heating",
            ("chauffage_decalage_consigne", "ems"): "heating",
            ("high_load_trigger_w", "ems"): "protection",
            ("main_breaker_current_a", "ems"): "protection",
            ("intensite_reseau", "ems"): "protection",
            ("statut_delestage", "ems"): "protection",
            ("peak_shaving_decharge_w", "ems"): "protection",
            ("impact_peak_adder_eur_kwh", "ems"): "pricing",
            ("network_billed_import_max_w", "ems"): "pri",
            ("machine_lave_linge_arret_utilisateur", "user_functions"): "machines",
            ("boiler_demarrage_utilisateur", "user_functions"): "boiler",
            ("analyser_solaire", "solar"): "ai",
            ("bilan_revenu_injection_jour", "energy"): "pricing",
            ("economiser_foxcat_jour", "accounting"): "pricing",
        }
        for (key, legacy), expected in cases.items():
            self.assertEqual(layout.resolve_device(key, legacy), expected, key)

    def test_legacy_fallbacks(self):
        for legacy, expected in (
            ("ems", "system"), ("energy_bus", "system"), ("diagnostic", "system"),
            ("energy", "sources"), ("metronome", "sources"), ("sources", "sources"),
            ("inverter", "pri"), ("solar", "ai"), ("inconnu", "system"),
        ):
            self.assertEqual(layout.resolve_device("une_cle", legacy), expected, legacy)


@unittest.skipUnless(HAS_HOME_ASSISTANT, "Home Assistant non installé")
class RealEntitiesTests(unittest.TestCase):
    """Toutes les entités réellement créées par FoxCat."""

    @classmethod
    def setUpClass(cls):
        from foxcat_energy import binary_sensor, button, number, select, sensor, switch
        from foxcat_energy import time as time_platform
        from foxcat_energy.const import DEFAULT_SETTINGS

        fake = MagicMock()
        fake.entry.entry_id = "abc"
        fake.settings = dict(DEFAULT_SETTINGS)
        fake.config = {}
        fake.controllable_machines = []
        fake.machines = []
        fake.data = {}
        hass = MagicMock()
        hass.data = {"foxcat_energy": {"abc": fake}}
        cls.entities = []
        for module in (sensor, binary_sensor, number, switch, select, time_platform, button):
            got = []
            asyncio.run(module.async_setup_entry(hass, SimpleNamespace(entry_id="abc"), lambda e, got=got: got.extend(list(e))))
            cls.entities.extend(got)

    def devices(self):
        result = {}
        for entity in self.entities:
            info = entity.device_info
            result.setdefault(sorted(info["identifiers"])[0][1], []).append(entity)
        return result

    def test_every_entity_lands_in_a_known_device(self):
        known = {f"abc:{key}" for key in layout.DEVICE_NAMES}
        unknown = {ident for ident in self.devices() if ident not in known}
        self.assertEqual(unknown, set())

    def test_no_obsolete_device_is_used_any_more(self):
        used = set(self.devices())
        for key in layout.OBSOLETE_DEVICES:
            self.assertNotIn(f"abc:{key}", used, key)

    def test_names_come_from_the_layout(self):
        for entity in self.entities:
            info = entity.device_info
            ident = sorted(info["identifiers"])[0][1].split(":", 1)[1]
            self.assertEqual(info["name"], layout.DEVICE_NAMES[ident])

    def test_every_device_but_the_hub_hangs_off_the_hub(self):
        for entity in self.entities:
            info = entity.device_info
            ident = sorted(info["identifiers"])[0][1].split(":", 1)[1]
            if ident == layout.HUB_DEVICE:
                self.assertIsNone(info.get("via_device"))
            else:
                self.assertEqual(info["via_device"], ("foxcat_energy", f"abc:{layout.HUB_DEVICE}"))

    def test_unique_ids_do_not_depend_on_the_device(self):
        """Condition pour que les entity_id existants restent intacts."""
        for entity in self.entities:
            self.assertEqual(entity.unique_id, f"abc_{entity._key}")

    def test_heating_and_protection_devices_hold_their_entities(self):
        devices = self.devices()
        heating = {e._key for e in devices["abc:heating"]}
        for key in ("chauffage_decalage_consigne", "chauffage_decalage_actif", "heating_applied_c",
                    "heating_boost_enabled", "heating_boost_max_c"):
            self.assertIn(key, heating)
        protection = {e._key for e in devices["abc:protection"]}
        for key in ("high_load_shed_enabled", "high_load_trigger_w", "main_breaker_current_a",
                    "statut_delestage", "haute_consommation_active", "charge_disjoncteur_pct"):
            self.assertIn(key, protection)
        # Plus rien de chauffage ni de protection dans le « Système ».
        system = {e._key for e in devices["abc:system"]}
        self.assertFalse({k for k in system if k.startswith(("heating_", "chauffage_", "high_load_", "main_breaker_"))})

    def test_ai_is_one_single_device(self):
        """« IA » et « Solaire » (deux appareils du même nom) sont regroupés."""
        devices = self.devices()
        self.assertNotIn("abc:solar", devices)
        ai_keys = {e._key for e in devices["abc:ai"]}
        for key in ("analyser_solaire", "confiance_solaire", "potentiel_solaire", "tendance_solaire",
                    "solar_advisor_enabled", "solar_forecast_arbitrage", "prevision_solaire_raison"):
            self.assertIn(key, ai_keys)
        names = {e.device_info["name"] for e in devices["abc:ai"]}
        self.assertEqual(names, {"FoxCat Energy – Prévisions et IA"})

    def test_no_device_is_a_dumping_ground(self):
        for ident, items in self.devices().items():
            self.assertLessEqual(len(items), 120, ident)


@unittest.skipUnless(HAS_HOME_ASSISTANT, "Home Assistant non installé")
class ObsoleteDeviceCleanupTests(unittest.TestCase):
    def setUp(self):
        from foxcat_energy import device_cleanup

        self.integration = device_cleanup

    def device(self, key, device_id):
        return SimpleNamespace(
            id=device_id, name=f"FoxCat Energy – {key}", name_by_user=None,
            identifiers={("foxcat_energy", f"abc:{key}")},
        )

    def run_cleanup(self, devices, entities_by_device):
        registry = MagicMock()
        with patch.object(self.integration.dr, "async_get", return_value=registry), \
             patch.object(self.integration.er, "async_get", return_value=MagicMock()), \
             patch.object(self.integration.dr, "async_entries_for_config_entry", return_value=devices), \
             patch.object(self.integration.er, "async_entries_for_device",
                          side_effect=lambda reg, device_id, **kw: entities_by_device.get(device_id, [])):
            self.integration.async_remove_obsolete_devices(MagicMock(), SimpleNamespace(entry_id="abc"))
        return registry

    def test_empty_obsolete_devices_are_removed(self):
        registry = self.run_cleanup([self.device("ems", "d1"), self.device("energy_bus", "d2")], {})
        removed = {call.args[0] for call in registry.async_update_device.call_args_list}
        self.assertEqual(removed, {"d1", "d2"})
        for call in registry.async_update_device.call_args_list:
            self.assertEqual(call.kwargs, {"remove_config_entry_id": "abc"})

    def test_an_obsolete_device_that_still_has_entities_is_kept(self):
        registry = self.run_cleanup([self.device("ems", "d1")], {"d1": [object()]})
        registry.async_update_device.assert_not_called()

    def test_current_devices_are_never_removed_even_if_empty(self):
        registry = self.run_cleanup([self.device("boiler", "d1"), self.device("heating", "d2")], {})
        registry.async_update_device.assert_not_called()


if __name__ == "__main__":
    unittest.main()
