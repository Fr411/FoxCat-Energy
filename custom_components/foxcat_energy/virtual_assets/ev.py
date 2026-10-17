"""Véhicule électrique virtuel : charge seule (pas de V2G), besoin de départ validé."""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from .config import EVSpec
from .models import VirtualAssetsError, require_number


@dataclass(frozen=True, slots=True)
class EVSession:
    """Branchement : plage de présence, SoC à l'arrivée et SoC cible au départ."""

    arrival: datetime
    departure: datetime
    arrival_soc_pct: float
    target_soc_pct: float

    def __post_init__(self) -> None:
        if not self.arrival < self.departure:
            raise VirtualAssetsError("arrival doit précéder departure")
        require_number("arrival_soc_pct", self.arrival_soc_pct, minimum=0, maximum=100)
        require_number("target_soc_pct", self.target_soc_pct, minimum=0, maximum=100)


class VirtualEV:
    __slots__ = ("spec", "session", "soc_kwh")

    def __init__(self, spec: EVSpec, session: EVSession | None = None) -> None:
        self.spec = spec
        self.session = session
        self.soc_kwh = 0.0 if session is None else spec.capacity_kwh * session.arrival_soc_pct / 100

    def clone(self) -> "VirtualEV":
        return copy(self)

    @property
    def target_kwh(self) -> float:
        return 0.0 if self.session is None else \
            self.spec.capacity_kwh * self.session.target_soc_pct / 100

    def plugged(self, at: datetime) -> bool:
        return self.session is not None and self.session.arrival <= at < self.session.departure

    def need_cell_kwh(self) -> float:
        return max(self.target_kwh - self.soc_kwh, 0.0)

    def need_ac_kwh(self) -> float:
        return self.need_cell_kwh() / self.spec.charge_efficiency

    def max_charge_ac(self, at: datetime, hours: float) -> float:
        """Plafonné par la puissance et par la capacité restante ; 0 si débranché."""
        if not self.plugged(at):
            return 0.0
        room = max(self.spec.capacity_kwh - self.soc_kwh, 0.0) / self.spec.charge_efficiency
        return min(self.spec.max_charge_kw * hours, room)

    def charge(self, ac_kwh: float, at: datetime, hours: float) -> float:
        require_number("ac_kwh", ac_kwh, minimum=0)
        used = min(ac_kwh, self.max_charge_ac(at, hours))
        self.soc_kwh += used * self.spec.charge_efficiency
        return used

    def departure_shortfall_kwh(self) -> float:
        """Énergie cellule manquante par rapport à la cible de départ."""
        return self.need_cell_kwh()


class EVTracker:
    """Suit plusieurs sessions successives : un VE neuf à chaque branchement."""

    def __init__(self, ev: VirtualEV | None, sessions: Sequence[EVSession] = ()) -> None:
        self.spec = None if ev is None else ev.spec
        own = [] if ev is None or ev.session is None else [ev.session]
        self.sessions = sorted(list(sessions) or own, key=lambda s: s.arrival)
        self.car = None if ev is None else VirtualEV(ev.spec, None)
        self.reports: list[tuple[EVSession, float]] = []

    def for_slot(self, at: datetime) -> VirtualEV | None:
        car = self.car
        if car is None:
            return None
        cur = car.session
        if cur is not None and cur.arrival <= at < cur.departure:
            return car
        if cur is not None:
            self.reports.append((cur, car.departure_shortfall_kwh()))
        nxt = next((s for s in self.sessions if s.arrival <= at < s.departure), None)
        self.car = VirtualEV(self.spec, nxt)  # type: ignore[arg-type]
        return self.car

    def finish(self, end: datetime) -> None:
        car = self.car
        if car is not None and car.session is not None and end >= car.session.departure:
            self.reports.append((car.session, car.departure_shortfall_kwh()))
