"""Mode contrefactuel : recalcule un scénario historique sans muter les données enregistrées."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .accounting import SimulatedLedger, account_simulation
from .battery import VirtualBattery
from .config import BatterySpec, EVSpec, PlannerConfig
from .ev import EVSession, VirtualEV
from .models import Slot
from .planner import SimulationResult, simulate


@dataclass(frozen=True, slots=True)
class CounterfactualResult:
    simulation: SimulationResult
    ledger: SimulatedLedger

    def summary(self) -> dict[str, Any]:
        out = self.ledger.summary()
        out["mode"] = "counterfactual"
        out["skipped_slots"] = len(self.simulation.skipped)
        out["ev_shortfalls_kwh"] = [round(s, 6) for _, s in self.simulation.ev_reports]
        return out


def run_counterfactual(history: Sequence[Slot], battery_spec: BatterySpec,
                       ev_spec: EVSpec | None = None, sessions: Sequence[EVSession] = (),
                       cfg: PlannerConfig | None = None,
                       initial_soc_pct: float | None = None) -> CounterfactualResult:
    """``history`` (Slot immuables) est seulement lue ; état initial neuf à chaque appel."""
    slots = tuple(history)
    battery = VirtualBattery(battery_spec, initial_soc_pct)
    ev = None if ev_spec is None else VirtualEV(ev_spec)
    sim = simulate(slots, battery, ev, cfg, sessions)
    return CounterfactualResult(sim, account_simulation(slots, sim, battery, ev, sessions))
