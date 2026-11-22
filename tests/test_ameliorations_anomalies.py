"""Corrections des anomalies A-04 à A-28 testables sans Home Assistant."""
from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

COMPONENT_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT_PATH)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy.const import BOILER_STOP, DEFAULT_SETTINGS, MODE_ECO, TARIFF_TOU  # noqa: E402
from foxcat_energy.domain.engine import runtime_rules as rules  # noqa: E402
from foxcat_energy.domain.engine.models import BoilerIntent, EnergySnapshot  # noqa: E402
from foxcat_energy.domain.engine.modes import common  # noqa: E402
from foxcat_energy.domain.engine.modes.eco import evaluate_eco  # noqa: E402
from foxcat_energy.domain.pricing import dynamic_scheduler  # noqa: E402
from foxcat_energy.domain.tariff import legacy  # noqa: E402
from foxcat_energy.domain.tariff.tariff_model import final_client_price  # noqa: E402
from foxcat_energy.domain.tariff.valuation import Slot, value_series  # noqa: E402
from foxcat_energy.trading.virtual_assets.config import config_from_settings  # noqa: E402

TZ = timezone(timedelta(hours=1))
MONDAY = datetime(2026, 11, 16, 0, 0, tzinfo=TZ)
T0 = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)


class AttrFloatTests(unittest.TestCase):
    def test_a07_none_text_and_nan_never_raise(self):
        self.assertEqual(rules.attr_float(None), 0.0)
        self.assertEqual(rules.attr_float("abc", 7.0), 7.0)
        self.assertEqual(rules.attr_float(float("nan"), 3.0), 3.0)
        self.assertEqual(rules.attr_float("46.5"), 46.5)


class OverrideExpiryTests(unittest.TestCase):
    def test_a13_expires_after_the_limit(self):
        self.assertFalse(rules.override_expired(T0, T0 + timedelta(hours=5), 6))
        self.assertTrue(rules.override_expired(T0, T0 + timedelta(hours=6), 6))

    def test_a13_zero_means_unlimited_and_unknown_origin_never_expires(self):
        self.assertFalse(rules.override_expired(T0, T0 + timedelta(days=9), 0))
        self.assertFalse(rules.override_expired(None, T0, 6))


class SocketActionTests(unittest.TestCase):
    base = dict(cycle_active=False, keep_running=False, backup_on=False, high_load_block=False,
                allowed=True, tariff_ok=True)

    def test_a23_management_off_sends_nothing(self):
        self.assertIsNone(rules.machine_socket_action(management=False, **self.base))
        self.assertIsNone(rules.machine_socket_action(management=False, **{**self.base, "backup_on": True}))

    def test_a23_management_off_still_sheds_a_sheddable_machine(self):
        self.assertEqual(
            rules.machine_socket_action(management=False, **{**self.base, "high_load_block": True}), "turn_off"
        )

    def test_management_on_keeps_previous_behaviour(self):
        self.assertEqual(rules.machine_socket_action(management=True, **self.base), "turn_on")
        self.assertEqual(rules.machine_socket_action(management=True, **{**self.base, "tariff_ok": False}), "turn_off")
        self.assertEqual(
            rules.machine_socket_action(management=True, **{**self.base, "tariff_ok": False, "cycle_active": True}),
            "turn_on",
        )


class PromptWindowsTests(unittest.TestCase):
    def test_a27_default_windows_match_the_old_hard_coded_text(self):
        text = rules.hp_hc_windows_text({})
        self.assertIn("HP: 07:00-11:00 et 17:00-22:00", text)
        self.assertIn("22:00-07:00", text)
        self.assertIn("11:00-17:00", text)

    def test_a27_follows_the_settings(self):
        text = rules.hp_hc_windows_text({"tariff_hp_start_1": "06:00:00", "tariff_hp_end_1": "10:00:00"})
        self.assertIn("HP: 06:00-10:00 et 17:00-22:00", text)
        self.assertNotIn("07:00-11:00", text)


class ContractTariffTests(unittest.TestCase):
    def assert_equivalent(self, settings, base):
        tariff = legacy.tariff_from_settings(settings)
        self.assertIsNotNone(tariff)
        for quarter in range(96):
            at = MONDAY + timedelta(minutes=15 * quarter)
            cost = value_series([Slot(at, 1.0, 0.0)], tariff)
            self.assertAlmostEqual(
                cost.energy_eur + cost.network_eur, final_client_price(base, at, settings), places=9, msg=str(at)
            )

    def test_a15_all_in_ignores_period_adders(self):
        self.assert_equivalent(
            {
                "price_source": "Contractuelle / fixe", "tariff_structure": "Bi-horaire", "price_is_all_in": True,
                "tariff_hp_price_eur_kwh": 0.40, "tariff_hc_price_eur_kwh": 0.40,
                "tariff_tou_hp_adder_eur_kwh": 0.05, "tariff_tou_hc_adder_eur_kwh": 0.03,
            },
            0.40,
        )

    def test_a15_components_are_added_when_the_price_is_not_final(self):
        self.assert_equivalent(
            {
                "price_source": "Contractuelle / fixe", "tariff_structure": "Simple",
                "price_curve_is_final": False, "tariff_simple_fixed_price_eur_kwh": 0.20,
                "tariff_network_component_eur_kwh": 0.08, "tariff_tax_component_eur_kwh": 0.02,
                "tariff_contract_component_eur_kwh": 0.01,
            },
            0.20,
        )


class SchedulerStepTests(unittest.TestCase):
    def test_a18_point_step_is_read_from_the_series(self):
        P = dynamic_scheduler.PricePoint
        quarter = [P(T0 + timedelta(minutes=15 * i), 0.1, "T") for i in range(4)]
        hourly = [P(T0 + timedelta(hours=i), 0.1, "T") for i in range(4)]
        self.assertEqual(dynamic_scheduler._point_step(quarter), timedelta(minutes=15))
        self.assertEqual(dynamic_scheduler._point_step(hourly), timedelta(hours=1))
        self.assertEqual(dynamic_scheduler._point_step(quarter[:1]), timedelta(hours=1))


class VirtualAssetsConfigTests(unittest.TestCase):
    def test_a28_real_price_source_labels_allow_export_arbitrage(self):
        for source in ("Dynamique Day-Ahead", "Intégration externe"):
            cfg = config_from_settings({"price_source": source})
            self.assertTrue(cfg.planner.allow_export_arbitrage, source)
        self.assertFalse(config_from_settings({"price_source": "Contractuelle / fixe"}).planner.allow_export_arbitrage)


class BoilerRatesTests(unittest.TestCase):
    def test_a08_rates_are_settings_with_the_old_defaults(self):
        self.assertEqual(common.heat_rate_c_per_h({}), 10.0)
        self.assertEqual(common.cool_rate_c_per_h({}), 0.5)
        self.assertEqual(common.heat_rate_c_per_h({"boiler_heat_rate_c_per_h": 5}), 5.0)
        self.assertEqual(common.heat_rate_c_per_h({"boiler_heat_rate_c_per_h": "x"}), 10.0)
        self.assertIn("boiler_heat_rate_c_per_h", DEFAULT_SETTINGS)

    def test_a08_slower_heating_needs_an_earlier_departure(self):
        snap = EnergySnapshot(
            timestamp=T0, pv_w=0, house_w=300, export_w=0, import_w=300, grid_net_w=-300, boiler_temp_c=30.0,
            boiler_safety_temp_c=30.0, boiler_power_w=1800, inverter_power_w=4000, boiler_on=False,
            boiler_setpoint_c=45, machine_active=False,
        )
        settings = dict(DEFAULT_SETTINGS)
        now = datetime(2026, 1, 1, 5, 30)  # 90 min avant les HP de 07:00
        fast = common.ecs_last_departure(snap, {**settings, "boiler_heat_rate_c_per_h": 30}, now)
        slow = common.ecs_last_departure(snap, {**settings, "boiler_heat_rate_c_per_h": 3}, now)
        self.assertFalse(fast)
        self.assertTrue(slow)


class EnergyOnlyIntentTests(unittest.TestCase):
    def test_a05_default_is_false_and_eco_hp_stop_is_flagged(self):
        self.assertFalse(BoilerIntent(BOILER_STOP, "hp achat réseau dans le texte").energy_only)
        snap = EnergySnapshot(
            timestamp=T0, pv_w=0, house_w=300, export_w=0, import_w=300, grid_net_w=300, boiler_temp_c=50.0,
            boiler_safety_temp_c=50.0, boiler_power_w=1800, inverter_power_w=4000, boiler_on=True,
            boiler_setpoint_c=45, machine_active=False,
        )
        settings = dict(DEFAULT_SETTINGS, mode=MODE_ECO, tariff_regime=TARIFF_TOU)
        # 08:00 = HP, boiler en marche et import > 50 W : arrêt « achat réseau HP interdit ».
        intent = evaluate_eco(snap, snap, settings, datetime(2026, 1, 1, 8, 0), 600.0, "NONE")
        self.assertEqual(intent.action, BOILER_STOP)
        self.assertIn("achat réseau HP", intent.reason)
        self.assertTrue(intent.energy_only)
        # Un arrêt de sécurité n'est jamais une simple contrainte énergétique.
        safe = evaluate_eco(snap, snap, {**settings, "boiler_enabled": False}, datetime(2026, 1, 1, 8, 0), 600.0, "NONE")
        self.assertFalse(safe.energy_only)


if __name__ == "__main__":
    unittest.main()
