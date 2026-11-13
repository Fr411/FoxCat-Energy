"""Modèle de tarif FoxCat : un tarif est un ensemble de composantes.

Module pur (stdlib uniquement) : aucun import Home Assistant, donc testable
unitairement. Un tarif décrit comment valoriser une consommation ; il ne décide
rien. Les listes déroulantes historiques (mono, bi-horaire, Impact, dynamique)
deviennent de simples modèles de départ (voir ``templates.py``).

Composantes :
  * énergie : fixe, par plages horaires, ou prix observé (courbe réellement lue) ;
  * réseau : compléments €/kWh par plages (ignorés si le prix est « tout compris ») ;
  * réinjection : aucune, fixe ou observée ;
  * frais fixes annuels ;
  * terme capacitaire : forfait annuel, ou pointe mensuelle au quart d'heure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ENERGY_FIXED = "fixed"
ENERGY_PERIODS = "periods"
ENERGY_OBSERVED = "observed"
ENERGY_KINDS = (ENERGY_FIXED, ENERGY_PERIODS, ENERGY_OBSERVED)

INJECTION_NONE = "none"
INJECTION_FIXED = "fixed"
INJECTION_OBSERVED = "observed"
INJECTION_KINDS = (INJECTION_NONE, INJECTION_FIXED, INJECTION_OBSERVED)

CAPACITY_NONE = "none"
CAPACITY_FLAT = "flat"
CAPACITY_PEAK = "peak_monthly"
CAPACITY_KINDS = (CAPACITY_NONE, CAPACITY_FLAT, CAPACITY_PEAK)

ALL_DAYS = (0, 1, 2, 3, 4, 5, 6)


class TariffError(ValueError):
    """Définition de tarif invalide."""


def parse_minutes(value: Any) -> int:
    """Convertit « HH:MM » ou « HH:MM:SS » en minutes depuis minuit."""
    try:
        parts = str(value).strip().split(":")
        hours, minutes = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except (TypeError, ValueError, IndexError) as exc:
        raise TariffError(f"heure invalide : {value!r}") from exc
    if not (0 <= hours <= 24 and 0 <= minutes < 60) or (hours == 24 and minutes):
        raise TariffError(f"heure invalide : {value!r}")
    return hours * 60 + minutes


def _number(value: Any, label: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool):
        raise TariffError(f"{label} : nombre attendu")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise TariffError(f"{label} : nombre attendu") from exc
    if result != result or result in (float("inf"), float("-inf")):
        raise TariffError(f"{label} : nombre fini attendu")
    if minimum is not None and result < minimum:
        raise TariffError(f"{label} : doit être ≥ {minimum}")
    return result


@dataclass(frozen=True, slots=True)
class Period:
    """Plage horaire. ``price`` est un prix (énergie) ou un complément (réseau), en €/kWh.

    Une plage qui franchit minuit (22:00 → 07:00) est acceptée ; ``start == end``
    signifie « jamais ». Les jours sont ceux du début du créneau évalué
    (0 = lundi … 6 = dimanche).
    """

    name: str
    start: str
    end: str
    price: float
    days: tuple[int, ...] = ALL_DAYS

    def validate(self) -> None:
        parse_minutes(self.start)
        parse_minutes(self.end)
        if not self.days or any(d not in ALL_DAYS for d in self.days):
            raise TariffError(f"plage {self.name!r} : jours invalides")
        _number(self.price, f"plage {self.name!r} : prix")

    def contains(self, minute_of_day: float, weekday: int) -> bool:
        if weekday not in self.days:
            return False
        start, end = parse_minutes(self.start), parse_minutes(self.end)
        if start == end:
            return False
        if start < end:
            return start <= minute_of_day < end
        return minute_of_day >= start or minute_of_day < end

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "start": self.start, "end": self.end,
            "price": self.price, "days": list(self.days),
        }

    @classmethod
    def from_dict(cls, raw: Any) -> "Period":
        if not isinstance(raw, dict):
            raise TariffError("plage : objet attendu")
        days = raw.get("days", ALL_DAYS)
        try:
            days_t = tuple(int(d) for d in days)
        except (TypeError, ValueError) as exc:
            raise TariffError("plage : jours invalides") from exc
        period = cls(
            name=str(raw.get("name") or "plage"),
            start=str(raw.get("start", "00:00")),
            end=str(raw.get("end", "00:00")),
            price=_number(raw.get("price", 0.0), "plage : prix"),
            days=days_t,
        )
        period.validate()
        return period


@dataclass(frozen=True, slots=True)
class CapacityTerm:
    """Terme capacitaire.

    ``flat`` : forfait ``eur_per_year`` (Bruxelles).
    ``peak_monthly`` : ``max(pointe mensuelle au quart d'heure, min_kw)`` × ``eur_per_kw_year`` / 12 (Flandre).
    """

    kind: str = CAPACITY_NONE
    eur_per_year: float = 0.0
    eur_per_kw_year: float = 0.0
    min_kw: float = 0.0

    def validate(self) -> None:
        if self.kind not in CAPACITY_KINDS:
            raise TariffError(f"terme capacitaire inconnu : {self.kind!r}")
        _number(self.eur_per_year, "capacitaire : forfait", minimum=0.0)
        _number(self.eur_per_kw_year, "capacitaire : €/kW/an", minimum=0.0)
        _number(self.min_kw, "capacitaire : minimum kW", minimum=0.0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind, "eur_per_year": self.eur_per_year,
            "eur_per_kw_year": self.eur_per_kw_year, "min_kw": self.min_kw,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> "CapacityTerm":
        if raw is None:
            return cls()
        if not isinstance(raw, dict):
            raise TariffError("capacitaire : objet attendu")
        term = cls(
            kind=str(raw.get("kind", CAPACITY_NONE)),
            eur_per_year=_number(raw.get("eur_per_year", 0.0), "capacitaire : forfait", minimum=0.0),
            eur_per_kw_year=_number(raw.get("eur_per_kw_year", 0.0), "capacitaire : €/kW/an", minimum=0.0),
            min_kw=_number(raw.get("min_kw", 0.0), "capacitaire : minimum kW", minimum=0.0),
        )
        term.validate()
        return term


@dataclass(frozen=True, slots=True)
class Tariff:
    """Définition complète d'un tarif."""

    id: str
    name: str
    energy_kind: str = ENERGY_FIXED
    # Prix fixe (ENERGY_FIXED) ou prix hors plages (ENERGY_PERIODS), en €/kWh.
    energy_price: float = 0.0
    energy_periods: tuple[Period, ...] = ()
    # Prix « tout compris » : réseau, taxes et marge sont déjà dans le prix.
    all_in: bool = False
    # Compléments ignorés quand ``all_in`` est vrai.
    network_periods: tuple[Period, ...] = ()
    # Complément appliqué hors de toutes les plages réseau (ex. HC, MEDIUM).
    network_default: float = 0.0
    # Complément plat ajouté dans tous les cas (marge, taxes).
    adder_flat: float = 0.0
    injection_kind: str = INJECTION_NONE
    injection_price: float = 0.0
    fixed_fee_eur_year: float = 0.0
    capacity: CapacityTerm = field(default_factory=CapacityTerm)
    note: str = ""

    def validate(self) -> "Tariff":
        if not self.id or not str(self.id).strip():
            raise TariffError("tarif : identifiant manquant")
        if not self.name or not str(self.name).strip():
            raise TariffError("tarif : nom manquant")
        if self.energy_kind not in ENERGY_KINDS:
            raise TariffError(f"tarif {self.id} : type d'énergie inconnu {self.energy_kind!r}")
        if self.injection_kind not in INJECTION_KINDS:
            raise TariffError(f"tarif {self.id} : type de réinjection inconnu {self.injection_kind!r}")
        _number(self.energy_price, f"tarif {self.id} : prix énergie")
        _number(self.adder_flat, f"tarif {self.id} : complément")
        _number(self.network_default, f"tarif {self.id} : complément hors plages")
        _number(self.injection_price, f"tarif {self.id} : prix réinjection")
        _number(self.fixed_fee_eur_year, f"tarif {self.id} : frais fixes", minimum=0.0)
        for period in (*self.energy_periods, *self.network_periods):
            period.validate()
        self.capacity.validate()
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "name": self.name, "energy_kind": self.energy_kind,
            "energy_price": self.energy_price,
            "energy_periods": [p.to_dict() for p in self.energy_periods],
            "all_in": self.all_in,
            "network_periods": [p.to_dict() for p in self.network_periods],
            "network_default": self.network_default,
            "adder_flat": self.adder_flat,
            "injection_kind": self.injection_kind,
            "injection_price": self.injection_price,
            "fixed_fee_eur_year": self.fixed_fee_eur_year,
            "capacity": self.capacity.to_dict(),
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> "Tariff":
        if not isinstance(raw, dict):
            raise TariffError("tarif : objet attendu")
        tariff = cls(
            id=str(raw.get("id") or "").strip(),
            name=str(raw.get("name") or "").strip(),
            energy_kind=str(raw.get("energy_kind", ENERGY_FIXED)),
            energy_price=_number(raw.get("energy_price", 0.0), "prix énergie"),
            energy_periods=tuple(Period.from_dict(p) for p in raw.get("energy_periods", []) or []),
            all_in=bool(raw.get("all_in", False)),
            network_periods=tuple(Period.from_dict(p) for p in raw.get("network_periods", []) or []),
            network_default=_number(raw.get("network_default", 0.0), "complément hors plages"),
            adder_flat=_number(raw.get("adder_flat", 0.0), "complément"),
            injection_kind=str(raw.get("injection_kind", INJECTION_NONE)),
            injection_price=_number(raw.get("injection_price", 0.0), "prix réinjection"),
            fixed_fee_eur_year=_number(raw.get("fixed_fee_eur_year", 0.0), "frais fixes", minimum=0.0),
            capacity=CapacityTerm.from_dict(raw.get("capacity")),
            note=str(raw.get("note") or ""),
        )
        return tariff.validate()


def tariffs_from_json_value(raw: Any) -> list[Tariff]:
    """Accepte un tarif, ou une liste de tarifs (import JSON)."""
    items = raw if isinstance(raw, list) else [raw]
    tariffs = [Tariff.from_dict(item) for item in items]
    ids = [t.id for t in tariffs]
    if len(set(ids)) != len(ids):
        raise TariffError("identifiants de tarif en double")
    return tariffs
