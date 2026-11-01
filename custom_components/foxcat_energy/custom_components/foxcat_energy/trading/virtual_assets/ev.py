"""Véhicule électrique virtuel : charge seule (pas de V2G), besoin de départ validé."""
from __future__ import annotations

from copy import copy
from dataclasses import dataclass
from datetime import datetime, timedelta
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
        assert self.session is not None
        hours = min(hours, max((self.session.departure - at).total_seconds() / 3600.0, 0.0))
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
    """Suit des sessions explicites ou le rythme hebdomadaire du foyer."""

    def __init__(self, ev: VirtualEV | None, sessions: Sequence[EVSession] = ()) -> None:
        self.spec = None if ev is None else ev.spec
        own = [] if ev is None or ev.session is None else [ev.session]
        self.sessions = sorted(list(sessions) or own, key=lambda s: s.arrival)
        self._automatic = ev is not None and ev.session is None and not sessions
        self._automatic_session: EVSession | None = None
        self.car = None if ev is None else VirtualEV(ev.spec, None)
        if self._automatic and self.car is not None:
            self.car.soc_kwh = self.spec.capacity_kwh * self.spec.initial_soc_pct / 100
        self.reports: list[tuple[EVSession, float]] = []

    def for_slot(self, at: datetime) -> VirtualEV | None:
        if self._automatic:
            return self._automatic_for_slot(at)
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

    def _scheduled_session(self, at: datetime) -> EVSession | None:
        """Retourne la présence de nuit en semaine ou la présence continue du week-end."""
        weekday = at.weekday()
        if weekday == 0 and at.hour < 7 or weekday in (5, 6):
            days_since_friday = (weekday - 4) % 7
            friday = at.date() - timedelta(days=days_since_friday)
            arrival = at.replace(year=friday.year, month=friday.month, day=friday.day,
                                 hour=19, minute=0, second=0, microsecond=0)
            monday = friday + timedelta(days=3)
            departure = at.replace(year=monday.year, month=monday.month, day=monday.day,
                                   hour=7, minute=0, second=0, microsecond=0)
            target_pct = 100.0
        elif weekday < 5 and at.hour < 7:
            yesterday = at.date() - timedelta(days=1)
            arrival = at.replace(year=yesterday.year, month=yesterday.month, day=yesterday.day,
                                 hour=19, minute=0, second=0, microsecond=0)
            departure = at.replace(hour=7, minute=0, second=0, microsecond=0)
            target_pct = 80.0
        elif weekday < 5 and at.hour >= 19:
            arrival = at.replace(hour=19, minute=0, second=0, microsecond=0)
            if weekday == 4:
                monday = at.date() + timedelta(days=3)
                departure = at.replace(year=monday.year, month=monday.month, day=monday.day,
                                       hour=7, minute=0, second=0, microsecond=0)
                target_pct = 100.0
            else:
                departure = (at + timedelta(days=1)).replace(
                    hour=7, minute=0, second=0, microsecond=0
                )
                target_pct = 80.0
        else:
            return None

        assert self.car is not None and self.spec is not None
        arrival_pct = 100.0 * self.car.soc_kwh / self.spec.capacity_kwh
        return EVSession(arrival, departure, arrival_pct, target_pct)

    def _automatic_for_slot(self, at: datetime) -> VirtualEV:
        car = self.car
        assert car is not None and self.spec is not None
        active = self._automatic_session
        if active is not None and at >= active.departure:
            self.reports.append((active, car.departure_shortfall_kwh()))
            car.soc_kwh = max(0.0, car.soc_kwh - self.spec.trip_kwh)
            car.session = None
            self._automatic_session = None

        scheduled = self._scheduled_session(at)
        active = self._automatic_session
        if scheduled is None:
            car.session = None
        elif active is None or (
            active.arrival != scheduled.arrival or active.departure != scheduled.departure
        ):
            car.session = scheduled
            self._automatic_session = scheduled
        return car

    def finish(self, end: datetime) -> None:
        car = self.car
        if car is not None and car.session is not None and end >= car.session.departure:
            self.reports.append((car.session, car.departure_shortfall_kwh()))
