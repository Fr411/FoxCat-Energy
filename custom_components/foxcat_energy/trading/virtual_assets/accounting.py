"""Comptabilité dédiée à l'énergie et à l'économie simulées.

Totalement séparée du ``EnergyAccounting`` historique (seul ledger du réel) : rien n'est
écrit dans le réel. Les clés d'énergie/coût reprennent celles de ``accounting.manager.ZERO``.
Les montants sont ventilés selon la qualité du prix : ``measured`` (prix final observé),
``estimated`` (prix futur) ; sans prix, seuls les kWh sont cumulés (``missing``).
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from ...domain.accounting.manager import ZERO
from .battery import VirtualBattery
from .ev import EVTracker, VirtualEV
from .models import DataQuality, Slot, SlotFlow

_BUCKETS = (DataQuality.MEASURED.value, DataQuality.ESTIMATED.value, DataQuality.MISSING.value)


def _bucket() -> dict[str, float]:
    b: dict[str, float] = deepcopy(ZERO)
    b.update(slots=0, net_cost_eur=0.0)
    return b


def baseline_step(slot: Slot, car: VirtualEV | None) -> tuple[float, float, float]:
    """Référence sans actifs : maison seule + VE chargé au plus tôt à pleine puissance.

    Retourne (import_kWh, export_kWh, énergie VE AC).
    """
    load, pv = float(slot.load_kwh), float(slot.pv_kwh)  # type: ignore[arg-type]
    ev = 0.0 if car is None else car.charge(car.need_ac_kwh(), slot.start, slot.hours)
    net = pv - load - ev
    return max(-net, 0.0), max(net, 0.0), ev


class SimulatedLedger:
    """Cumule scénario simulé et référence, par qualité de prix."""

    def __init__(self) -> None:
        self.scenario = {q: _bucket() for q in _BUCKETS}
        self.baseline = {q: _bucket() for q in _BUCKETS}
        self.battery_charge_kwh = 0.0
        self.battery_discharge_kwh = 0.0
        self.battery_loss_kwh = 0.0
        self.ev_kwh = 0.0
        self.slots = 0

    @staticmethod
    def _add(b: dict[str, float], flow: SlotFlow, imp: float, exp: float) -> None:
        b["slots"] += 1
        b["house_kwh"] += flow.load_kwh
        b["pv_kwh"] += flow.pv_kwh
        b["import_kwh"] += imp
        b["export_kwh"] += exp
        if flow.price_quality is DataQuality.MISSING or flow.import_price is None:
            return
        cost = imp * flow.import_price
        revenue = exp * flow.export_price if flow.export_price is not None else 0.0
        b["import_cost_eur"] += cost
        b["export_revenue_eur"] += revenue
        b["export_value_eur"] += revenue
        b["net_cost_eur"] += cost - revenue

    def record(self, flow: SlotFlow, base_import: float, base_export: float,
               loss_kwh: float = 0.0) -> None:
        q = flow.price_quality.value
        self._add(self.scenario[q], flow, flow.import_kwh, flow.export_kwh)
        self._add(self.baseline[q], flow, base_import, base_export)
        self.slots += 1
        self.battery_charge_kwh += flow.battery_charge_kwh
        self.battery_discharge_kwh += flow.battery_discharge_kwh
        self.battery_loss_kwh += loss_kwh
        self.ev_kwh += flow.ev_charge_kwh

    @property
    def savings_eur(self) -> float:
        """Économie sur prix mesurés uniquement (baseline - scénario)."""
        m = DataQuality.MEASURED.value
        return self.baseline[m]["net_cost_eur"] - self.scenario[m]["net_cost_eur"]

    @property
    def estimated_savings_eur(self) -> float:
        e = DataQuality.ESTIMATED.value
        return self.baseline[e]["net_cost_eur"] - self.scenario[e]["net_cost_eur"]

    def summary(self) -> dict[str, Any]:
        miss = DataQuality.MISSING.value
        return {
            "quality": DataQuality.SIMULATED.value,
            "slots": self.slots,
            "scenario": deepcopy(self.scenario),
            "baseline": deepcopy(self.baseline),
            "battery_charge_kwh": self.battery_charge_kwh,
            "battery_discharge_kwh": self.battery_discharge_kwh,
            "battery_loss_kwh": self.battery_loss_kwh,
            "ev_kwh": self.ev_kwh,
            "savings_eur": self.savings_eur,
            "savings_estimated_eur": self.estimated_savings_eur,
            "unpriced_slots": int(self.scenario[miss]["slots"]),
        }


def account_simulation(slots, result, battery_start: VirtualBattery,
                       ev: VirtualEV | None = None, sessions=()) -> SimulatedLedger:
    """Rejoue la référence sur les mêmes pas et cumule le résultat d'une ``simulate``."""
    ledger = SimulatedLedger()
    tracker = EVTracker(ev, sessions)
    by_start = {f.start: f for f in result.flows}
    prev_soc = battery_start.soc_kwh
    for s in slots:
        car = tracker.for_slot(s.start)
        flow = by_start.get(s.start)
        if flow is None:
            continue
        base_imp, base_exp, _ = baseline_step(s, car)
        d_cell = flow.soc_battery_kwh - prev_soc
        loss = flow.battery_charge_kwh - flow.battery_discharge_kwh - d_cell
        prev_soc = flow.soc_battery_kwh
        ledger.record(flow, base_imp, base_exp, loss)
    return ledger
