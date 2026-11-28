"""Planificateur bi-horaire : place les machines dans les heures creuses (HC).

Logique pure. Deux niveaux de prix seulement (HP / HC), mais les mêmes principes que le planificateur
dynamique : le cycle **entier** doit tenir dans une plage utilisateur et avant l'échéance, le coût est
intégré créneau par créneau (un cycle qui déborde sur les HP paie ses minutes HP), le surplus solaire
vaut la valeur de réinjection, et on ne reporte que si l'économie dépasse le minimum du mode.

Particularités du bi-horaire (inspirées d'EVCC « plan avant échéance » et des départs différés des
appareils) :

* heure de départ **différée** affichée (démarrage prévu au début des HC ou à l'ouverture de la plage) ;
* choix du **meilleur départ dans les HC** : tôt si le solaire ou l'échéance l'exigent, sinon dès que
  le cycle tient entièrement en HC ;
* HP et HC identiques (ou écart sous l'économie minimale) : aucun report, démarrage immédiat.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ..engine.models import EnergySnapshot, SolarForecast
from ..loads.machines import MachineDefinition
from ..tariff.tariff import tariff_period
from .dynamic_planner import BAND_HC, BAND_HP, MAX_HORIZON_H, build_dynamic_plan
from .economic_optimizer import PricePoint, build_hphc_points


def _periods(points: list[PricePoint], now: datetime, settings: dict[str, Any]) -> list[dict[str, Any]]:
    """Suite de plages HP/HC consécutives (début, fin, période, prix) sur l'horizon."""
    runs: list[dict[str, Any]] = []
    for point in points:
        label = tariff_period(point.at, settings)
        if runs and runs[-1]["period"] == label:
            continue
        runs.append({"period": label, "start": point.at, "price_eur_kwh": round(point.price, 5)})
    for index, run in enumerate(runs):
        run["end"] = runs[index + 1]["start"] if index + 1 < len(runs) else points[-1].at
    return [
        {
            **run,
            "start": run["start"].isoformat(),
            "end": run["end"].isoformat(),
            "start_ts": int(run["start"].timestamp()),
            "end_ts": int(run["end"].timestamp()),
        }
        for run in runs
        if run["end"] > now
    ]


def build_bihoraire_plan(
    *,
    now: datetime,
    snapshot: EnergySnapshot,
    settings: dict[str, Any],
    bihoraire_active: bool,
    hp_price: float | None,
    hc_price: float | None,
    export_points: list[PricePoint],
    machines: list[MachineDefinition],
    learning: dict[str, Any],
    cycles: dict[str, dict[str, Any]],
    solar_forecast: SolarForecast | None = None,
    previous: dict[str, str] | None = None,
    peak_shaving_active: bool = False,
) -> dict[str, Any]:
    """Plan des machines en bi-horaire ; même format de sortie que le planificateur dynamique."""
    if not bihoraire_active:
        return {"active": False, "ready": False, "machines": {}, "timeline": [], "state": {},
                "reason": "Planificateur bi-horaire réservé au tarif bi-horaire."}
    if hp_price is None or hc_price is None:
        return {"active": True, "ready": False, "machines": {}, "timeline": [], "state": {},
                "reason": "Prix HP ou HC indisponible."}

    points = build_hphc_points(now, settings, hp_price, hc_price, horizon_hours=int(MAX_HORIZON_H))
    plan = build_dynamic_plan(
        now=now, snapshot=snapshot, settings=settings, dynamic_active=True, import_points=points,
        export_points=export_points, machines=machines, learning=learning, cycles=cycles,
        solar_forecast=solar_forecast, previous=previous, peak_shaving_active=peak_shaving_active,
        tomorrow_available=True, band_for=lambda at, _price: tariff_period(at, settings),
    )
    if not plan.get("ready"):
        return plan
    spread = float(hp_price) - float(hc_price)
    periods = _periods(points, now, settings)
    plan.update(
        kind="BIHORAIRE",
        reason="Planificateur bi-horaire : cycles complets placés dans les heures creuses.",
        period=tariff_period(now, settings),
        hp_price_eur_kwh=round(float(hp_price), 5),
        hc_price_eur_kwh=round(float(hc_price), 5),
        spread_eur_kwh=round(spread, 5),
        periods=periods,
        next_hc=next((p for p in periods if p["period"] == BAND_HC), None),
        next_hp=next((p for p in periods if p["period"] == BAND_HP), None),
    )
    for key in ("next_valley", "next_peak", "current_rank_pct", "tomorrow_available"):
        plan.pop(key, None)
    if spread <= 0:
        plan["note"] = "HP et HC au même prix (ou HC plus cher) : aucun report n'est rentable."
    return plan
