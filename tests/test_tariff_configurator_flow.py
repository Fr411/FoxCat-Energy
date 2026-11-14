"""Flux d'installation (contrat × réseau × prix) et étapes d'options de tarification."""
from __future__ import annotations

import asyncio
import json
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("foxcat_energy", package)

try:
    import voluptuous_serialize
    from homeassistant.data_entry_flow import FlowResultType, section
    from homeassistant.helpers import config_validation as cv

    from foxcat_energy import config_flow as cf
    from foxcat_energy.runtime import coordinator as rc

    HAS_HOME_ASSISTANT = True
except ModuleNotFoundError:  # pragma: no cover - environnement sans Home Assistant
    HAS_HOME_ASSISTANT = False

from foxcat_energy.domain.tariff.tariff_model import final_client_price  # noqa: E402
from foxcat_energy.domain.tariff.tariff_prices import apply_configured_tariff  # noqa: E402


def run(coroutine):
    return asyncio.run(coroutine)


def field_names(schema) -> set[str]:
    names: set[str] = set()
    for marker, value in schema.schema.items():
        if isinstance(value, section):
            names |= {inner.schema for inner in value.schema.schema}
        else:
            names.add(str(marker.schema))
    return names


class SettingsApplicationTests(unittest.TestCase):
    """Toutes les combinaisons contrat × réseau aboutissent à des réglages cohérents."""

    def test_every_contract_and_network_combination(self) -> None:
        cases = [
            # famille, structure, source, régime, structure interne
            ("hphc", "Mono-horaire", None, "Mono-horaire", "Simple"),
            ("hphc", "Bi-horaire", None, "Bi-horaire (HP/HC)", "Bi-horaire"),
            ("hphc", "Impact", None, "Mono-horaire", "Impact"),
            ("dynamique", "Simple", None, "Dynamique", "Simple"),
            ("dynamique", "Bi-horaire", None, "Dynamique", "Bi-horaire"),
            ("dynamique", "Impact", None, "Dynamique", "Impact"),
        ]
        for family, structure, source, regime, internal in cases:
            settings: dict = {}
            apply_configured_tariff(settings, {"tariff_family": family, "tariff_structure": structure})
            self.assertEqual(settings["tariff_regime"], regime, (family, structure))
            self.assertEqual(settings["tariff_structure"], internal, (family, structure))

    def test_dynamic_bi_horaire_selects_the_bi_horaire_dynamic_structure(self) -> None:
        settings: dict = {}
        apply_configured_tariff(settings, {"tariff_family": "dynamique", "tariff_structure": "Bi-horaire"})
        self.assertEqual(settings["dynamic_structure"], "Bi-horaire")

    def test_manual_prices_keep_the_contract_price_source(self) -> None:
        settings: dict = {}
        apply_configured_tariff(
            settings,
            {"tariff_family": "hphc", "tariff_structure": "Bi-horaire", "price_source": "Contractuelle / fixe"},
        )
        self.assertEqual(settings["price_source"], "Contractuelle / fixe")
        settings = {}
        apply_configured_tariff(settings, {"tariff_family": "hphc", "tariff_structure": "Bi-horaire"})
        self.assertEqual(settings["price_source"], "Variable via entités Home Assistant")

    def test_unknown_or_legacy_configuration_is_left_untouched(self) -> None:
        settings = {"price_source": "x"}
        apply_configured_tariff(settings, {})
        self.assertEqual(settings, {"price_source": "x"})


class AllInTests(unittest.TestCase):
    base = {"price_source": "Dynamique Day-Ahead", "dynamic_structure": "Bi-horaire", "tariff_tou_hp_adder_eur_kwh": 0.10}
    at = datetime(2026, 1, 2, 8, 0)  # heures pleines

    def test_adders_are_added_by_default(self) -> None:
        self.assertAlmostEqual(final_client_price(0.20, self.at, dict(self.base)), 0.30)

    def test_all_in_price_is_never_increased(self) -> None:
        self.assertAlmostEqual(final_client_price(0.20, self.at, {**self.base, "price_is_all_in": True}), 0.20)

    def test_all_in_also_skips_component_surcharges(self) -> None:
        settings = {**self.base, "price_is_all_in": True, "price_curve_is_final": False,
                    "tariff_network_component_eur_kwh": 0.05}
        self.assertAlmostEqual(final_client_price(0.20, self.at, settings), 0.20)


@unittest.skipUnless(HAS_HOME_ASSISTANT, "Home Assistant non installé")
class InstallFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.translations = json.loads((COMPONENT / "translations/fr.json").read_text(encoding="utf-8"))
        self.flow = cf.FoxCatEnergyConfigFlow()
        self.flow.hass = MagicMock()
        self.flow._async_current_entries = lambda: []

    def check_form(self, step_id: str, result) -> None:
        self.assertEqual(result["type"], FlowResultType.FORM, step_id)
        step = self.translations["config"]["step"][step_id]
        labels = set(step.get("data", {}))
        for group in step.get("sections", {}).values():
            labels |= set(group.get("data", {}))
        self.assertEqual(field_names(result["data_schema"]), labels, step_id)
        voluptuous_serialize.convert(result["data_schema"], custom_serializer=cv.custom_serializer)

    def test_first_screen_is_a_form_not_a_menu(self) -> None:
        result = run(self.flow.async_step_user())
        self.check_form("user", result)

    def test_aborts_when_already_installed(self) -> None:
        self.flow._async_current_entries = lambda: [object()]
        result = run(self.flow.async_step_user())
        self.assertEqual(result["type"], FlowResultType.ABORT)

    def test_manual_mono_path(self) -> None:
        run(self.flow.async_step_user({"tariff_family": "hphc", "grid_region": "wallonie"}))
        self.check_form("network", run(self.flow.async_step_network()))
        self.check_form("hphc", run(self.flow.async_step_network({"tariff_structure": "Mono-horaire", "price_is_all_in": False})))
        result = run(self.flow.async_step_hphc({"price_input": "manual"}))
        self.check_form("hphc_manual", result)
        result = run(self.flow.async_step_hphc_manual(
            {"tariff_simple_fixed_price_eur_kwh": 0.28, "tariff_fixed_injection_eur_kwh": 0.04}
        ))
        self.assertEqual(result["step_id"], "core")
        self.assertEqual(self.flow._options["price_source"], "Contractuelle / fixe")
        self.assertAlmostEqual(self.flow._options["tariff_simple_fixed_price_eur_kwh"], 0.28)
        self.assertNotIn("tariff_hp_price_eur_kwh", self.flow._options)

    def test_manual_bi_path_asks_hp_and_hc(self) -> None:
        run(self.flow.async_step_user({"tariff_family": "hphc", "grid_region": "wallonie"}))
        run(self.flow.async_step_network({"tariff_structure": "Bi-horaire", "price_is_all_in": True}))
        result = run(self.flow.async_step_hphc({"price_input": "manual"}))
        self.assertEqual(result["step_id"], "hphc_bi_manual")
        self.check_form("hphc_bi_manual", result)
        # Le formulaire soumis arrive sur l'étape qui porte l'identifiant du formulaire.
        result = run(self.flow.async_step_hphc_bi_manual(
            {"tariff_hp_price_eur_kwh": 0.40, "tariff_hc_price_eur_kwh": 0.21}
        ))
        self.assertEqual(result["step_id"], "core")
        self.assertAlmostEqual(self.flow._options["tariff_hp_price_eur_kwh"], 0.40)
        self.assertAlmostEqual(self.flow._options["tariff_hc_price_eur_kwh"], 0.21)
        self.assertTrue(self.flow._options["price_is_all_in"])

    def test_sensor_paths(self) -> None:
        run(self.flow.async_step_user({"tariff_family": "hphc", "grid_region": "flandre"}))
        run(self.flow.async_step_network({"tariff_structure": "Bi-horaire", "price_is_all_in": False}))
        result = run(self.flow.async_step_hphc({"price_input": "sensors"}))
        self.assertEqual(result["step_id"], "hphc_bi")
        self.check_form("hphc_bi", result)

        flow = cf.FoxCatEnergyConfigFlow()
        flow.hass = MagicMock()
        flow._async_current_entries = lambda: []
        run(flow.async_step_user({"tariff_family": "hphc", "grid_region": "flandre"}))
        run(flow.async_step_network({"tariff_structure": "Impact", "price_is_all_in": False}))
        result = run(flow.async_step_hphc({"price_input": "sensors"}))
        self.assertEqual(result["step_id"], "hphc_mono")
        self.check_form("hphc_mono", result)

    def test_dynamic_family_skips_the_price_questions(self) -> None:
        run(self.flow.async_step_user({"tariff_family": "dynamique", "grid_region": "wallonie"}))
        result = run(self.flow.async_step_network({"tariff_structure": "Bi-horaire", "price_is_all_in": True}))
        self.assertEqual(result["step_id"], "core")
        self.assertEqual(self.flow._data["tariff_structure"], "Bi-horaire")

    def test_no_supplier_specific_entity_is_prefilled(self) -> None:
        for builder in (cf._pricing_schema, cf._hphc_schema):
            for marker in builder().schema:
                default = marker.default() if callable(getattr(marker, "default", None)) else None
                self.assertFalse(isinstance(default, str) and "luminus" in default.lower(), marker.schema)

    def test_entry_creation_carries_options_and_region_templates(self) -> None:
        run(self.flow.async_step_user({"tariff_family": "hphc", "grid_region": "flandre"}))
        run(self.flow.async_step_network({"tariff_structure": "Mono-horaire", "price_is_all_in": False}))
        run(self.flow.async_step_hphc({"price_input": "manual"}))
        run(self.flow.async_step_hphc_manual({"tariff_simple_fixed_price_eur_kwh": 0.28}))
        self.flow._data["installation_name"] = "Maison"
        self.flow.async_set_unique_id = AsyncMock()
        self.flow._abort_if_unique_id_configured = lambda: None
        result = run(self.flow.async_step_ia({}))
        self.assertEqual(result["type"], FlowResultType.CREATE_ENTRY)
        self.assertEqual(result["data"]["tariff_family"], "hphc")
        self.assertEqual(result["data"]["grid_region"], "flandre")
        options = result["options"]
        self.assertEqual(options["price_source"], "Contractuelle / fixe")
        self.assertEqual([t["id"] for t in options["tariff_comparison"]], ["wal_mono"])
        # La Flandre précharge le capacitaire du guide, modifiable dans « Coûts réseau ».
        self.assertEqual(options["grid_capacity_kind"], "peak_monthly")
        self.assertEqual(options["grid_capacity_min_kw"], 2.5)
        # Ce que l'installation produit alimente bien les réglages.
        settings: dict = {}
        apply_configured_tariff(settings, {**result["data"], **options})
        self.assertEqual(settings["price_source"], "Contractuelle / fixe")
        self.assertEqual(settings["tariff_structure"], "Simple")

    def test_unknown_region_preloads_no_comparison(self) -> None:
        run(self.flow.async_step_user({"tariff_family": "dynamique", "grid_region": "autre"}))
        run(self.flow.async_step_network({"tariff_structure": "Simple", "price_is_all_in": True}))
        self.flow.async_set_unique_id = AsyncMock()
        self.flow._abort_if_unique_id_configured = lambda: None
        result = run(self.flow.async_step_ia({}))
        self.assertNotIn("tariff_comparison", result["options"])
        self.assertTrue(result["options"]["price_is_all_in"])


@unittest.skipUnless(HAS_HOME_ASSISTANT, "Home Assistant non installé")
class OptionsFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.translations = json.loads((COMPONENT / "translations/fr.json").read_text(encoding="utf-8"))
        entry = SimpleNamespace(entry_id="abc", data={}, options={})

        class Flow(cf.FoxCatEnergyOptionsFlow):
            config_entry = entry

        self.flow = Flow()
        self.flow.hass = MagicMock()
        self.flow.hass.data = {cf.DOMAIN: {}}

    def check_form(self, step_id: str, result) -> None:
        self.assertEqual(result["type"], FlowResultType.FORM, step_id)
        step = self.translations["options"]["step"][step_id]
        self.assertEqual(field_names(result["data_schema"]), set(step.get("data", {})), step_id)
        voluptuous_serialize.convert(result["data_schema"], custom_serializer=cv.custom_serializer)

    def test_pricing_menu_lists_every_screen_and_each_has_a_step(self) -> None:
        menu = run(self.flow.async_step_pricing())
        self.assertEqual(
            menu["menu_options"],
            ["tariff_contract", "pricing_dynamic", "hphc", "grid_costs", "price_publication", "tariff_compare", "init"],
        )
        labels = self.translations["options"]["step"]["pricing"]["menu_options"]
        for option in menu["menu_options"]:
            self.assertIn(option, labels)
            self.assertTrue(hasattr(self.flow, f"async_step_{option}"))

    def test_contract_screen_is_translated_and_serialisable(self) -> None:
        self.check_form("tariff_contract", run(self.flow.async_step_tariff_contract()))

    def test_contract_change_writes_coherent_keys(self) -> None:
        result = run(self.flow.async_step_tariff_contract({
            "price_source": "Dynamique Day-Ahead", "tariff_structure": "Bi-horaire",
            "price_is_all_in": True, "network_policy": "Compensation",
            "tariff_simple_fixed_price_eur_kwh": 0.30, "tariff_hp_price_eur_kwh": 0.35,
            "tariff_hc_price_eur_kwh": 0.25, "tariff_fixed_injection_eur_kwh": 0.0,
        }))
        self.assertEqual(result["type"], FlowResultType.MENU)
        pending = self.flow._ensure_pending()
        self.assertEqual(pending["tariff_family"], "dynamique")
        self.assertEqual(pending["tariff_regime"], "Dynamique")
        self.assertEqual(pending["dynamic_structure"], "Bi-horaire")
        self.assertEqual(pending["distribution_profile"], "Bi-horaire (jour / nuit)")
        self.assertTrue(pending["price_is_all_in"])

    def test_every_contract_network_pair_is_coherent(self) -> None:
        expected = {
            ("Prix saisis", "Simple"): ("hphc", "Mono-horaire", "Simple"),
            ("Prix saisis", "Bi-horaire"): ("hphc", "Bi-horaire (HP/HC)", "Bi-horaire (jour / nuit)"),
            ("Prix saisis", "Impact"): ("hphc", "Mono-horaire", "Impact"),
            ("Dynamique Day-Ahead", "Simple"): ("dynamique", "Dynamique", "Simple"),
            ("Dynamique Day-Ahead", "Bi-horaire"): ("dynamique", "Dynamique", "Bi-horaire (jour / nuit)"),
            ("Dynamique Day-Ahead", "Impact"): ("dynamique", "Dynamique", "Impact"),
        }
        for (source, structure), (family, regime, profile) in expected.items():
            keys = cf._coherent_tariff_keys(source, structure)
            self.assertEqual((keys["tariff_family"], keys["tariff_regime"], keys["distribution_profile"]),
                             (family, regime, profile), (source, structure))

    def test_grid_costs_screen_is_translated_and_serialisable(self) -> None:
        self.check_form("grid_costs", run(self.flow.async_step_grid_costs()))

    def test_grid_costs_are_saved_and_applied_as_settings(self) -> None:
        result = run(self.flow.async_step_grid_costs({
            "grid_capacity_kind": "peak_monthly", "grid_capacity_eur_per_kw_year": 58.5,
            "grid_capacity_min_kw": 2.5, "grid_prosumer_eur_per_year": 0.0,
            "grid_peak_kw_entity": "sensor.monthly_peak_kw",
        }))
        self.assertEqual(result["type"], FlowResultType.MENU)
        pending = self.flow._ensure_pending()
        self.assertEqual(pending["grid_capacity_kind"], "peak_monthly")
        self.assertAlmostEqual(pending["grid_capacity_eur_per_kw_year"], 58.5)
        self.assertEqual(pending["grid_peak_kw_entity"], "sensor.monthly_peak_kw")
        self.assertEqual(pending["grid_capacity_cost_entity"], "")
        from foxcat_energy.const import DEFAULT_SETTINGS
        from foxcat_energy.domain.tariff.grid_costs import GridCosts

        for key in ("grid_capacity_kind", "grid_capacity_eur_per_kw_year", "grid_capacity_min_kw", "grid_prosumer_eur_per_year"):
            self.assertIn(key, DEFAULT_SETTINGS, key)  # sinon l'option ne serait pas appliquée
        costs = GridCosts.from_settings(pending)
        self.assertEqual(costs.capacity.kind, "peak_monthly")
        self.assertAlmostEqual(costs.capacity.eur_per_kw_year, 58.5)

    def test_grid_costs_incomplete_capacity_is_refused(self) -> None:
        for payload in (
            {"grid_capacity_kind": "flat", "grid_capacity_eur_per_year": 0},
            {"grid_capacity_kind": "peak_monthly", "grid_capacity_eur_per_kw_year": 0},
        ):
            result = run(self.flow.async_step_grid_costs(payload))
            self.assertEqual(result["errors"], {"base": "invalid_grid_costs"}, payload)
        self.assertNotIn("grid_capacity_kind", self.flow._ensure_pending())

    def test_grid_costs_can_be_switched_off(self) -> None:
        run(self.flow.async_step_grid_costs({"grid_capacity_kind": "flat", "grid_capacity_eur_per_year": 47.0}))
        run(self.flow.async_step_grid_costs({"grid_capacity_kind": "none"}))
        self.assertEqual(self.flow._ensure_pending()["grid_capacity_kind"], "none")

    def test_publication_screen(self) -> None:
        self.check_form("price_publication", run(self.flow.async_step_price_publication()))

    def test_publication_service_name_is_validated(self) -> None:
        for bad in ("refresh", "Be.Refresh", "a.b.c!", ".x", "x."):
            result = run(self.flow.async_step_price_publication({"price_refresh_service": bad}))
            self.assertEqual(result["errors"], {"base": "invalid_service_name"}, bad)
        result = run(self.flow.async_step_price_publication({
            "price_publication_entity": "binary_sensor.nord_pool_be_prix_de_demain_disponible",
            "price_refresh_service": "be_electricity_prices.refresh",
        }))
        self.assertEqual(result["type"], FlowResultType.MENU)
        pending = self.flow._ensure_pending()
        self.assertEqual(pending["price_refresh_service"], "be_electricity_prices.refresh")
        self.assertEqual(pending["price_publication_entity"], "binary_sensor.nord_pool_be_prix_de_demain_disponible")

    def test_publication_can_be_cleared(self) -> None:
        run(self.flow.async_step_price_publication({"price_publication_entity": "binary_sensor.x", "price_refresh_service": "a.b"}))
        run(self.flow.async_step_price_publication({}))
        pending = self.flow._ensure_pending()
        self.assertEqual(pending["price_publication_entity"], "")
        self.assertEqual(pending["price_refresh_service"], "")


@unittest.skipUnless(HAS_HOME_ASSISTANT, "Home Assistant non installé")
class GridCostsViewTests(unittest.TestCase):
    def test_integration_values_are_read_for_control_only(self) -> None:
        from foxcat_energy.domain.tariff.grid_costs import GridCosts
        from foxcat_energy.domain.tariff.valuation import Slot

        values = {"sensor.cap": 12.3, "sensor.peak": 4.0}
        me = SimpleNamespace(
            config={"grid_capacity_cost_entity": "sensor.cap", "grid_peak_kw_entity": "sensor.peak"},
            _optional_float_state=lambda eid: values.get(eid),
        )
        at = datetime(2026, 11, 3, 18, 0, tzinfo=timezone.utc)
        slots = [Slot(at, 1.0, 0.0), Slot(at + timedelta(minutes=15), 0.2, 0.0)]  # pointe 4 kW
        view = rc.FoxCatEnergyCoordinator._grid_costs_view(me, GridCosts(), slots)
        self.assertEqual(view["foxcat_peak_kw"], 4.0)
        self.assertEqual(view["peak_kw_integration"], 4.0)
        self.assertEqual(view["capacity_cost_integration"], 12.3)
        self.assertIsNone(view["prosumer_cost_integration"])  # entité non configurée
        self.assertEqual(view["configured"]["capacitaire"]["kind"], "none")


@unittest.skipUnless(HAS_HOME_ASSISTANT, "Home Assistant non installé")
class PublicationSignalTests(unittest.TestCase):
    def fake(self, service: str = "be_electricity_prices.refresh"):
        return SimpleNamespace(
            hass=MagicMock(),
            config={"price_refresh_service": service},
            _last_price_refresh=None,
            async_set_updated_data=MagicMock(),
            async_refresh_prices=MagicMock(),
            _build_data=lambda: {"ok": True},
        )

    def event(self, domain: str, old: str | None, new: str | None):
        state = lambda value: None if value is None else SimpleNamespace(state=value, domain=domain)
        return SimpleNamespace(data={"old_state": state(old), "new_state": state(new)})

    def test_binary_sensor_only_triggers_when_turning_on(self) -> None:
        me = self.fake()
        handler = rc.FoxCatEnergyCoordinator._on_price_publication
        for old, new in (("off", "on"),):
            me.hass.async_create_task.reset_mock()
            handler(me, self.event("binary_sensor", old, new))
            self.assertEqual(me.hass.async_create_task.call_count, 1)
        for old, new in (("on", "off"), ("on", "on"), ("off", "unavailable"), ("on", None)):
            me.hass.async_create_task.reset_mock()
            handler(me, self.event("binary_sensor", old, new))
            self.assertEqual(me.hass.async_create_task.call_count, 0, (old, new))

    def test_timestamp_sensor_triggers_on_any_change(self) -> None:
        me = self.fake()
        rc.FoxCatEnergyCoordinator._on_price_publication(me, self.event("sensor", "2026-11-13T13:00", "2026-11-13T13:05"))
        self.assertEqual(me.hass.async_create_task.call_count, 1)

    def test_refresh_calls_the_service_then_recomputes(self) -> None:
        me = self.fake()
        me.hass.services.has_service.return_value = True
        me.hass.services.async_call = AsyncMock()
        run(rc.FoxCatEnergyCoordinator.async_refresh_prices(me, "test"))
        me.hass.services.async_call.assert_awaited_once_with("be_electricity_prices", "refresh", {}, blocking=True)
        me.async_set_updated_data.assert_called_once()

    def test_refresh_is_rate_limited(self) -> None:
        me = self.fake()
        me.hass.services.has_service.return_value = True
        me.hass.services.async_call = AsyncMock()
        run(rc.FoxCatEnergyCoordinator.async_refresh_prices(me, "1"))
        run(rc.FoxCatEnergyCoordinator.async_refresh_prices(me, "2"))
        self.assertEqual(me.hass.services.async_call.await_count, 1)

    def test_missing_service_does_not_fail(self) -> None:
        me = self.fake()
        me.hass.services.has_service.return_value = False
        me.hass.services.async_call = AsyncMock()
        run(rc.FoxCatEnergyCoordinator.async_refresh_prices(me, "test"))
        me.hass.services.async_call.assert_not_awaited()
        me.async_set_updated_data.assert_called_once()

    def test_service_failure_is_not_fatal(self) -> None:
        me = self.fake()
        me.hass.services.has_service.return_value = True
        me.hass.services.async_call = AsyncMock(side_effect=RuntimeError("boom"))
        run(rc.FoxCatEnergyCoordinator.async_refresh_prices(me, "test"))
        me.async_set_updated_data.assert_called_once()

    def test_no_service_configured_still_recomputes(self) -> None:
        me = self.fake(service="")
        run(rc.FoxCatEnergyCoordinator.async_refresh_prices(me, "test"))
        me.async_set_updated_data.assert_called_once()


if __name__ == "__main__":
    unittest.main()
