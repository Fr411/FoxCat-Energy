"""Mode shadow : simule en parallèle des données réelles sans toucher à l'état physique.

Les entrées (``Slot``) sont immuables et seulement lues ; l'état simulé (batterie/VE) et le
ledger sont propres au shadow. Les données réelles restent « measured » ; tout le reste est
« simulated » ou « estimated ».
"""
from __future__ import annotations

from typing import Any, Sequence

from .accounting import SimulatedLedger, baseline_step
from .battery import VirtualBattery
from .config import PlannerConfig, VirtualAssetsConfig
from .ev import EVSession, EVTracker, VirtualEV
from .models import DataQuality, Slot, SlotFlow
from .planner import plan_and_apply


class ShadowSimulator:
    def __init__(self, config: VirtualAssetsConfig, sessions: Sequence[EVSession] = ()) -> None:
        self.config = config
        self.battery = VirtualBattery(config.battery)
        ev = None if config.ev is None else VirtualEV(config.ev)
        self._tracker = EVTracker(ev, sessions)
        self._base_tracker = EVTracker(ev, sessions)
        self.ledger = SimulatedLedger()
        self.real_totals = {"load_kwh": 0.0, "pv_kwh": 0.0, "slots": 0, "quality": "measured"}
        self.skipped = 0
        self.last_flow: SlotFlow | None = None

    def observe(self, slot: Slot, forecast: Sequence[Slot] = ()) -> SlotFlow | None:
        """Traite un pas réel ; ``forecast`` (estimé) n'alimente que la planification."""
        if not self.config.enabled:
            return None
        car = self._tracker.for_slot(slot.start)
        base_car = self._base_tracker.for_slot(slot.start)
        if slot.load_kwh is None or slot.pv_kwh is None:
            self.skipped += 1
            return None
        self.real_totals["load_kwh"] += slot.load_kwh
        self.real_totals["pv_kwh"] += slot.pv_kwh
        self.real_totals["slots"] += 1
        before = self.battery.soc_kwh
        window = [slot, *forecast][: self.config.planner.horizon_slots]
        flow = plan_and_apply(window, self.battery, car, self.config.planner)
        b_imp, b_exp, _ = baseline_step(slot, base_car)
        loss = flow.battery_charge_kwh - flow.battery_discharge_kwh - (self.battery.soc_kwh - before)
        self.ledger.record(flow, b_imp, b_exp, loss)
        self.last_flow = flow
        return flow

    def snapshot(self) -> dict[str, Any]:
        car = self._tracker.car
        return {
            "mode": "shadow",
            "real": dict(self.real_totals),
            "simulated": {
                "quality": DataQuality.SIMULATED.value,
                "battery_soc_pct": round(self.battery.soc_pct, 3),
                "battery_cycles": round(self.battery.equivalent_cycles, 4),
                "ev_soc_kwh": None if car is None else round(car.soc_kwh, 4),
                "last_action": None if self.last_flow is None else self.last_flow.action,
                "last_reasons": [] if self.last_flow is None else list(self.last_flow.reasons),
            },
            "skipped_slots": self.skipped,
            "accounting": self.ledger.summary(),
        }
