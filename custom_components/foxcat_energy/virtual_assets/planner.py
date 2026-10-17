"""Planificateur déterministe à horizon glissant (simulation uniquement).

Priorités (de la plus forte à la plus faible) :
1. contraintes physiques (puissance, capacité, plancher SoC : portées par les modèles) ;
2. besoin de départ du VE ;
3. surplus solaire (VE puis batterie) ;
4. réduction d'import (décharge jusqu'à la réserve) ;
5. arbitrage tarifaire (charge réseau uniquement si le gain net dépasse la marge) ;
6. préservation de la réserve (plancher de toute décharge discrétionnaire) ;
7. minimisation de l'usure (coût d'usure déduit des gains).
Un prix manquant n'est jamais fabriqué : pas d'arbitrage ni de retenue sur ce pas.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Sequence

from .battery import VirtualBattery
from .config import PlannerConfig
from .ev import EVSession, EVTracker, VirtualEV
from .models import DataQuality, Slot, SlotFlow

_EPS = 1e-9


@dataclass(frozen=True, slots=True)
class SimulationResult:
    flows: tuple[SlotFlow, ...]
    skipped: tuple[tuple[object, str], ...]   # (start, raison) : pas ignorés faute de données
    battery: VirtualBattery
    ev: VirtualEV | None
    ev_reports: tuple[tuple[EVSession, float], ...] = ()   # (session, kWh cellule manquants)


def _net(slot: Slot) -> float:
    """pv - charge ; 0 si une donnée manque (aucune valeur inventée)."""
    if slot.load_kwh is None or slot.pv_kwh is None:
        return 0.0
    return slot.pv_kwh - slot.load_kwh


def _ev_allocation(first: Slot, window: list[Slot], ev: VirtualEV) -> float:
    """Part d'énergie VE (AC) allouée au premier pas du plan de recharge sur la fenêtre."""
    if ev.session is None:
        return 0.0
    need = ev.need_ac_kwh()
    if need <= _EPS or not ev.plugged(first.start):
        return 0.0
    cands = []
    for idx, s in enumerate(window):
        cap = ev.max_charge_ac(s.start, s.hours)
        if cap <= _EPS:
            continue
        if _net(s) > _EPS:
            key = (0, 0.0, idx)
        elif s.import_price is not None:
            key = (1, s.import_price, idx)
        else:
            key = (2, 0.0, idx)
        cands.append((key, idx, cap))
    cands.sort()
    for _, idx, cap in cands:
        take = min(cap, need)
        if idx == 0:
            return take
        need -= take
        if need <= _EPS:
            break
    return 0.0


def _arbitrage_charge(window: list[Slot], battery: VirtualBattery, cfg: PlannerConfig,
                      wear: float) -> float:
    """Énergie AC à charger depuis le réseau sur le premier pas (0 si non rentable)."""
    first = window[0]
    p0 = first.import_price
    if p0 is None:
        return 0.0
    eta_c, eta_d = battery.spec.charge_efficiency, battery.spec.discharge_efficiency
    cost = p0 / (eta_c * eta_d) + wear
    delivered = 0.0
    surplus_stored = 0.0
    cheaper_seen = False
    for s in window[1:]:
        if s.import_price is not None and s.import_price < p0:
            cheaper_seen = True
        if _net(s) > 0:
            surplus_stored += _net(s) * eta_c
        elif _net(s) < 0 and s.import_price is not None and not cheaper_seen \
                and s.import_price - cost >= cfg.min_arbitrage_margin_eur_kwh:
            delivered += -_net(s)
    if delivered <= _EPS:
        return 0.0
    have = max(battery.soc_kwh - battery.reserve_kwh, 0.0)
    stored_target = delivered / eta_d - have - surplus_stored
    if stored_target <= _EPS:
        return 0.0
    return min(stored_target / eta_c, battery.max_charge_ac(first.hours))


def _holdback(window: list[Slot], first: Slot) -> float:
    """Énergie AC à garder pour des pas futurs strictement plus chers (déficits)."""
    if first.import_price is None:
        return 0.0
    return sum(-_net(s) for s in window[1:]
               if _net(s) < 0 and s.import_price is not None and s.import_price > first.import_price)


def plan_and_apply(window: list[Slot], battery: VirtualBattery, ev: VirtualEV | None,
                   cfg: PlannerConfig) -> SlotFlow:
    """Décide pour ``window[0]`` et applique la décision aux modèles (clones appelant)."""
    s = window[0]
    h = s.hours
    load, pv = float(s.load_kwh), float(s.pv_kwh)  # type: ignore[arg-type]
    reasons: list[str] = []
    wear = cfg.wear_cost_eur_per_kwh
    if wear is None:
        wear = battery.wear_cost_eur_per_kwh()
    if wear is None:
        wear = 0.0
        reasons.append("wear_unknown")
    net = pv - load

    ev_ac = 0.0
    if ev is not None:
        ev_ac = ev.charge(_ev_allocation(s, window, ev), s.start, h)
    pv_for_ev = min(max(net, 0.0), ev_ac)
    ev_grid = ev_ac - pv_for_ev
    if ev_ac > _EPS:
        reasons.append("ev_departure_need" if ev_grid > _EPS else "ev_solar")
        if ev_grid > _EPS and s.import_price is None:
            reasons.append("price_missing_ev_must_charge")
    surplus = max(net, 0.0) - pv_for_ev
    deficit = max(-net, 0.0)

    bat_chg = bat_grid = bat_dis = 0.0
    if surplus > _EPS:
        bat_chg = battery.charge(surplus, h)
        if bat_chg > _EPS:
            reasons.append("solar_surplus_to_battery")
    if deficit > _EPS:
        price_ok = s.import_price is None or s.import_price - wear > 0
        if not price_ok:
            reasons.append("wear_exceeds_price")
        else:
            total_avail = battery.max_discharge_ac(1e9, battery.reserve_kwh)
            allowed = max(total_avail - _holdback(window, s), 0.0)
            if allowed < total_avail - _EPS:
                reasons.append("holdback_for_higher_price")
            bat_dis = battery.discharge(min(deficit, allowed), h, battery.reserve_kwh)
            if bat_dis > _EPS:
                reasons.append("import_reduction")
        if battery.soc_kwh <= battery.reserve_kwh + _EPS:
            reasons.append("reserve_preserved")
    if cfg.allow_grid_arbitrage and bat_dis <= _EPS and surplus - bat_chg <= _EPS:
        if s.import_price is None:
            reasons.append("price_missing_no_arbitrage")
        else:
            grid_ac = battery.charge(_arbitrage_charge(window, battery, cfg, wear), h)
            if grid_ac > _EPS:
                bat_grid = grid_ac
                bat_chg += grid_ac
                reasons.append("tariff_arbitrage")

    export = max(surplus - (bat_chg - bat_grid), 0.0)
    imp = max(deficit - bat_dis, 0.0) + ev_grid + bat_grid
    action = ("charge_battery_grid" if bat_grid > _EPS else
              "discharge_battery" if bat_dis > _EPS else
              "charge_battery_solar" if bat_chg > _EPS else
              "charge_ev" if ev_ac > _EPS else "idle")
    return SlotFlow(
        start=s.start, hours=h, action=action, reasons=tuple(reasons), load_kwh=load, pv_kwh=pv,
        battery_charge_kwh=bat_chg, battery_charge_from_grid_kwh=bat_grid,
        battery_discharge_kwh=bat_dis, ev_charge_kwh=ev_ac, ev_charge_from_grid_kwh=ev_grid,
        import_kwh=imp, export_kwh=export, soc_battery_kwh=battery.soc_kwh,
        soc_ev_kwh=0.0 if ev is None else ev.soc_kwh, import_price=s.import_price,
        export_price=s.export_price, quality=DataQuality.SIMULATED,
        price_quality=s.price_quality)


def simulate(slots, battery: VirtualBattery, ev: VirtualEV | None,
             cfg: PlannerConfig | None = None, sessions: Sequence[EVSession] = ()
             ) -> SimulationResult:
    """Horizon glissant : re-planifie à chaque pas sur ``cfg.horizon_slots``.

    Travaille sur des clones ; ni ``battery`` ni ``ev`` ni ``slots`` ne sont modifiés.
    Sans ``sessions``, la session de ``ev`` (s'il en a une) est utilisée.
    """
    cfg = cfg or PlannerConfig()
    slots = list(slots)
    bat = battery.clone()
    tracker = EVTracker(ev, sessions)
    flows: list[SlotFlow] = []
    skipped: list[tuple[object, str]] = []
    for i, s in enumerate(slots):
        car = tracker.for_slot(s.start)
        if s.load_kwh is None or s.pv_kwh is None:
            skipped.append((s.start, "missing_load_or_pv"))
            continue
        flows.append(plan_and_apply(slots[i:i + cfg.horizon_slots], bat, car, cfg))
    if slots:
        tracker.finish(slots[-1].start + timedelta(hours=slots[-1].hours))
    return SimulationResult(tuple(flows), tuple(skipped), bat, tracker.car,
                            tuple(tracker.reports))
