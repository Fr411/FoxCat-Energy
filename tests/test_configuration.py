from __future__ import annotations

import asyncio
import importlib
import sys
import tempfile
import types
import unittest
import yaml
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

COMPONENT_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT_PATH)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy.const import (
    DEFAULT_DYNAMIC_HIGH_POSITION_PCT,
    DYNAMIC_STRUCT_BI,
    DYNAMIC_STRUCT_IMPACT,
    DISTRIBUTION_PROFILE_BI,
    DISTRIBUTION_PROFILE_IMPACT,
    DISTRIBUTION_PROFILE_SIMPLE,
    DISTRIBUTION_PROFILES,
    MODES,
    NETWORK_POLICIES,
    NUMBER_DEFINITIONS,
    OFFICIAL_MENU_STEPS,
    PRICE_SOURCE_INTEGRATION,
    PRICE_SOURCE_VARIABLE,
    PRICE_SOURCES,
    TARIFF_BI,
    TARIFF_DYNAMIC,
    TARIFF_REGIMES,
    TARIFF_STRUCTURE_TOU,
    SWITCH_DEFINITIONS,
)
from foxcat_energy.dashboard_versions import (
    available_dashboard_versions,
    dashboard_template_path,
    dashboard_variant_files,
    dashboard_version_for_label,
    dashboard_version_label,
    recommended_dashboard_version,
)
from foxcat_energy.dashboard_merge import merge_dashboard_text
from foxcat_energy.devices import apply_device_toggle, device_definitions
from foxcat_energy.profiles import profile_path, validate_profile_settings
from foxcat_energy.migration import migrate_settings_v173
from foxcat_energy.tariff_model import (
    distribution_period,
    distribution_profile,
    final_client_price,
    tariff_dimensions,
)
from foxcat_energy.accounting import EnergyAccounting
from foxcat_energy.tariff_prices import (
    CONF_TARIFF_HC_PRICE_SENSOR,
    CONF_TARIFF_HP_PRICE_SENSOR,
    apply_configured_tariff,
    scoped_config,
)
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
        self.assertEqual(tariff_regime_option({"price_source": "Dynamique Day-Ahead"}), TARIFF_DYNAMIC)
        for policy in NETWORK_POLICIES:
            self.assertEqual(network_policy_option({"network_policy": policy}), policy)
        for regime in TARIFF_REGIMES:
            if regime == TARIFF_BI:
                settings = {"tariff_structure": "Bi-horaire"}
            elif regime == TARIFF_DYNAMIC:
                settings = {"price_source": "Dynamique Day-Ahead"}
            else:
                settings = {"tariff_structure": "Simple"}
            self.assertEqual(tariff_regime_option(settings), regime)

    def test_external_integration_uses_dynamic_structure_for_prices(self) -> None:
        settings = {
            "price_source": PRICE_SOURCE_INTEGRATION,
            "dynamic_structure": DYNAMIC_STRUCT_BI,
            "tariff_tou_hp_adder_eur_kwh": 0.1,
        }
        dimensions = tariff_dimensions(settings)

        self.assertTrue(dimensions.dynamic)
        self.assertEqual(dimensions.structure, TARIFF_STRUCTURE_TOU)
        self.assertAlmostEqual(final_client_price(0.2, datetime(2026, 1, 2, 8), settings), 0.3)
        self.assertEqual(tariff_regime_option(settings), TARIFF_DYNAMIC)

    def test_configured_bihourly_tariff_uses_its_configured_price_entities(self) -> None:
        config = {
            "tariff_family": "hphc",
            "tariff_structure": "Bi-horaire",
            CONF_TARIFF_HP_PRICE_SENSOR: "sensor.custom_hp",
            CONF_TARIFF_HC_PRICE_SENSOR: "sensor.custom_hc",
            "price_current": "sensor.dynamic_price",
        }
        settings: dict[str, object] = {}

        apply_configured_tariff(settings, config)

        self.assertEqual(settings["tariff_regime"], TARIFF_BI)
        self.assertEqual(settings["tariff_structure"], TARIFF_STRUCTURE_TOU)
        self.assertEqual(
            scoped_config(config),
            {
                "tariff_family": "hphc",
                "tariff_structure": "Bi-horaire",
                CONF_TARIFF_HP_PRICE_SENSOR: "sensor.custom_hp",
                CONF_TARIFF_HC_PRICE_SENSOR: "sensor.custom_hc",
            },
        )

    def test_configured_dynamic_tariff_supports_simple_or_impact(self) -> None:
        for selected, expected_structure in (
            ("Simple", "Simple"),
            ("Impact", DYNAMIC_STRUCT_IMPACT),
        ):
            settings: dict[str, object] = {}
            apply_configured_tariff(
                settings,
                {"tariff_family": "dynamique", "tariff_structure": selected},
            )

            self.assertEqual(settings["price_source"], "Dynamique Day-Ahead")
            self.assertEqual(settings["tariff_regime"], TARIFF_DYNAMIC)
            self.assertEqual(settings["dynamic_structure"], expected_structure)

    def test_dynamic_impact_structure_is_normalized(self) -> None:
        settings = {
            "price_source": "Dynamique Day-Ahead",
            "dynamic_structure": "Impact",
            "impact_peak_adder_eur_kwh": 0.2,
        }

        self.assertAlmostEqual(
            final_client_price(0.1, datetime(2026, 1, 2, 18), settings),
            0.3,
        )

    def test_distribution_profile_is_independent_from_energy_contract(self) -> None:
        settings = {
            "price_source": "Dynamique Day-Ahead",
            "tariff_structure": "Simple",
            "dynamic_structure": "Simple",
            "distribution_profile": DISTRIBUTION_PROFILE_IMPACT,
            "impact_eco_adder_eur_kwh": 0.01,
            "impact_medium_adder_eur_kwh": 0.02,
            "impact_peak_adder_eur_kwh": 0.03,
        }

        dimensions = tariff_dimensions(settings)

        self.assertEqual(dimensions.structure, "Simple")
        self.assertEqual(dimensions.distribution_profile, DISTRIBUTION_PROFILE_IMPACT)
        self.assertEqual(dimensions.network_policy, "Compensation")
        for hour, expected in ((3, 0.11), (8, 0.12), (18, 0.13)):
            self.assertAlmostEqual(
                final_client_price(0.1, datetime(2026, 1, 2, hour), settings),
                expected,
            )
        self.assertEqual(
            [
                distribution_period(datetime(2026, 1, 2, hour), settings)
                for hour in (0, 1, 7, 11, 17, 22)
            ],
            ["MEDIUM", "ECO", "MEDIUM", "ECO", "PIC", "MEDIUM"],
        )
        settings["distribution_profile"] = DISTRIBUTION_PROFILE_SIMPLE
        self.assertEqual(distribution_profile(settings), DISTRIBUTION_PROFILE_SIMPLE)
        self.assertEqual(final_client_price(0.1, datetime(2026, 1, 2, 18), settings), 0.1)
        self.assertEqual(
            DISTRIBUTION_PROFILES,
            ["Simple", "Bi-horaire (jour / nuit)", "Impact"],
        )
        self.assertEqual(
            distribution_profile({"dynamic_structure": DYNAMIC_STRUCT_IMPACT}),
            DISTRIBUTION_PROFILE_IMPACT,
        )
        self.assertEqual(
            distribution_profile(
                {"dynamic_structure": "Simple", "tariff_structure": "Impact"}
            ),
            DISTRIBUTION_PROFILE_IMPACT,
        )

    def test_bihourly_distribution_adders_apply_to_fixed_contracts(self) -> None:
        settings = {
            "price_source": PRICE_SOURCE_VARIABLE,
            "tariff_structure": "Simple",
            "distribution_profile": DISTRIBUTION_PROFILE_BI,
            "tariff_tou_hp_adder_eur_kwh": 0.05,
            "tariff_tou_hc_adder_eur_kwh": 0.02,
        }

        self.assertAlmostEqual(
            final_client_price(0.2, datetime(2026, 1, 2, 8), settings),
            0.25,
        )
        self.assertAlmostEqual(
            final_client_price(0.2, datetime(2026, 1, 2, 12), settings),
            0.22,
        )
        self.assertEqual(
            distribution_period(datetime(2026, 1, 2, 8), settings),
            "HP",
        )
        self.assertEqual(
            distribution_period(datetime(2026, 1, 2, 12), settings),
            "HC",
        )
        for legacy_value in ("Bi-horaire", "Bi-horaire (HP/HC)"):
            self.assertEqual(
                distribution_profile({"tariff_structure": legacy_value}),
                DISTRIBUTION_PROFILE_BI,
            )

    def test_reinjection_value_never_changes_physical_import_kwh(self) -> None:
        accounting = EnergyAccounting()
        first = datetime(2026, 1, 2, 12, 0)
        snapshot = SimpleNamespace(
            timestamp=first,
            valid=True,
            house_w=500.0,
            pv_w=500.0,
            import_w=100.0,
            export_w=50.0,
        )
        accounting.process(snapshot, {"regime": "Mono-horaire", "active_buy": 0.2}, [])
        snapshot.timestamp = first.replace(minute=1)
        accounting.process(
            snapshot,
            {"regime": "Mono-horaire", "active_buy": 0.2, "export_value": -0.3},
            [],
        )

        totals = accounting.view()["today"]
        self.assertAlmostEqual(totals["import_kwh"], 100.0 / 1000 * 60 / 3600)
        self.assertAlmostEqual(totals["export_kwh"], 50.0 / 1000 * 60 / 3600)
        self.assertGreater(totals["export_cost_eur"], 0)

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
        self.assertEqual(
            migrated["dynamic_high_position_pct"],
            DEFAULT_DYNAMIC_HIGH_POSITION_PCT,
        )

    def test_migration_preserves_configured_dynamic_high_position(self) -> None:
        migrated, _ = migrate_settings_v173(
            {
                "mode": "Éco",
                "dynamic_high_position_pct": 65.0,
            }
        )

        self.assertEqual(migrated["dynamic_high_position_pct"], 65.0)


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
    def test_contract_dashboard_entities_are_registered(self) -> None:
        homeassistant = types.ModuleType("homeassistant")
        homeassistant.__path__ = []
        config_entries = types.ModuleType("homeassistant.config_entries")
        config_entries.ConfigEntry = object
        core = types.ModuleType("homeassistant.core")
        core.HomeAssistant = object
        helpers = types.ModuleType("homeassistant.helpers")
        helpers.__path__ = []
        entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
        helpers.entity_registry = entity_registry
        stubs = {
            "homeassistant": homeassistant,
            "homeassistant.config_entries": config_entries,
            "homeassistant.core": core,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.entity_registry": entity_registry,
        }
        original_registry = sys.modules.pop("foxcat_energy.registry", None)
        try:
            with patch.dict(sys.modules, stubs):
                registry = importlib.import_module("foxcat_energy.registry")
                self.assertEqual(
                    registry.BINDINGS["pricing.distribution_profile"].key,
                    "profil_distribution_belgique",
                )
                self.assertEqual(
                    registry.BINDINGS["pricing.distribution_period"].kind,
                    "native",
                )
                for key in (
                    "dynamic_favorable_position_pct",
                    "dynamic_high_position_pct",
                    "impact_eco_adder_eur_kwh",
                    "impact_medium_adder_eur_kwh",
                    "impact_peak_adder_eur_kwh",
                ):
                    self.assertIn(key, NUMBER_DEFINITIONS)
                    self.assertEqual(registry.BINDINGS[f"settings.{key}"].key, key)
                self.assertIn("dynamic_negative_price_charge_enabled", SWITCH_DEFINITIONS)
                self.assertEqual(
                    registry.BINDINGS[
                        "settings.dynamic_negative_price_charge_enabled"
                    ].key,
                    "dynamic_negative_price_charge_enabled",
                )
                for role in (
                    "accounting.appliance.boiler.hp_today",
                    "accounting.appliance.boiler.hc_today",
                    "accounting.appliance.washer.hp_today",
                    "accounting.appliance.washer.hc_today",
                ):
                    self.assertIn(role, registry.BINDINGS)
        finally:
            sys.modules.pop("foxcat_energy.registry", None)
            if original_registry is not None:
                sys.modules["foxcat_energy.registry"] = original_registry

    def test_dashboard_merge_keeps_disjoint_user_and_latest_changes(self) -> None:
        base = "title: FoxCat\nviews:\n  - title: Energy\n    cards:\n      - type: entities\n"
        user = "title: My FoxCat\nviews:\n  - title: Energy\n    cards:\n      - type: entities\n"
        latest = "title: FoxCat\nviews:\n  - title: Energy\n    cards:\n      - type: entities\n      - type: glance\n"

        self.assertEqual(
            merge_dashboard_text(base, user, latest),
            "title: My FoxCat\nviews:\n  - title: Energy\n    cards:\n      - type: entities\n      - type: glance\n",
        )

    def test_dashboard_merge_rejects_conflicting_changes(self) -> None:
        base = "title: FoxCat\n"
        with self.assertRaisesRegex(ValueError, "modifications incompatibles"):
            merge_dashboard_text(
                base,
                "title: Mon dashboard\n",
                "title: Nouveau FoxCat\n",
            )

    def test_dashboard_merge_applies_user_only_with_unchanged_latest(self) -> None:
        base = "title: FoxCat\nviews: []\n"
        user = "title: Mon FoxCat\nviews: []\n"

        self.assertEqual(merge_dashboard_text(base, user, base), user)

    def test_dashboard_versions_are_discovered_and_sorted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for filename in (
                "dashboard_v1.6.160.yaml",
                "dashboard_v1.7.0-premium.yaml",
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
            (directory / "manifest_v1.7.0-premium.json").write_text(
                '{"dashboard_version":"1.7.0-premium","name":"V1.7.0 Premium"}',
                encoding="utf-8",
            )
            self.assertEqual(
                available_dashboard_versions(directory),
                ["1.7.3", "1.7.1", "1.7.0-premium", "1.6.160"],
            )
            self.assertEqual(recommended_dashboard_version(directory), "1.7.3")
            self.assertEqual(
                dashboard_version_label("1.7.0-premium", directory),
                "V1.7.0 Premium",
            )

    def test_dashboard_versions_are_discovered_independently_by_variant(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for filename in (
                "dashboard_v1.7.3.yaml",
                "dashboard_mobile_v1.7.1.yaml",
                "dashboard_mobile_v1.7.4.yaml",
            ):
                (directory / filename).touch()

            self.assertEqual(
                available_dashboard_versions(directory, "tablet"),
                ["1.7.3"],
            )
            self.assertEqual(
                available_dashboard_versions(directory, "mobile"),
                ["1.7.4", "1.7.1"],
            )
            self.assertEqual(
                recommended_dashboard_version(directory, "mobile"),
                "1.7.4",
            )
            (directory / "dashboard_v1.7.4.yaml").touch()
            (directory / "manifest_v1.7.4.json").write_text(
                '{"name":"Tablette 1.7.4"}',
                encoding="utf-8",
            )
            (directory / "manifest_mobile_v1.7.4.json").write_text(
                '{"name":"Mobile 1.7.4"}',
                encoding="utf-8",
            )
            self.assertEqual(
                dashboard_version_label("1.7.4", directory, "tablet"),
                "Tablette 1.7.4",
            )
            self.assertEqual(
                dashboard_version_label("1.7.4", directory, "mobile"),
                "Mobile 1.7.4",
            )
            self.assertEqual(
                dashboard_version_for_label("Tablette 1.7.4", directory, "tablet"),
                "1.7.4",
            )
            self.assertEqual(
                dashboard_version_for_label("Mobile 1.7.4", directory, "mobile"),
                "1.7.4",
            )

    def test_dashboard_templates_and_generated_files_are_independent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            versions = root / "versions"
            versions.mkdir()
            (versions / "dashboard_v1.7.4.yaml").write_text(
                "layout: tablet\n",
                encoding="utf-8",
            )
            (versions / "dashboard_mobile_v1.7.4.yaml").write_text(
                "layout: mobile\n",
                encoding="utf-8",
            )
            self.assertEqual(
                dashboard_template_path(versions, "1.7.4", "tablet"),
                versions / "dashboard_v1.7.4.yaml",
            )
            self.assertEqual(
                dashboard_template_path(versions, "1.7.4", "mobile"),
                versions / "dashboard_mobile_v1.7.4.yaml",
            )
            self.assertEqual(
                dashboard_variant_files("tablet"),
                ("dashboard.yaml", "dashboard_state.json"),
            )
            self.assertEqual(
                dashboard_variant_files("mobile"),
                ("dashboardmob1.yaml", "dashboard_state_mobile.json"),
            )
            with self.assertRaises(ValueError):
                dashboard_variant_files("other")

            homeassistant = types.ModuleType("homeassistant")
            homeassistant.__path__ = []
            config_entries = types.ModuleType("homeassistant.config_entries")
            config_entries.ConfigEntry = object
            core = types.ModuleType("homeassistant.core")
            core.HomeAssistant = object
            registry = types.ModuleType("foxcat_energy.registry")
            registry.resolve_registry = lambda hass, entry, config: {}
            registry.render_dashboard_template = lambda template, bindings: (template, [])
            stubs = {
                "homeassistant": homeassistant,
                "homeassistant.config_entries": config_entries,
                "homeassistant.core": core,
                "foxcat_energy.registry": registry,
            }
            original_dashboard = sys.modules.pop("foxcat_energy.dashboard", None)
            original_dashboard_attr = getattr(package, "dashboard", None)
            try:
                with patch.dict(sys.modules, stubs):
                    dashboard = importlib.import_module("foxcat_energy.dashboard")
                    dashboard._dir = lambda: versions

                    class FakeConfig:
                        def path(self, *parts: str) -> str:
                            return str(root.joinpath("config", *parts))

                    class FakeHass:
                        config = FakeConfig()

                        async def async_add_executor_job(self, function, *args):
                            return function(*args)

                    created_paths = asyncio.run(
                        dashboard.async_ensure_dashboards(FakeHass(), None, {})
                    )
                    self.assertEqual(
                        {Path(path).name for path in created_paths},
                        {"dashboard.yaml", "dashboardmob1.yaml"},
                    )
                    tablet_path = root / "config" / "foxcat_energy" / "dashboard.yaml"
                    self.assertEqual(tablet_path.read_text(encoding="utf-8"), "layout: tablet\n")
                    mobile_path = root / "config" / "foxcat_energy" / "dashboardmob1.yaml"
                    self.assertEqual(mobile_path.read_text(encoding="utf-8"), "layout: mobile\n")
                    legacy_result = asyncio.run(
                        dashboard.async_ensure_dashboard(FakeHass(), None, {})
                    )
                    self.assertEqual(legacy_result, (False, str(tablet_path)))

                    for filename in (
                        "dashboard.yaml",
                        "dashboard_state.json",
                        "dashboardmob1.yaml",
                        "dashboard_state_mobile.json",
                    ):
                        (tablet_path.parent / filename).unlink()
                    (versions / "dashboard_mobile_v1.7.4.yaml").unlink()
                    created_paths = asyncio.run(
                        dashboard.async_ensure_dashboards(FakeHass(), None, {})
                    )
                    self.assertEqual(created_paths, [str(tablet_path)])
                    self.assertTrue(tablet_path.is_file())
                    self.assertFalse(mobile_path.exists())

                    tablet_path.unlink()
                    (tablet_path.parent / "dashboard_state.json").unlink()
                    (versions / "dashboard_v1.7.4.yaml").unlink()
                    (versions / "dashboard_mobile_v1.7.4.yaml").write_text(
                        "layout: mobile\n",
                        encoding="utf-8",
                    )
                    with self.assertRaises(FileNotFoundError):
                        asyncio.run(
                            dashboard.async_ensure_dashboard(FakeHass(), None, {})
                        )
                    self.assertTrue(mobile_path.is_file())
                    self.assertFalse(tablet_path.exists())
            finally:
                sys.modules.pop("foxcat_energy.dashboard", None)
                if original_dashboard_attr is None and hasattr(package, "dashboard"):
                    delattr(package, "dashboard")
                elif original_dashboard_attr is not None:
                    package.dashboard = original_dashboard_attr
                if original_dashboard is not None:
                    sys.modules["foxcat_energy.dashboard"] = original_dashboard

    def test_repository_dashboard_versions_include_both_current_layouts(self) -> None:
        versions_directory = COMPONENT_PATH / "dashboard" / "versions"
        self.assertIn("1.7.4", available_dashboard_versions(versions_directory))
        self.assertIn("1.7.4", available_dashboard_versions(versions_directory, "mobile"))
        self.assertEqual(recommended_dashboard_version(versions_directory), "1.7.4")
        self.assertEqual(
            recommended_dashboard_version(versions_directory, "mobile"),
            "1.7.4",
        )

    def test_battery_ev_menu_and_dashboard_view_exist_for_both_layouts(self) -> None:
        self.assertIn("battery_ev", OFFICIAL_MENU_STEPS)
        versions_directory = COMPONENT_PATH / "dashboard" / "versions"
        for filename in ("dashboard_v1.7.4.yaml", "dashboard_mobile_v1.7.4.yaml"):
            dashboard = yaml.safe_load(
                (versions_directory / filename).read_text(encoding="utf-8")
            )
            view = next(
                (view for view in dashboard["views"] if view.get("title") == "Batterie + VE"),
                None,
            )
            self.assertIsNotNone(view, filename)
            self.assertEqual(view["path"], "batterie-ve")

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
