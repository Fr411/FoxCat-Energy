from __future__ import annotations

import sys
import types
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

COMPONENT_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT_PATH)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy.economic_optimizer import PricePoint
from foxcat_energy.virtual_assets.accounting import account_simulation
from foxcat_energy.virtual_assets.battery import VirtualBattery
from foxcat_energy.virtual_assets.config import (
    BatterySpec, EVSpec, PlannerConfig, VirtualAssetsConfig, config_from_settings)
from foxcat_energy.virtual_assets.counterfactual import run_counterfactual
from foxcat_energy.virtual_assets.diagnostics import build_diagnostics
from foxcat_energy.virtual_assets.ev import EVSession, VirtualEV
from foxcat_energy.virtual_assets.ha import VirtualAssetsRuntime, read_float_state, setup_virtual_assets
from foxcat_energy.virtual_assets.models import DataQuality, Slot, VirtualAssetsError
from foxcat_energy.virtual_assets.planner import simulate
from foxcat_energy.virtual_assets.profitability import ProfitabilityInputs, analyze_profitability
from foxcat_energy.virtual_assets.shadow import ShadowSimulator
from foxcat_energy.virtual_assets.tariff_adapter import (
    PriceKind, PriceRefused, TariffAdapter, make_slot)

T0 = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
# Batterie sans pertes pour des chiffres exacts
SPEC = BatterySpec(capacity_kwh=10, max_charge_kw=5, max_discharge_kw=5, charge_efficiency=1.0,
                   discharge_efficiency=1.0, min_soc_pct=0, max_soc_pct=100, reserve_soc_pct=20)


def slot(i, load, pv, price=None, export=None, hours=1.0, **kw):
    return Slot(T0 + timedelta(hours=i * hours), hours, load, pv, price, export,
                price_quality=DataQuality.MEASURED if price is not None else DataQuality.MISSING, **kw)


class BatteryTests(unittest.TestCase):
    def test_validation(self):
        for kw in ({"capacity_kwh": 0}, {"charge_efficiency": 1.2}, {"min_soc_pct": 60, "max_soc_pct": 50},
                   {"reserve_soc_pct": 5, "min_soc_pct": 10}, {"capacity_kwh": float("nan")},
                   {"max_charge_kw": True}):
            with self.assertRaises(VirtualAssetsError):
                BatterySpec(**kw)
        with self.assertRaises(VirtualAssetsError):
            VirtualBattery(SPEC, 150)

    def test_charge_limited_by_power_and_capacity(self):
        b = VirtualBattery(SPEC, 50)
        self.assertAlmostEqual(b.charge(10, 1.0), 5.0)      # 5 kW * 1 h
        self.assertAlmostEqual(b.soc_kwh, 10.0)
        self.assertAlmostEqual(b.charge(3, 1.0), 0.0)       # plein
        self.assertEqual(b.soc_pct, 100.0)

    def test_efficiency_and_discharge_floor(self):
        spec = BatterySpec(capacity_kwh=10, charge_efficiency=0.9, discharge_efficiency=0.8,
                           min_soc_pct=10, reserve_soc_pct=20)
        b = VirtualBattery(spec, 20)
        self.assertAlmostEqual(b.charge(2.0, 1.0), 2.0)
        self.assertAlmostEqual(b.soc_kwh, 2.0 + 1.8)
        out = b.discharge(100, 1.0, floor_kwh=b.reserve_kwh)   # plancher réserve 2 kWh
        self.assertAlmostEqual(out, 1.8 * 0.8)
        self.assertAlmostEqual(b.soc_kwh, 2.0)
        self.assertAlmostEqual(b.equivalent_cycles, 0.18)
        self.assertAlmostEqual(b.discharge(100, 1.0), 1.0 * 0.8)  # plancher physique 1 kWh

    def test_wear_cost(self):
        self.assertIsNone(VirtualBattery(SPEC).wear_cost_eur_per_kwh())
        spec = BatterySpec(capex_eur=5000, rated_throughput_kwh=25000)
        self.assertAlmostEqual(VirtualBattery(spec).wear_cost_eur_per_kwh(), 0.2)


class EVTests(unittest.TestCase):
    def session(self):
        return EVSession(T0, T0 + timedelta(hours=8), 20, 80)

    def test_session_validation(self):
        with self.assertRaises(VirtualAssetsError):
            EVSession(T0, T0, 20, 80)
        with self.assertRaises(VirtualAssetsError):
            EVSession(T0, T0 + timedelta(hours=1), 120, 80)

    def test_need_and_charge(self):
        ev = VirtualEV(EVSpec(capacity_kwh=50, max_charge_kw=7.4, charge_efficiency=0.9), self.session())
        self.assertAlmostEqual(ev.need_cell_kwh(), 30.0)
        self.assertAlmostEqual(ev.need_ac_kwh(), 30 / 0.9)
        self.assertAlmostEqual(ev.charge(20, T0, 1.0), 7.4)
        self.assertAlmostEqual(ev.soc_kwh, 10 + 7.4 * 0.9)
        self.assertEqual(ev.charge(5, T0 + timedelta(hours=9), 1.0), 0.0)  # débranché

    def test_departure_shortfall(self):
        ev = VirtualEV(EVSpec(), self.session())
        ev.charge(1.0, T0, 1.0)
        self.assertAlmostEqual(ev.departure_shortfall_kwh(), 30 - 0.9)


class TariffTests(unittest.TestCase):
    def setUp(self):
        self.a = TariffAdapter({})
        self.now = datetime(2026, 1, 5, 12, tzinfo=timezone.utc)

    def test_aiesh_calendar_every_day(self):
        for day in range(7):
            for minute in range(24 * 60):
                at = datetime(2026, 1, 5 + day, minute // 60, minute % 60)
                peak = 420 <= minute < 660 or 1020 <= minute < 1320
                self.assertEqual(self.a.period(at), "HP" if peak else "HC", at)

    def test_classification(self):
        at = self.now
        q = self.a.classify(0.25, at, self.now, is_final=True)
        self.assertEqual((q.kind, q.quality, q.usable), (PriceKind.FINAL_IMPORT, DataQuality.MEASURED, True))
        self.assertEqual(self.a.classify(0.1, at, self.now, direction="export", is_final=True).kind,
                         PriceKind.FINAL_EXPORT)
        self.assertEqual(self.a.classify(0.2, at, self.now).kind, PriceKind.UNKNOWN)
        self.assertFalse(self.a.classify(0.2, at, self.now).usable)
        w = self.a.classify(0.05, at, self.now, is_wholesale=True)
        self.assertEqual(w.kind, PriceKind.WHOLESALE)
        with self.assertRaises(PriceRefused):
            self.a.require_final(w)
        fut = self.a.classify(0.3, at + timedelta(hours=2), self.now, is_final=True)
        self.assertTrue(fut.is_future and fut.usable and not fut.usable_for_accounting)
        self.assertEqual(fut.quality, DataQuality.ESTIMATED)

    def test_missing_not_fabricated(self):
        for bad in (None, float("nan"), True, "0.2"):
            q = self.a.classify(bad, self.now, self.now, is_final=True)
            self.assertIsNone(q.value)
            self.assertEqual(q.quality, DataQuality.MISSING)
        self.assertIsNone(self.a.fixed_import_quote(self.now, self.now, {"HP": 0.3}).value)  # HC absent
        self.assertIsNone(self.a.curve_quote(self.now, self.now, []).value)
        s = make_slot(self.now, 1, 1.0, 0.0, self.a.classify(None, self.now, self.now))
        self.assertIsNone(s.import_price)
        self.assertEqual(s.price_quality, DataQuality.MISSING)

    def test_fixed_bihoraire_and_mono(self):
        hp = datetime(2026, 1, 5, 8, tzinfo=timezone.utc)
        hc = datetime(2026, 1, 5, 13, tzinfo=timezone.utc)
        prices = {"HP": 0.30, "HC": 0.18}
        self.assertEqual(self.a.fixed_import_quote(hp, hc, prices).value, 0.30)
        self.assertEqual(self.a.fixed_import_quote(hc, hc, prices).value, 0.18)
        self.assertEqual(self.a.fixed_import_quote(hp, hc, {"ALL": 0.2}).value, 0.2)

    def test_wholesale_conversion_uses_existing_engine(self):
        settings = {"tariff_network_component_eur_kwh": 0.05, "tariff_tax_component_eur_kwh": 0.02,
                    "tariff_contract_component_eur_kwh": 0.01}
        a = TariffAdapter(settings)
        q = a.curve_quote(self.now, self.now, [PricePoint(self.now, 0.10)], is_wholesale=True)
        self.assertEqual(q.kind, PriceKind.FINAL_IMPORT)
        self.assertAlmostEqual(q.value, 0.18)
        with self.assertRaises(PriceRefused):   # composantes absentes : refus
            self.a.curve_quote(self.now, self.now, [PricePoint(self.now, 0.10)], is_wholesale=True)


class PlannerTests(unittest.TestCase):
    def test_solar_surplus_charges_then_exports(self):
        res = simulate([slot(0, 1, 4, 0.2, 0.05), slot(1, 0, 10, 0.2, 0.05)], VirtualBattery(SPEC, 20), None,
                       PlannerConfig(allow_grid_arbitrage=False))
        f0, f1 = res.flows
        self.assertAlmostEqual(f0.battery_charge_kwh, 3.0)
        self.assertAlmostEqual(f0.export_kwh, 0.0)
        self.assertAlmostEqual(f1.battery_charge_kwh, 5.0)    # limite de puissance
        self.assertAlmostEqual(f1.export_kwh, 5.0)
        self.assertAlmostEqual(res.battery.soc_kwh, 2 + 3 + 5)
        self.assertIn("solar_surplus_to_battery", f0.reasons)

    def test_import_reduction_stops_at_reserve(self):
        res = simulate([slot(0, 3, 0, 0.2), slot(1, 3, 0, 0.2)], VirtualBattery(SPEC, 50), None,
                       PlannerConfig(allow_grid_arbitrage=False))
        f0, f1 = res.flows
        self.assertAlmostEqual(f0.battery_discharge_kwh, 3.0)
        self.assertAlmostEqual(f0.import_kwh, 0.0)
        self.assertAlmostEqual(f1.battery_discharge_kwh, 0.0)   # 5-3=2 kWh = réserve
        self.assertAlmostEqual(f1.import_kwh, 3.0)
        self.assertAlmostEqual(res.battery.soc_kwh, 2.0)
        self.assertIn("reserve_preserved", f1.reasons)

    def test_holdback_for_more_expensive_slot(self):
        slots = [slot(0, 2, 0, 0.15), slot(1, 4, 0, 0.40)]
        res = simulate(slots, VirtualBattery(SPEC, 50), None, PlannerConfig(allow_grid_arbitrage=False))
        f0, f1 = res.flows
        self.assertAlmostEqual(f0.battery_discharge_kwh, 0.0)   # 3 kWh utiles gardés pour 4 kWh à 0.40
        self.assertIn("holdback_for_higher_price", f0.reasons)
        self.assertAlmostEqual(f1.battery_discharge_kwh, 3.0)
        self.assertAlmostEqual(f1.import_kwh, 1.0)

    def test_arbitrage_charges_cheap_then_discharges_expensive(self):
        slots = [slot(0, 0, 0, 0.10), slot(1, 4, 0, 0.40)]
        res = simulate(slots, VirtualBattery(SPEC, 20), None, PlannerConfig())
        f0, f1 = res.flows
        self.assertEqual(f0.action, "charge_battery_grid")
        self.assertAlmostEqual(f0.battery_charge_from_grid_kwh, 4.0)
        self.assertAlmostEqual(f0.import_kwh, 4.0)
        self.assertIn("tariff_arbitrage", f0.reasons)
        self.assertAlmostEqual(f1.battery_discharge_kwh, 4.0)
        self.assertAlmostEqual(f1.import_kwh, 0.0)

    def test_no_arbitrage_when_margin_or_wear_too_high(self):
        slots = [slot(0, 0, 0, 0.10), slot(1, 4, 0, 0.12)]
        self.assertEqual(simulate(slots, VirtualBattery(SPEC, 20), None, PlannerConfig()).flows[0].action, "idle")
        slots = [slot(0, 0, 0, 0.10), slot(1, 4, 0, 0.40)]
        cfg = PlannerConfig(wear_cost_eur_per_kwh=0.35)
        self.assertEqual(simulate(slots, VirtualBattery(SPEC, 20), None, cfg).flows[0].action, "idle")

    def test_missing_price_no_arbitrage(self):
        res = simulate([slot(0, 0, 0, None), slot(1, 4, 0, 0.40)], VirtualBattery(SPEC, 20), None)
        self.assertEqual(res.flows[0].action, "idle")
        self.assertIn("price_missing_no_arbitrage", res.flows[0].reasons)

    def test_ev_departure_prefers_cheapest_slots(self):
        ev = VirtualEV(EVSpec(capacity_kwh=50, max_charge_kw=10, charge_efficiency=1.0),
                       EVSession(T0, T0 + timedelta(hours=3), 40, 60))   # besoin 10 kWh
        slots = [slot(0, 0, 0, 0.30), slot(1, 0, 0, 0.10), slot(2, 0, 0, 0.20)]
        res = simulate(slots, VirtualBattery(SPEC, 20), ev, PlannerConfig(allow_grid_arbitrage=False))
        self.assertEqual([f.ev_charge_kwh for f in res.flows], [0.0, 10.0, 0.0])
        self.assertAlmostEqual(res.flows[1].import_kwh, 10.0)
        self.assertAlmostEqual(res.ev_reports[0][1], 0.0)

    def test_ev_prefers_solar_and_reports_shortfall(self):
        ev = VirtualEV(EVSpec(capacity_kwh=50, max_charge_kw=4, charge_efficiency=1.0),
                       EVSession(T0, T0 + timedelta(hours=2), 40, 60))   # besoin 10, capacité 8
        slots = [slot(0, 0, 4, 0.30), slot(1, 0, 0, 0.10)]
        res = simulate(slots, VirtualBattery(SPEC, 20), ev, PlannerConfig(allow_grid_arbitrage=False))
        f0, f1 = res.flows
        self.assertAlmostEqual(f0.ev_charge_kwh, 4.0)
        self.assertAlmostEqual(f0.import_kwh, 0.0)
        self.assertAlmostEqual(f1.ev_charge_kwh, 4.0)
        self.assertAlmostEqual(res.ev_reports[0][1], 2.0)

    def test_ev_has_priority_over_battery_solar(self):
        ev = VirtualEV(EVSpec(capacity_kwh=50, max_charge_kw=3, charge_efficiency=1.0),
                       EVSession(T0, T0 + timedelta(hours=1), 40, 60))
        res = simulate([slot(0, 0, 5, 0.2)], VirtualBattery(SPEC, 20), ev, PlannerConfig())
        self.assertAlmostEqual(res.flows[0].ev_charge_kwh, 3.0)
        self.assertAlmostEqual(res.flows[0].battery_charge_kwh, 2.0)

    def test_deterministic_and_inputs_untouched(self):
        slots = [slot(0, 1, 4, 0.1), slot(1, 4, 0, 0.4)]
        bat = VirtualBattery(SPEC, 20)
        a = simulate(slots, bat, None)
        b = simulate(slots, bat, None)
        self.assertEqual(a.flows, b.flows)
        self.assertEqual(bat.soc_kwh, 2.0)

    def test_missing_load_is_skipped_not_invented(self):
        res = simulate([slot(0, None, 3, 0.2), slot(1, 1, 0, 0.2)], VirtualBattery(SPEC, 50), None)
        self.assertEqual(len(res.flows), 1)
        self.assertEqual(res.skipped[0][1], "missing_load_or_pv")


class AccountingAndCounterfactualTests(unittest.TestCase):
    def history(self):
        return (slot(0, 0, 0, 0.10, 0.05), slot(1, 4, 0, 0.40, 0.05))

    def test_counterfactual_savings_and_immutability(self):
        hist = self.history()
        snapshot = deepcopy(hist)
        r = run_counterfactual(hist, SPEC, initial_soc_pct=20)
        self.assertEqual(hist, snapshot)
        s = r.summary()
        # baseline : 4 kWh * 0.40 = 1.6 € ; scénario : 4 kWh * 0.10 = 0.4 €
        self.assertAlmostEqual(s["baseline"]["measured"]["net_cost_eur"], 1.6)
        self.assertAlmostEqual(s["scenario"]["measured"]["net_cost_eur"], 0.4)
        self.assertAlmostEqual(s["savings_eur"], 1.2)
        self.assertAlmostEqual(s["battery_charge_kwh"], 4.0)
        self.assertAlmostEqual(s["battery_discharge_kwh"], 4.0)
        self.assertAlmostEqual(s["battery_loss_kwh"], 0.0)
        self.assertEqual(s["quality"], "simulated")
        self.assertEqual(r.summary(), run_counterfactual(hist, SPEC, initial_soc_pct=20).summary())

    def test_losses_accounted(self):
        spec = BatterySpec(capacity_kwh=10, charge_efficiency=0.9, discharge_efficiency=0.9,
                           min_soc_pct=0, reserve_soc_pct=0)
        r = run_counterfactual((slot(0, 0, 3, 0.2), slot(1, 2, 0, 0.2)), spec, initial_soc_pct=0)
        s = r.summary()
        # 3 kWh AC -> 2.7 stocké ; 2 kWh demandés -> 2/0.9 = 2.222 cellule ; pertes = 3-2 - (2.7-2.2222)
        self.assertAlmostEqual(s["battery_loss_kwh"], 1.0 - (2.7 - 2 / 0.9), places=6)

    def test_missing_prices_not_costed(self):
        r = run_counterfactual((slot(0, 4, 0, None), slot(1, 4, 0, 0.2)), SPEC, initial_soc_pct=50)
        s = r.summary()
        self.assertEqual(s["unpriced_slots"], 1)
        self.assertAlmostEqual(s["scenario"]["missing"]["net_cost_eur"], 0.0)
        self.assertAlmostEqual(s["scenario"]["missing"]["import_kwh"], 1.0)   # 3 kWh déchargés
        self.assertAlmostEqual(s["baseline"]["missing"]["import_kwh"], 4.0)

    def test_estimated_prices_separate(self):
        fut = Slot(T0, 1.0, 4, 0, 0.2, None, price_quality=DataQuality.ESTIMATED, price_is_future=True)
        s = run_counterfactual((fut,), SPEC, initial_soc_pct=20).summary()
        self.assertAlmostEqual(s["savings_eur"], 0.0)
        self.assertAlmostEqual(s["baseline"]["estimated"]["net_cost_eur"], 0.8)

    def test_counterfactual_ev_multi_sessions(self):
        sessions = [EVSession(T0, T0 + timedelta(hours=2), 40, 60),
                    EVSession(T0 + timedelta(hours=3), T0 + timedelta(hours=5), 40, 60)]
        hist = tuple(slot(i, 0, 0, 0.3 if i in (0, 3) else 0.1) for i in range(5))
        r = run_counterfactual(hist, SPEC, EVSpec(capacity_kwh=50, max_charge_kw=10, charge_efficiency=1.0),
                               sessions, PlannerConfig(allow_grid_arbitrage=False), 20)
        self.assertEqual([f.ev_charge_kwh for f in r.simulation.flows], [0, 10, 0, 0, 10])
        s = r.summary()
        self.assertEqual(s["ev_shortfalls_kwh"], [0.0, 0.0])
        self.assertAlmostEqual(s["ev_kwh"], 20.0)
        # baseline charge au plus tôt (0.3 €/kWh aux pas 0 et 3) : 6 € ; planifié : 2 €
        self.assertAlmostEqual(s["baseline"]["measured"]["net_cost_eur"], 6.0)
        self.assertAlmostEqual(s["scenario"]["measured"]["net_cost_eur"], 2.0)


class ShadowTests(unittest.TestCase):
    def cfg(self, enabled=True):
        return VirtualAssetsConfig(enabled=enabled, battery=SPEC)

    def test_disabled_does_nothing(self):
        sh = ShadowSimulator(self.cfg(False))
        self.assertIsNone(sh.observe(slot(0, 1, 0, 0.2)))
        self.assertEqual(sh.real_totals["slots"], 0)

    def test_shadow_separates_real_and_simulated(self):
        sh = ShadowSimulator(self.cfg())
        real = slot(0, 0, 4, 0.2, 0.05)
        before = deepcopy(real)
        sh.observe(real)
        self.assertEqual(real, before)
        self.assertEqual(sh.battery.soc_kwh, 2.0 + 4.0)  # solde initial = réserve
        snap = sh.snapshot()
        self.assertEqual(snap["real"]["quality"], "measured")
        self.assertEqual(snap["real"]["pv_kwh"], 4.0)
        self.assertEqual(snap["simulated"]["quality"], "simulated")
        self.assertAlmostEqual(snap["simulated"]["battery_soc_pct"], 60.0)
        # sans batterie réelle ici : l'export de référence est de 4 kWh, simulé 0
        self.assertAlmostEqual(snap["accounting"]["baseline"]["measured"]["export_kwh"], 4.0)
        self.assertAlmostEqual(snap["accounting"]["scenario"]["measured"]["export_kwh"], 0.0)

    def test_shadow_missing_data_counted(self):
        sh = ShadowSimulator(self.cfg())
        sh.observe(slot(0, None, 4, 0.2))
        self.assertEqual(sh.skipped, 1)
        self.assertEqual(sh.battery.soc_kwh, 2.0)

    def test_shadow_state_persists_across_slots(self):
        sh = ShadowSimulator(self.cfg())
        sh.observe(slot(0, 0, 4, 0.2))
        f = sh.observe(slot(1, 3, 0, 0.2))
        self.assertAlmostEqual(f.battery_discharge_kwh, 3.0)
        self.assertAlmostEqual(sh.battery.soc_kwh, 3.0)


class ProfitabilityTests(unittest.TestCase):
    def test_numbers(self):
        r = analyze_profitability(ProfitabilityInputs(
            savings_eur=10, period_days=36.5, capex_eur=1000, years=10, discount_rate=0.0,
            degradation_pct_per_year=0.0))
        self.assertAlmostEqual(r["annual_savings_eur"], 100.0)
        self.assertAlmostEqual(r["roi"], 0.0)
        self.assertAlmostEqual(r["payback_years"], 10.0)
        self.assertAlmostEqual(r["npv_eur"], 0.0)

    def test_degradation_discount_replacement(self):
        r = analyze_profitability(ProfitabilityInputs(
            savings_eur=100, period_days=365, capex_eur=150, years=3, discount_rate=0.1,
            degradation_pct_per_year=10, replacement_cost_eur=50, replacement_year=2))
        flows = [100, 90, 81]
        npv = -150 + sum(f / 1.1 ** (i + 1) for i, f in enumerate(flows)) - 50 / 1.1 ** 2
        self.assertAlmostEqual(r["npv_eur"], npv)
        self.assertAlmostEqual(r["roi"], (271 - 150) / 150)
        self.assertAlmostEqual(r["payback_years"], 1 + 50 / 90)
        sens = r["replacement_sensitivity"]
        self.assertAlmostEqual(sens[1.0], npv)
        self.assertAlmostEqual(sens[0.5], npv + 25 / 1.1 ** 2)

    def test_missing_data_gives_none(self):
        r = analyze_profitability(ProfitabilityInputs(savings_eur=5, period_days=3, capex_eur=None))
        self.assertIsNone(r["roi"]); self.assertIsNone(r["npv_eur"]); self.assertIsNone(r["payback_years"])
        self.assertIn("capex", r["missing"])
        self.assertIn("period_shorter_than_7_days", r["missing"])
        r = analyze_profitability(ProfitabilityInputs(savings_eur=100, period_days=365, capex_eur=500))
        self.assertIn("degradation_not_provided_assumed_0", r["assumptions"])
        self.assertIsNone(r["replacement_sensitivity"])

    def test_negative_savings_no_payback(self):
        r = analyze_profitability(ProfitabilityInputs(savings_eur=-5, period_days=30, capex_eur=500))
        self.assertIsNone(r["payback_years"])
        self.assertLess(r["npv_eur"], -500)


class IsolationTests(unittest.TestCase):
    def test_disabled_by_default(self):
        self.assertFalse(config_from_settings({}).enabled)
        self.assertFalse(config_from_settings(None).enabled)
        self.assertFalse(config_from_settings({"virtual_assets_enabled": "true"}).enabled)
        self.assertIsNone(setup_virtual_assets({}).shadow)
        self.assertTrue(setup_virtual_assets({"virtual_assets_enabled": True}).shadow is not None)

    def test_no_physical_command_in_source(self):
        for path in (COMPONENT_PATH / "virtual_assets").glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for forbidden in ("async_call", "services.", "turn_on", "turn_off", "set_value"):
                self.assertNotIn(forbidden, text, f"{path.name}: {forbidden}")

    def test_diagnostics_no_control_paths(self):
        rt = VirtualAssetsRuntime(VirtualAssetsConfig(enabled=True, battery=SPEC))
        rt.shadow.observe(slot(0, 0, 2, 0.2))
        snap = rt.shadow.snapshot()
        snap["entity_id"] = "switch.x"
        snap["accounting"]["service_call"] = "x"
        diag = build_diagnostics(rt.config, snap)
        text = str(diag)
        self.assertNotIn("switch.x", text)
        self.assertNotIn("service", text)
        self.assertFalse(diag["controls_physical_devices"])
        self.assertEqual(build_diagnostics(VirtualAssetsConfig(), snap).get("shadow"), None)

    def test_read_float_state(self):
        class S:  # noqa: D401
            def __init__(self, state): self.state = state
        class States:
            def get(self, e): return {"a": S("1.5"), "b": S("unavailable")}.get(e)
        hass = types.SimpleNamespace(states=States())
        self.assertEqual(read_float_state(hass, "a"), 1.5)
        self.assertIsNone(read_float_state(hass, "b"))
        self.assertIsNone(read_float_state(hass, "c"))
        self.assertIsNone(read_float_state(hass, None))


if __name__ == "__main__":
    unittest.main()
