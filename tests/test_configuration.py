from __future__ import annotations

import sys
import tempfile
import types
import unittest
from pathlib import Path

COMPONENT_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT_PATH)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy.const import MODES, NETWORK_POLICIES, PRICE_SOURCES, TARIFF_REGIMES
from foxcat_energy.dashboard_versions import (
    available_dashboard_versions,
    recommended_dashboard_version,
)
from foxcat_energy.devices import apply_device_toggle, device_definitions
from foxcat_energy.profiles import profile_path, validate_profile_settings
from foxcat_energy.migration import migrate_settings_v173
from foxcat_energy.select_options import (
    mode_option,
    network_policy_option,
    select_options_are_valid,
    tariff_regime_option,
)


class SelectOptionTests(unittest.TestCase):
    def test_modes_and_current_value_are_valid(self) -> None:
        self.assertTrue(select_options_are_valid())
        self.assertEqual(mode_option({"mode": "Dynamique"}), MODES[0])
        self.assertEqual(mode_option({"mode": "obsolete"}), MODES[-1])
        self.assertTrue(all(mode_option({"mode": value}) in MODES for value in MODES))

    def test_network_and_tariff_current_values_are_valid(self) -> None:
        self.assertEqual(network_policy_option({"network_policy": "obsolete"}), NETWORK_POLICIES[0])
        self.assertEqual(tariff_regime_option({"price_source": "Dynamique Day-Ahead"}), TARIFF_REGIMES[1])
        for policy in NETWORK_POLICIES:
            self.assertEqual(network_policy_option({"network_policy": policy}), policy)
        for regime in TARIFF_REGIMES:
            if regime == TARIFF_REGIMES[0]:
                settings = {"tariff_structure": "Bi-horaire"}
            elif regime == TARIFF_REGIMES[1]:
                settings = {"price_source": "Dynamique Day-Ahead"}
            else:
                settings = {"tariff_structure": "Simple"}
            self.assertEqual(tariff_regime_option(settings), regime)

    def test_legacy_invalid_values_migrate_to_supported_options(self) -> None:
        migrated, notes = migrate_settings_v173(
            {
                "mode": "obsolete",
                "price_source": "obsolete",
                "tariff_structure": "obsolete",
                "network_policy": "Injection facturée",
                "tariff_regime": "obsolete",
            }
        )
        self.assertIn(migrated["mode"], MODES)
        self.assertIn(migrated["price_source"], PRICE_SOURCES)
        self.assertIn(migrated["network_policy"], NETWORK_POLICIES)
        self.assertIn(migrated["tariff_regime"], TARIFF_REGIMES)
        self.assertTrue(notes)


class DeviceConfigurationTests(unittest.TestCase):
    def test_templates_load_with_expected_categories_and_settings(self) -> None:
        definitions = device_definitions()
        self.assertEqual({item.device_id for item in definitions}, {"inverter", "meter", "boiler", "machines"})
        for definition in definitions:
            self.assertEqual(definition.enabled_setting, f"device_{definition.device_id}_enabled")

    def test_disabling_devices_runs_safe_actions(self) -> None:
        settings = {"pri_enabled": True, "regulation_active": True, "washer_enabled": True}
        self.assertEqual(apply_device_toggle(settings, "inverter", False), "release_inverter")
        self.assertFalse(settings["pri_enabled"])
        self.assertEqual(apply_device_toggle(settings, "meter", False), "stop_regulation")
        self.assertFalse(settings["regulation_active"])
        self.assertEqual(apply_device_toggle(settings, "boiler", False), "stop_boiler")
        self.assertEqual(apply_device_toggle(settings, "machines", False), "reconcile_machines")
        self.assertTrue(settings["washer_enabled"])
        with self.assertRaises(ValueError):
            apply_device_toggle(settings, "../unknown", False)


class DashboardAndProfileTests(unittest.TestCase):
    def test_dashboard_versions_are_discovered_and_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for filename in (
                "dashboard_v1.6.160.yaml",
                "dashboard_v1.7.1.yaml",
                "dashboard_v1.7.3.yaml",
                "dashboard_vbad.yaml",
                "manifest_v1.8.0.json",
            ):
                (directory / filename).touch()
            (directory / "manifest_v1.7.3.json").write_text(
                '{"dashboard_version":"1.7.3","recommended":true}',
                encoding="utf-8",
            )
            self.assertEqual(
                available_dashboard_versions(directory),
                ["1.7.3", "1.7.1", "1.6.160"],
            )
            self.assertEqual(recommended_dashboard_version(directory), "1.7.3")

    def test_repository_dashboard_versions_include_recommended_release_candidate(self) -> None:
        versions_directory = COMPONENT_PATH / "dashboard" / "versions"
        versions = available_dashboard_versions(versions_directory)
        self.assertIn("1.7.3", versions)
        self.assertIn("1.7.1", versions)
        self.assertIn("1.6.160", versions)
        self.assertEqual(recommended_dashboard_version(versions_directory), "1.7.3")

    def test_profile_values_are_bounded_and_names_cannot_escape_directory(self) -> None:
        self.assertEqual(
            validate_profile_settings({"boiler_power_w": 1800, "mode": "Dynamique"}),
            {"boiler_power_w": 1800, "mode": "Éco"},
        )
        tariff = validate_profile_settings({"tariff_regime": "Dynamique"})
        self.assertEqual(tariff["price_source"], "Dynamique Day-Ahead")
        self.assertEqual(tariff["tariff_regime"], "Dynamique")
        with self.assertRaises(ValueError):
            validate_profile_settings({"boiler_power_w": 10001})
        with self.assertRaises(ValueError):
            validate_profile_settings({"tariff_hp_start_1": "not-a-time"})
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                profile_path(Path(temporary), "../outside")


if __name__ == "__main__":
    unittest.main()
