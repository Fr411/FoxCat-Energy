"""Planificateur dynamique : planifie les charges flexibles sur la courbe de prix dynamique.

Logique pure (aucun accès Home Assistant). Idées reprises d'autres EMS :

* **EVCC** : « énergie requise avant une échéance » → on choisit les créneaux les moins chers ; un
  plan déjà établi n'est remplacé que si le nouveau est nettement meilleur (stabilité du plan).
* **Predbat** : bandes de prix par rang (très bas, bas, normal, élevé, pic) plutôt que seuils fixes ;
  le prix négatif déclenche tout de suite.
* **EMHASS** : charges différables avec fenêtre de démarrage, puissance parallèle limitée, valeur du
  surplus solaire à la valeur de réinjection.
* **Blueprints Nord Pool / Tibber** : « les N heures les moins chères » pour les charges interruptibles.

Le planificateur ne remplace pas les sécurités : un cycle protégé continue toujours, l'écrêtage bloque
tout nouveau départ, et le boiler reste décidé par ``dynamic_boiler_v2``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from ...const import DEFAULT_SETTINGS
from ..engine.models import EnergySnapshot, SolarForecast
from ..loads.machines import MachineDefinition
from .dynamic_scheduler import ScheduleWindow, _machine_windows, _parse_forecast_window
from .economic_optimizer import PricePoint

START_NOW = "START_NOW"
WAIT = "WAIT"
CONTINUE = "CONTINUE"
USER_CONTROL = "USER_CONTROL"
SAFETY_OVERRIDE = "SAFETY_OVERRIDE"

BAND_NEGATIVE = "NEGATIF"
BAND_VERY_LOW = "TRES_BAS"
BAND_LOW = "BAS"
BAND_NORMAL = "NORMAL"
BAND_HIGH = "ELEVE"
BAND_PEAK = "PIC"

# Rang (en % des créneaux connus, du moins cher au plus cher) qui borne chaque bande.
_BAND_LIMITS = ((15.0, BAND_VERY_LOW), (35.0, BAND_LOW), (70.0, BAND_NORMAL), (90.0, BAND_HIGH))

BAND_HC = "HC"
BAND_HP = "HP"

MAX_HORIZON_H = 36.0
SOLAR_SHARE_CAP = 0.5  # une fenêtre solaire prévue ne couvre au plus que la moitié de la puissance


@dataclass(frozen=True, slots=True)
class Slot:
    start: datetime
    end: datetime
    price: float
    rank_pct: float = 0.0
    band: str = BAND_NORMAL


@dataclass(frozen=True, slots=True)
class Segment:
    start: datetime
    end: datetime
    cost: float


def _setting(settings: dict[str, Any], key: str, default: float) -> float:
    try:
        return float(settings.get(key, DEFAULT_SETTINGS.get(key, default)))
    except (TypeError, ValueError):
        return default


def _step(points: list[PricePoint]) -> timedelta:
    gaps = [b.at - a.at for a, b in zip(points, points[1:]) if b.at > a.at]
    return min(gaps) if gaps else timedelta(hours=1)


def classify(price: float, rank_pct: float) -> str:
    """Bande d'un prix : un prix négatif prime sur le rang."""
    if price < 0:
        return BAND_NEGATIVE
    for limit, band in _BAND_LIMITS:
        if rank_pct <= limit:
            return band
    return BAND_PEAK


def build_slots(
    points: list[PricePoint],
    now: datetime,
    horizon_end: datetime,
    band_for: Callable[[datetime, float], str] | None = None,
) -> list[Slot]:
    """Transforme la courbe en créneaux [début, fin[ classés par rang de prix."""
    ordered = sorted({p.at: p for p in points}.values(), key=lambda p: p.at)
    if not ordered:
        return []
    step = _step(ordered)
    raw: list[tuple[datetime, datetime, float]] = []
    for index, point in enumerate(ordered):
        end = ordered[index + 1].at if index + 1 < len(ordered) else point.at + step
        if end - point.at > step * 1.5:  # trou dans la courbe : le créneau ne couvre que son pas
            end = point.at + step
        if end <= now or point.at >= horizon_end:
            continue
        raw.append((point.at, min(end, horizon_end), float(point.price)))
    prices = [price for _, _, price in raw]
    count = len(prices)
    slots: list[Slot] = []
    for start, end, price in raw:
        below = sum(1 for other in prices if other < price)
        equal = sum(1 for other in prices if other == price)
        rank = 100.0 * (below + 0.5 * equal) / count if count else 50.0
        band = band_for(start, price) if band_for else classify(price, rank)
        slots.append(Slot(start, end, price, rank, band))
    return slots


def interval_cost(slots: list[Slot], start: datetime, end: datetime) -> float | None:
    """Prix moyen pondéré (€/kWh) entre deux instants ; ``None`` si la courbe ne couvre pas tout."""
    total = (end - start).total_seconds()
    if total <= 0:
        return None
    covered = 0.0
    weighted = 0.0
    for slot in slots:
        a, b = max(slot.start, start), min(slot.end, end)
        if b > a:
            seconds = (b - a).total_seconds()
            covered += seconds
            weighted += seconds * slot.price
    if covered < total - 1.0:
        return None
    return weighted / covered


def _price_at(points: list[PricePoint], at: datetime) -> float | None:
    chosen = None
    for point in sorted(points, key=lambda p: p.at):
        if point.at <= at:
            chosen = float(point.price)
        else:
            break
    return chosen


def _profile(machine: MachineDefinition, learning: dict[str, Any]) -> tuple[float, float, str]:
    """Durée (h), puissance moyenne (W) et origine : apprentissage sur 10 cycles, sinon réglages."""
    stats = learning.get(machine.machine_id, {}) if isinstance(learning, dict) else {}
    duration_s = stats.get("average_duration_s_10")
    energy_wh = stats.get("average_energy_wh_10")
    if isinstance(duration_s, (int, float)) and duration_s > 0:
        duration_h = max(float(duration_s) / 3600.0, 0.25)
        source = "APPRENTISSAGE_10_CYCLES"
    else:
        duration_h = max(float(machine.cycle_duration_minutes) / 60.0, 0.25)
        source = "DUREE_CONFIGUREE"
    if isinstance(energy_wh, (int, float)) and energy_wh > 0:
        return duration_h, float(energy_wh) / duration_h, source
    return duration_h, max(float(machine.nominal_power_w), 1.0), source


def _clock(now: datetime, raw: str) -> datetime | None:
    try:
        hh, mm = str(raw).split(":")[:2]
        return now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
    except (TypeError, ValueError):
        return None


def _available_from(machine: MachineDefinition, now: datetime) -> datetime:
    moment = _clock(now, machine.available_from) if machine.available_from else None
    if moment is None:
        return now
    return moment if moment > now else now


def _deadline(machine: MachineDefinition, now: datetime, max_wait_h: float) -> datetime:
    cap = now + timedelta(hours=max(max_wait_h, 0.25))
    moment = _clock(now, machine.deadline) if machine.deadline else None
    if moment is not None:
        if moment <= now:
            moment += timedelta(days=1)
        return min(moment, cap)
    return min(now + timedelta(hours=max(float(machine.max_delay_hours), 1.0)), cap)


def _parallel_free(reservations: list[dict[str, Any]], start: datetime, end: datetime, power_w: float, max_w: float) -> bool:
    used = sum(r["power_w"] for r in reservations if start < r["end"] and end > r["start"])
    return used + power_w <= max_w


def _solar_share(
    *,
    start: datetime,
    end: datetime,
    now: datetime,
    power_w: float,
    export_w: float,
    solar_window: ScheduleWindow | None,
    confidence_pct: float,
    near: timedelta,
) -> float:
    """Part de la charge couverte par le solaire : surplus mesuré si départ immédiat, prévision sinon."""
    if power_w <= 0:
        return 0.0
    if start - now <= near:
        return max(0.0, min(1.0, export_w / power_w))
    if solar_window is None:
        return 0.0
    overlap_s = (min(end, solar_window.end) - max(start, solar_window.start)).total_seconds()
    ratio = max(0.0, min(1.0, overlap_s / max((end - start).total_seconds(), 1.0)))
    return ratio * max(0.0, min(1.0, confidence_pct / 100.0)) * SOLAR_SHARE_CAP


def _candidate_cost(
    *,
    slots: list[Slot],
    export_points: list[PricePoint],
    start: datetime,
    duration_h: float,
    power_w: float,
    share: float,
) -> float | None:
    end = start + timedelta(hours=duration_h)
    grid_price = interval_cost(slots, start, end)
    if grid_price is None:
        return None
    export_price = _price_at(export_points, start) if export_points else None
    solar_price = export_price if export_price is not None else 0.0
    unit = (1.0 - share) * grid_price + share * solar_price
    return unit * power_w / 1000.0 * duration_h


def _contiguous_starts(
    *, windows: list[ScheduleWindow], slots: list[Slot], earliest: datetime, latest: datetime, duration: timedelta
) -> list[datetime]:
    """Départs possibles : maintenant, chaque début de créneau et chaque ouverture de plage."""
    raw = {earliest}
    raw.update(slot.start for slot in slots)
    raw.update(window.start for window in windows)
    starts = []
    for start in sorted(raw):
        if start < earliest or start > latest:
            continue
        if any(window.start <= start and start + duration <= window.end for window in windows):
            starts.append(start)
    return starts


def _plan_interruptible(
    *,
    slots: list[Slot],
    windows: list[ScheduleWindow],
    earliest: datetime,
    latest_end: datetime,
    duration_h: float,
    power_w: float,
    reservations: list[dict[str, Any]],
    max_w: float,
) -> list[Segment] | None:
    """Les créneaux les moins chers (style « N heures les moins chères »), peu importe leur ordre."""
    pieces: list[tuple[float, datetime, datetime]] = []
    for slot in slots:
        for window in windows:
            a = max(slot.start, window.start, earliest)
            b = min(slot.end, window.end, latest_end)
            if b > a and _parallel_free(reservations, a, b, power_w, max_w):
                pieces.append((slot.price, a, b))
    pieces.sort(key=lambda item: (item[0], item[1]))
    remaining = duration_h * 3600.0
    chosen: list[Segment] = []
    for price, a, b in pieces:
        if remaining <= 0:
            break
        take = min((b - a).total_seconds(), remaining)
        end = a + timedelta(seconds=take)
        chosen.append(Segment(a, end, price * power_w / 1000.0 * take / 3600.0))
        remaining -= take
    if remaining > 1.0:
        return None
    chosen.sort(key=lambda seg: seg.start)
    return chosen


def _machine_entry(machine: MachineDefinition, decision: str, allow: bool, reason: str, **extra: Any) -> dict[str, Any]:
    return {"name": machine.name, "decision": decision, "allow_start_now": allow, "reason": reason, **extra}


def build_dynamic_plan(
    *,
    now: datetime,
    snapshot: EnergySnapshot,
    settings: dict[str, Any],
    dynamic_active: bool,
    import_points: list[PricePoint],
    export_points: list[PricePoint],
    machines: list[MachineDefinition],
    learning: dict[str, Any],
    cycles: dict[str, dict[str, Any]],
    solar_forecast: SolarForecast | None = None,
    previous: dict[str, str] | None = None,
    peak_shaving_active: bool = False,
    tomorrow_available: bool = False,
    band_for: Callable[[datetime, float], str] | None = None,
) -> dict[str, Any]:
    """Construit le plan des machines. ``previous`` : départs planifiés au calcul précédent (stabilité).

    ``band_for`` remplace les bandes par rang (ex. HP/HC en bi-horaire).
    """
    previous = previous or {}
    base = {"active": False, "ready": False, "machines": {}, "timeline": [], "slots": [], "state": {}}
    if not dynamic_active:
        return base | {"reason": "Planificateur dynamique réservé au tarif dynamique."}

    horizon_end = now + timedelta(hours=MAX_HORIZON_H)
    slots = build_slots(import_points, now, horizon_end, band_for)
    if not slots:
        return base | {"active": True, "reason": "Courbe de prix dynamique indisponible."}

    last_end = max(slot.end for slot in slots)
    horizon_end = min(horizon_end, last_end)
    step = _step(sorted(import_points, key=lambda p: p.at))
    current = next((slot for slot in slots if slot.start <= now < slot.end), slots[0])
    mode = str(settings.get("mode", "Éco"))
    comfort = mode == "Confort"
    wait_penalty = _setting(settings, "comfort_wait_penalty_eur_h" if comfort else "eco_wait_penalty_eur_h", 0.03 if comfort else 0.0)
    min_saving = _setting(settings, "comfort_min_saving_eur" if comfort else "eco_min_saving_eur", 0.10 if comfort else 0.03)
    max_wait_h = _setting(settings, "comfort_max_wait_h" if comfort else "eco_max_wait_h", 6.0 if comfort else 24.0)
    hysteresis_pct = max(0.0, _setting(settings, "dynamic_planner_hysteresis_pct", 5.0))
    max_parallel_w = min(
        _setting(settings, "planner_max_parallel_power_w", 5000.0),
        max(_setting(settings, "planner_grid_import_limit_w", 5000.0) + max(snapshot.pv_w, 0.0) - max(snapshot.house_w, 0.0), 100.0),
    )
    solar_on = bool(settings.get("solar_forecast_arbitrage", True))
    solar_window = _parse_forecast_window(now, solar_forecast) if solar_on else None
    confidence = float(getattr(solar_forecast, "confidence", 0.0) or 0.0)
    near = max(step / 2, timedelta(minutes=5))

    plan: dict[str, Any] = {
        "active": True,
        "ready": True,
        "reason": "Planificateur dynamique : créneaux les moins chers avant l'échéance.",
        "behavior": mode,
        "max_parallel_power_w": round(max_parallel_w, 0),
        "current_price_eur_kwh": round(current.price, 6),
        "current_band": current.band,
        "current_rank_pct": round(current.rank_pct, 1),
        "horizon_hours": round((horizon_end - now).total_seconds() / 3600.0, 2),
        "price_step_minutes": int(step.total_seconds() // 60),
        "tomorrow_available": bool(tomorrow_available),
        "slots": [
            {"start": s.start.isoformat(), "price": round(s.price, 5), "band": s.band, "rank_pct": round(s.rank_pct, 1)}
            for s in slots[:96]
        ],
        "next_valley": _next_block(slots, now, {BAND_HC} if band_for else {BAND_NEGATIVE, BAND_VERY_LOW, BAND_LOW}),
        "next_peak": _next_block(slots, now, {BAND_HP} if band_for else {BAND_PEAK, BAND_HIGH}),
        "machines": {},
        "timeline": [],
    }

    if peak_shaving_active:
        plan["safety_override"] = True
        plan["machines"] = {
            m.machine_id: _machine_entry(m, SAFETY_OVERRIDE, False, "Écrêtage : nouveau démarrage suspendu") for m in machines
        }
        plan["state"] = dict(previous)
        return plan

    reservations: list[dict[str, Any]] = []
    new_state: dict[str, str] = {}
    total_saving = 0.0

    for machine in sorted(machines, key=lambda m: -int(m.priority)):
        mid = machine.machine_id
        if not settings.get(machine.setting_key, machine.automatic_default):
            plan["machines"][mid] = _machine_entry(machine, USER_CONTROL, False, "Gestion automatique désactivée")
            continue
        cycle = cycles.get(mid, {})
        duration_h, power_w, source = _profile(machine, learning)
        duration = timedelta(hours=duration_h)
        if cycle.get("protected"):
            end = _as_datetime(cycle.get("expected_end_at"), now + duration)
            plan["machines"][mid] = _machine_entry(
                machine, CONTINUE, True, "Cycle protégé : il va jusqu'au bout",
                planned_start=now.isoformat(), planned_end=end.isoformat(), duration_source=source,
            )
            reservations.append({"start": now, "end": end, "power_w": power_w})
            continue

        earliest = _available_from(machine, now)
        deadline = _deadline(machine, now, max_wait_h)
        latest_start = deadline - duration
        windows = _machine_windows(machine, now, deadline)
        info = {
            "duration_h": round(duration_h, 3),
            "duration_source": source,
            "average_power_w": round(power_w, 1),
            "deadline": deadline.isoformat(),
            "interruptible": bool(machine.interruptible),
        }

        if mode == "Manuel":
            plan["machines"][mid] = _machine_entry(machine, USER_CONTROL, False, "Manuel : recommandation seulement", **info)
            continue

        if machine.interruptible:
            entry = _decide_interruptible(
                machine=machine, now=now, slots=slots, windows=windows, earliest=earliest, deadline=deadline,
                duration_h=duration_h, power_w=power_w, reservations=reservations, max_w=max_parallel_w,
                info=info,
            )
            if entry.get("segments"):
                new_state[mid] = entry["planned_start"]
            plan["machines"][mid] = entry
            continue

        starts = _contiguous_starts(windows=windows, slots=slots, earliest=earliest, latest=latest_start, duration=duration)
        candidates: list[tuple[float, datetime, float]] = []
        for start in starts:
            end = start + duration
            if not _parallel_free(reservations, start, end, power_w, max_parallel_w):
                continue
            share = _solar_share(
                start=start, end=end, now=now, power_w=power_w, export_w=float(snapshot.export_w or 0.0),
                solar_window=solar_window, confidence_pct=confidence, near=near,
            )
            cost = _candidate_cost(
                slots=slots, export_points=export_points, start=start, duration_h=duration_h, power_w=power_w, share=share,
            )
            if cost is None:
                continue
            wait_h = max((start - now).total_seconds() / 3600.0, 0.0)
            candidates.append((cost + wait_h * wait_penalty, start, cost))

        immediate = next((c for c in candidates if c[1] <= earliest + near and c[1] <= now + near), None)
        if not candidates:
            reason = "Aucun créneau complet dans les plages autorisées avant l'échéance."
            if not tomorrow_available and deadline > last_end:
                reason = "Prix de demain pas encore publiés : le plan sera refait à leur arrivée."
            plan["machines"][mid] = _machine_entry(machine, WAIT, False, reason, **info)
            continue

        candidates.sort(key=lambda c: (c[0], c[1]))
        best = candidates[0]
        kept = _keep_previous(candidates, best, previous.get(mid), now, hysteresis_pct)
        stable = kept is not best
        best = kept

        negative_now = immediate is not None and current.band == BAND_NEGATIVE
        saving = (immediate[2] - best[2]) if immediate else 0.0
        saving_pct = (saving / immediate[2] * 100.0) if immediate and immediate[2] > 0 else 0.0
        near_best = best[1] <= now + near

        if immediate is None:
            decision, allow = WAIT, False
            reason = "Hors plage autorisée maintenant : départ planifié dans la prochaine plage."
        elif negative_now:
            decision, allow = START_NOW, True
            reason = f"Prix négatif ({current.price:.4f} €/kWh) : on consomme maintenant."
            best = immediate
        elif near_best:
            decision, allow = START_NOW, True
            reason = (
                f"Meilleur créneau = maintenant (période {current.band})."
                if band_for else
                f"Meilleur créneau = maintenant (bande {current.band}, rang {current.rank_pct:.0f} %)."
            )
        elif saving < min_saving:
            decision, allow = START_NOW, True
            reason = f"Attendre ne gagnerait que {max(saving, 0):.3f} € (minimum {min_saving:.2f} €) : on démarre."
            best = immediate
        else:
            decision, allow = WAIT, False
            wait_h = (best[1] - now).total_seconds() / 3600.0
            reason = f"Attendre {wait_h:.1f} h économise {saving:.3f} € ({saving_pct:.0f} %)."
            if stable:
                reason += " Plan précédent conservé (écart trop faible pour le changer)."

        end = best[1] + duration
        reservations.append({"start": best[1], "end": end, "power_w": power_w})
        new_state[mid] = best[1].isoformat()
        if decision == WAIT:
            total_saving += max(saving, 0.0)
        plan["machines"][mid] = _machine_entry(
            machine, decision, allow, reason,
            planned_start=best[1].isoformat(), planned_end=end.isoformat(),
            estimated_cost_eur=round(best[2], 4),
            start_now_cost_eur=round(immediate[2], 4) if immediate else None,
            expected_saving_eur=round(max(saving, 0.0), 4),
            expected_saving_pct=round(max(saving_pct, 0.0), 1),
            planned_band=_band_at(slots, best[1]),
            plan_kept=stable,
            **info,
        )

    plan["total_expected_saving_eur"] = round(total_saving, 4)
    plan["timeline"] = [
        {"load_id": mid, "start": entry.get("planned_start"), "end": entry.get("planned_end"), "decision": entry.get("decision")}
        for mid, entry in plan["machines"].items()
        if entry.get("planned_start")
    ]
    plan["state"] = new_state
    return plan


def _as_datetime(value: Any, default: datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return default
    return default


def _band_at(slots: list[Slot], at: datetime) -> str | None:
    return next((slot.band for slot in slots if slot.start <= at < slot.end), None)


def _keep_previous(
    candidates: list[tuple[float, datetime, float]],
    best: tuple[float, datetime, float],
    previous_start: str | None,
    now: datetime,
    hysteresis_pct: float,
) -> tuple[float, datetime, float]:
    """Stabilité du plan (EVCC) : on garde l'ancien départ s'il reste presque aussi bon."""
    if not previous_start:
        return best
    try:
        wanted = datetime.fromisoformat(previous_start)
    except ValueError:
        return best
    if wanted <= now:
        return best
    old = next((c for c in candidates if c[1] == wanted), None)
    if old is None or old is best:
        return best
    margin = max(0.005, abs(old[0]) * hysteresis_pct / 100.0)
    return old if old[0] - best[0] < margin else best


def _next_block(slots: list[Slot], now: datetime, bands: set[str]) -> dict[str, Any] | None:
    block: list[Slot] = []
    for slot in slots:
        if slot.end <= now:
            continue
        if slot.band in bands:
            block.append(slot)
        elif block:
            break
    if not block:
        return None
    return {
        "start": block[0].start.isoformat(),
        "end": block[-1].end.isoformat(),
        "average_price_eur_kwh": round(sum(s.price for s in block) / len(block), 5),
        "min_price_eur_kwh": round(min(s.price for s in block), 5),
        "max_price_eur_kwh": round(max(s.price for s in block), 5),
    }


def _decide_interruptible(
    *,
    machine: MachineDefinition,
    now: datetime,
    slots: list[Slot],
    windows: list[ScheduleWindow],
    earliest: datetime,
    deadline: datetime,
    duration_h: float,
    power_w: float,
    reservations: list[dict[str, Any]],
    max_w: float,
    info: dict[str, Any],
) -> dict[str, Any]:
    segments = _plan_interruptible(
        slots=slots, windows=windows, earliest=earliest, latest_end=deadline, duration_h=duration_h,
        power_w=power_w, reservations=reservations, max_w=max_w,
    )
    if not segments:
        return _machine_entry(machine, WAIT, False, "Créneaux insuffisants avant l'échéance.", **info)
    running_now = any(seg.start <= now < seg.end for seg in segments)
    first = segments[0]
    for seg in segments:
        reservations.append({"start": seg.start, "end": seg.end, "power_w": power_w})
    cost = sum(seg.cost for seg in segments)
    reason = (
        "Créneau parmi les moins chers : on charge maintenant."
        if running_now
        else f"Prochain créneau bon marché à {first.start:%H:%M}."
    )
    return _machine_entry(
        machine, START_NOW if running_now else WAIT, running_now, reason,
        planned_start=first.start.isoformat(), planned_end=segments[-1].end.isoformat(),
        estimated_cost_eur=round(cost, 4),
        segments=[{"start": seg.start.isoformat(), "end": seg.end.isoformat()} for seg in segments],
        **info,
    )
