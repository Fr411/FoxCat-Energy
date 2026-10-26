from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

COMPONENT_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT_PATH)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy.accounting.manager import EnergyAccounting, MAX_INTEGRATION_GAP_S
from foxcat_energy.engine.tariff import distribution_period, price_status
from foxcat_energy.economic_optimizer import PricePoint
from foxcat_energy.flexible_load_planner import SAFETY_OVERRIDE, build_flexible_load_plan
from foxcat_energy.machine_learning import MachineLearningRecorder
from foxcat_energy.machines import MachineDefinition
from foxcat_energy.virtual_assets.config import PlannerConfig, config_from_settings
from foxcat_energy.virtual_assets.models import DataQuality, Slot
from foxcat_energy.virtual_assets.planner import plan_and_apply
from foxcat_energy.virtual_assets.battery import VirtualBattery
from foxcat_energy.virtual_assets.config import BatterySpec
from foxcat_energy.virtual_assets.state_store import MAX_EXPECTED_GAP_SECONDS, VirtualAssetsStateStore
from foxcat_energy.vpp import evaluate_trade, evaluate_v2h


NOW = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)


class VPPDecisionTests(unittest.TestCase):
    def test_trade_spread_must_exceed_asset_wear(self):
        trade = evaluate_trade(0.20, [0.30, 0.45], battery_wear_eur_kwh=0.10, vehicle_wear_eur_kwh=0.30)
        self.assertAlmostEqual(trade["spread_eur_kwh"], 0.25)
        self.assertTrue(trade["battery_trade_profitable"])
        self.assertFalse(trade["vehicle_trade_profitable"])

    def test_v2h_uses_90_percent_breaker_limit_and_mobility_reserve(self):
        decision = evaluate_v2h(
            enabled=True,
            price_status="NORMAL",
            house_w=8300,
            breaker_limit_w=9200,
            max_power_w=3000,
            soc_pct=55,
            min_soc_pct=25,
        )
        self.assertTrue(decision["active"])
        self.assertTrue(decision["peak_shaving"])
        self.assertAlmostEqual(decision["peak_trigger_w"], 8280)
        self.assertAlmostEqual(decision["target_power_w"], 940)
        self.assertTrue(decision["thermal_interlock"])

        reserved = evaluate_v2h(
            enabled=True,
            price_status="TRÈS ÉLEVÉ",
            house_w=3000,
            breaker_limit_w=None,
            max_power_w=3000,
            soc_pct=24,
            min_soc_pct=25,
        )
        self.assertFalse(reserved["active"])
        self.assertEqual(reserved["target_power_w"], 0)

    def test_missing_soc_blocks_v2h_even_when_tariff_is_high(self):
        decision = evaluate_v2h(
            enabled=True,
            price_status="TRÈS ÉLEVÉ",
            house_w=3000,
            breaker_limit_w=None,
            max_power_w=3000,
            soc_pct=None,
            min_soc_pct=25,
        )
        self.assertFalse(decision["active"])
        self.assertIn("SoC", decision["reason"])

    def test_malformed_trade_and_v2h_values_fail_safely(self):
        trade = evaluate_trade(
            "invalid",
            [float("nan"), "0.45"],
            battery_wear_eur_kwh="invalid",
            vehicle_wear_eur_kwh=float("inf"),
        )
        self.assertIsNone(trade["current_buy_eur_kwh"])
        self.assertEqual(trade["best_future_sell_eur_kwh"], 0.45)
        self.assertIsNone(trade["spread_eur_kwh"])
        self.assertFalse(trade["battery_trade_profitable"])
        self.assertFalse(trade["vehicle_trade_profitable"])

        decision = evaluate_v2h(
            enabled=True,
            price_status="TRÈS ÉLEVÉ",
            house_w=float("nan"),
            breaker_limit_w=float("inf"),
            max_power_w="invalid",
            soc_pct="unavailable",
            min_soc_pct=float("nan"),
        )
        self.assertFalse(decision["active"])
        self.assertEqual(decision["target_power_w"], 0)
        self.assertEqual(decision["min_soc_pct"], 25.0)

    def test_price_status_and_distribution_period_are_canonical(self):
        self.assertEqual(price_status(0.5, 0.1, 0.5, 0.3), "TRÈS ÉLEVÉ")
        self.assertEqual(price_status(-0.01, -0.01, 0.5, 0.2), "NÉGATIF")
        self.assertEqual(
            distribution_period(NOW.replace(hour=18), {"distribution_profile": "Impact"}),
            "PIC",
        )
        self.assertEqual(
            distribution_period(NOW.replace(hour=8), {"distribution_profile": "Bi-horaire (jour / nuit)"}),
            "HP",
        )

    def test_flexible_planner_blocks_new_start_during_peak_shaving(self):
        machine = MachineDefinition("washer", "Washer", "switch.washer")
        plan = build_flexible_load_plan(
            now=NOW,
            snapshot=SimpleNamespace(pv_w=0, house_w=9000),
            settings={"mode": "Éco", machine.setting_key: True},
            import_points=[PricePoint(NOW, 0.2)],
            export_points=[],
            machines=[machine],
            learning={},
            cycles={},
            price_analysis={"active": True, "mode": "DYNAMIQUE"},
            solar_forecast=None,
            peak_shaving_active=True,
        )
        result = plan["machines"]["washer"]
        self.assertEqual(result["decision"], SAFETY_OVERRIDE)
        self.assertFalse(result["allow_start_now"])

    def test_virtual_grid_trade_uses_future_export_spread_and_wear(self):
        battery = VirtualBattery(
            BatterySpec(
                capacity_kwh=10,
                max_charge_kw=5,
                max_discharge_kw=5,
                charge_efficiency=1,
                discharge_efficiency=1,
                min_soc_pct=0,
                reserve_soc_pct=20,
            ),
            20,
        )
        slots = [
            Slot(NOW, 1, 0, 0, 0.20, None, price_quality=DataQuality.MEASURED),
            Slot(NOW + timedelta(hours=1), 1, 0, 0, None, 0.45, price_quality=DataQuality.MISSING),
        ]
        result = plan_and_apply(
            slots,
            battery,
            None,
            PlannerConfig(allow_grid_arbitrage=True, allow_export_arbitrage=True),
        )
        self.assertEqual(result.action, "charge_battery_grid")
        self.assertGreater(result.battery_charge_from_grid_kwh, 0)

        blocked = plan_and_apply(
            slots,
            battery,
            None,
            PlannerConfig(
                allow_grid_arbitrage=True,
                allow_export_arbitrage=True,
                wear_cost_eur_per_kwh=0.30,
            ),
        )
        self.assertEqual(blocked.battery_charge_from_grid_kwh, 0)

    def test_battery_wear_setting_is_used_by_virtual_planner(self):
        self.assertEqual(
            config_from_settings({"battery_degradation_cost_eur_kwh": 0.12})
            .planner.wear_cost_eur_per_kwh,
            0.12,
        )


class TelemetryGapTests(unittest.TestCase):
    def test_accounting_smooths_gaps_and_caps_at_one_hour(self):
        accounting = EnergyAccounting()
        snapshot = lambda at: SimpleNamespace(
            timestamp=at,
            valid=True,
            house_w=1000.0,
            pv_w=0.0,
            import_w=1000.0,
            export_w=0.0,
        )
        accounting.process(snapshot(NOW), {"regime": "Simple", "period": "SIMPLE"}, [])
        accounting.process(
            snapshot(NOW + timedelta(seconds=300)),
            {"regime": "Simple", "period": "SIMPLE"},
            [],
        )
        self.assertAlmostEqual(accounting.today["import_kwh"], 1000 * 300 / 3_600_000)
        accounting.process(
            snapshot(NOW + timedelta(seconds=7500)),
            {"regime": "Simple", "period": "SIMPLE"},
            [],
        )
        self.assertAlmostEqual(accounting.today["import_kwh"], 1000 * (300 + 3600) / 3_600_000)
        self.assertEqual(MAX_INTEGRATION_GAP_S, 3600.0)

    def test_machine_learning_integrates_a_gap_up_to_one_hour(self):
        recorder = MachineLearningRecorder()
        cycle = {"_last_at": NOW, "_last_power_w": 1000.0, "energy_wh": 0.0, "max_power_w": 1000.0}
        recorder._integrate(cycle, NOW + timedelta(seconds=3600), 1000.0)
        self.assertEqual(recorder.MAX_INTEGRATION_GAP_S, 3600.0)
        self.assertEqual(cycle["energy_wh"], 1000.0)

    def test_virtual_telemetry_store_accepts_longer_gaps(self):
        store = VirtualAssetsStateStore()
        store.check_and_advance_timestamp(NOW)
        valid, hours, _ = store.check_and_advance_timestamp(NOW + timedelta(minutes=30))
        self.assertTrue(valid)
        self.assertAlmostEqual(hours, 0.5)
        self.assertEqual(MAX_EXPECTED_GAP_SECONDS, 3600.0)


if __name__ == "__main__":
    unittest.main()
