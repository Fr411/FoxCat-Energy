"""Comparateur de tarifs : rejoue N tarifs sur la même consommation mesurée.

Limite à rappeler à l'utilisateur : la comparaison est « à comportement
constant ». FoxCat décale le ballon et les machines selon le tarif actif ; sous
un autre tarif, la consommation aurait été différente.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from .models import INJECTION_NONE, Tariff
from .valuation import CostBreakdown, Slot, value_series

METHOD_NOTE = (
    "Comparaison à comportement constant : la consommation mesurée est rejouée "
    "avec chaque tarif. FoxCat adapte le pilotage au tarif actif ; sous un autre "
    "tarif, la consommation aurait été différente."
)


def compare_tariffs(
    window_slots: list[Slot],
    tariffs: Iterable[Tariff],
    *,
    month_slots: list[Slot] | None = None,
    reference_id: str | None = None,
) -> dict[str, Any]:
    """Valorise chaque tarif et calcule l'écart par rapport à ``reference_id``."""
    costs: dict[str, CostBreakdown] = {}
    names: dict[str, str] = {}
    injection_valued: dict[str, bool] = {}
    for tariff in tariffs:
        injection_valued[tariff.id] = tariff.injection_kind != INJECTION_NONE
        costs[tariff.id] = value_series(window_slots, tariff, month_slots=month_slots)
        names[tariff.id] = tariff.name

    reference = costs.get(reference_id) if reference_id else None
    ranking = sorted(costs, key=lambda tid: costs[tid].total_eur)
    result: dict[str, Any] = {
        "slots": len(window_slots),
        "import_kwh": round(sum(max(s.import_kwh, 0.0) for s in window_slots), 4),
        "export_kwh": round(sum(max(s.export_kwh, 0.0) for s in window_slots), 4),
        "cheapest": ranking[0] if ranking else None,
        "cheapest_name": names.get(ranking[0]) if ranking else None,
        "tariffs": {},
        "method": METHOD_NOTE,
    }
    for tid in ranking:
        entry = costs[tid].to_dict()
        entry["name"] = names[tid]
        entry["reinjection_valorisee"] = injection_valued[tid]
        if reference is not None:
            entry["ecart_vs_reference_eur"] = round(costs[tid].total_eur - reference.total_eur, 4)
        result["tariffs"][tid] = entry
    return result


def window_bounds(now: datetime, period: str) -> tuple[datetime, datetime]:
    """Bornes (début, maintenant) d'une période : ``today`` ou ``month``."""
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0), now
    if period == "month":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0), now
    raise ValueError(f"période inconnue : {period!r}")
