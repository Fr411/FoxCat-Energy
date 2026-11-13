"""Valorisation d'une consommation selon un tarif (fonction pure).

Entrée : une série de créneaux d'un quart d'heure (kWh importés / exportés et
prix réellement observés). Sortie : le coût détaillé par composante.
Aucune dépendance à Home Assistant.
"""
from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from .models import (
    CAPACITY_FLAT,
    CAPACITY_PEAK,
    ENERGY_FIXED,
    ENERGY_OBSERVED,
    ENERGY_PERIODS,
    INJECTION_FIXED,
    INJECTION_OBSERVED,
    Period,
    Tariff,
)

SLOT_HOURS = 0.25
HOURS_PER_YEAR = 24.0 * 365.0


@dataclass(frozen=True, slots=True)
class Slot:
    """Un quart d'heure de consommation.

    ``buy`` et ``sell`` sont les prix réellement observés pendant le créneau
    (€/kWh, ``None`` si inconnus). Ils servent aux tarifs de type « observé ».
    """

    at: datetime
    import_kwh: float
    export_kwh: float
    buy: float | None = None
    sell: float | None = None


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    """Coût détaillé d'un tarif sur une fenêtre."""

    energy_eur: float = 0.0
    network_eur: float = 0.0
    fixed_eur: float = 0.0
    capacity_eur: float = 0.0
    injection_revenue_eur: float = 0.0
    import_kwh: float = 0.0
    export_kwh: float = 0.0
    unpriced_import_kwh: float = 0.0

    @property
    def total_eur(self) -> float:
        """Facture nette : coûts moins revenu de réinjection."""
        return (
            self.energy_eur + self.network_eur + self.fixed_eur
            + self.capacity_eur - self.injection_revenue_eur
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "energie_eur": round(self.energy_eur, 4),
            "reseau_eur": round(self.network_eur, 4),
            "frais_fixes_eur": round(self.fixed_eur, 4),
            "capacitaire_eur": round(self.capacity_eur, 4),
            "reinjection_eur": round(self.injection_revenue_eur, 4),
            "total_eur": round(self.total_eur, 4),
            "import_kwh": round(self.import_kwh, 4),
            "export_kwh": round(self.export_kwh, 4),
            "import_sans_prix_kwh": round(self.unpriced_import_kwh, 4),
        }


def _minute(at: datetime) -> float:
    return at.hour * 60 + at.minute + at.second / 60.0


def _first_match(periods: Iterable[Period], at: datetime) -> Period | None:
    minute, weekday = _minute(at), at.weekday()
    for period in periods:
        if period.contains(minute, weekday):
            return period
    return None


def energy_unit_price(tariff: Tariff, slot: Slot) -> float | None:
    """Prix d'énergie du créneau, ou ``None`` s'il est inconnu (tarif observé sans prix)."""
    if tariff.energy_kind == ENERGY_FIXED:
        return tariff.energy_price
    if tariff.energy_kind == ENERGY_PERIODS:
        period = _first_match(tariff.energy_periods, slot.at)
        return period.price if period is not None else tariff.energy_price
    if tariff.energy_kind == ENERGY_OBSERVED:
        return slot.buy
    return None


def network_unit_price(tariff: Tariff, slot: Slot) -> float:
    """Complément réseau / taxes / marge. Toujours nul pour un prix tout compris."""
    if tariff.all_in:
        return 0.0
    period = _first_match(tariff.network_periods, slot.at)
    base = period.price if period is not None else tariff.network_default
    return base + tariff.adder_flat


def injection_unit_price(tariff: Tariff, slot: Slot) -> float:
    if tariff.injection_kind == INJECTION_FIXED:
        return tariff.injection_price
    if tariff.injection_kind == INJECTION_OBSERVED:
        return slot.sell if slot.sell is not None else 0.0
    return 0.0


def monthly_peak_kw(slots: Iterable[Slot]) -> float:
    """Pointe d'import au quart d'heure (kW) : kWh du quart d'heure ÷ 0,25 h."""
    peak = 0.0
    for slot in slots:
        peak = max(peak, max(slot.import_kwh, 0.0) / SLOT_HOURS)
    return peak


def capacity_cost(
    tariff: Tariff,
    window_slots: list[Slot],
    month_slots: list[Slot],
    month_hours: float,
) -> float:
    """Terme capacitaire attribuable à la fenêtre.

    Le coût mensuel est réparti au prorata de la durée de la fenêtre dans le
    mois (``month_hours``). Pour un mois en cours, c'est donc une estimation
    « à ce jour » fondée sur la pointe déjà observée.
    """
    term = tariff.capacity
    if not window_slots or month_hours <= 0:
        return 0.0
    share = len(window_slots) * SLOT_HOURS / month_hours
    if term.kind == CAPACITY_FLAT:
        monthly = term.eur_per_year / 12.0
    elif term.kind == CAPACITY_PEAK:
        billed_kw = max(monthly_peak_kw(month_slots), term.min_kw)
        monthly = billed_kw * term.eur_per_kw_year / 12.0
    else:
        return 0.0
    return monthly * min(share, 1.0)


def hours_in_month(at: datetime) -> float:
    return calendar.monthrange(at.year, at.month)[1] * 24.0


def value_series(
    window_slots: list[Slot],
    tariff: Tariff,
    *,
    month_slots: list[Slot] | None = None,
) -> CostBreakdown:
    """Valorise ``window_slots`` avec ``tariff``.

    ``month_slots`` (créneaux du mois civil entier déjà observés) sert à la
    pointe capacitaire ; à défaut, la fenêtre elle-même est utilisée.
    """
    energy = network = injection = import_kwh = export_kwh = unpriced = 0.0
    for slot in window_slots:
        imp = max(slot.import_kwh, 0.0)
        exp = max(slot.export_kwh, 0.0)
        import_kwh += imp
        export_kwh += exp
        price = energy_unit_price(tariff, slot)
        if price is None:
            unpriced += imp
        else:
            energy += imp * price
        network += imp * network_unit_price(tariff, slot)
        injection += exp * injection_unit_price(tariff, slot)

    fixed = tariff.fixed_fee_eur_year * (len(window_slots) * SLOT_HOURS / HOURS_PER_YEAR)
    capacity = 0.0
    if window_slots:
        reference = month_slots if month_slots else window_slots
        capacity = capacity_cost(
            tariff, window_slots, reference, hours_in_month(window_slots[0].at)
        )
    return CostBreakdown(
        energy_eur=energy,
        network_eur=network,
        fixed_eur=fixed,
        capacity_eur=capacity,
        injection_revenue_eur=injection,
        import_kwh=import_kwh,
        export_kwh=export_kwh,
        unpriced_import_kwh=unpriced,
    )
