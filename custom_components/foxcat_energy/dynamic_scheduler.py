from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable

from .economic_optimizer import PricePoint, average_price
from .engine.models import EnergySnapshot, SolarForecast
from .machines import MachineDefinition, time_minutes


@dataclass(frozen=True, slots=True)
class ScheduleWindow:
    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class Candidate:
    start: datetime
    end: datetime
    average_buy: float
    average_export: float | None
    position_pct: float
    solar_overlap_pct: float
    favorable: bool


def _local_datetime(day: date, minute_of_day: int, tzinfo: Any) -> datetime:
    minute_of_day %= 24 * 60
    return datetime.combine(
        day,
        time(hour=minute_of_day // 60, minute=minute_of_day % 60),
        tzinfo=tzinfo,
    )


def _machine_windows(
    machine: MachineDefinition,
    start: datetime,
    end: datetime,
) -> list[ScheduleWindow]:
    """Expand the two user-configured machine windows over the requested horizon."""
    result: list[ScheduleWindow] = []
    first_day = (start - timedelta(days=1)).date()
    last_day = end.date()
    days = (last_day - first_day).days + 1
    pairs = (
        (time_minutes(machine.on_1, "21:30:00"), time_minutes(machine.off_1, "07:00:00")),
        (time_minutes(machine.on_2, "10:30:00"), time_minutes(machine.off_2, "17:00:00")),
    )
    for offset in range(days):
        day = first_day + timedelta(days=offset)
        for start_min, stop_min in pairs:
            if start_min == stop_min:
                continue
            ws = _local_datetime(day, start_min, start.tzinfo)
            we = _local_datetime(day, stop_min, start.tzinfo)
            if stop_min <= start_min:
                we += timedelta(days=1)
            if we <= start or ws >= end:
                continue
            result.append(ScheduleWindow(max(ws, start), min(we, end)))
    result.sort(key=lambda item: item.start)
    return result


def _ceil_step(value: datetime, minutes: int = 15) -> datetime:
    step = max(int(minutes), 1)
    clean = value.replace(second=0, microsecond=0)
    remainder = clean.minute % step
    if remainder == 0 and clean >= value:
        return clean
    return clean + timedelta(minutes=(step - remainder) % step)


def _candidate_starts(window: ScheduleWindow, duration: timedelta, step_minutes: int = 15) -> Iterable[datetime]:
    cursor = _ceil_step(window.start, step_minutes)
    while cursor + duration <= window.end:
        yield cursor
        cursor += timedelta(minutes=step_minutes)


def _parse_forecast_window(now: datetime, forecast: SolarForecast | None) -> ScheduleWindow | None:
    if forecast is None or not bool(getattr(forecast, "available", False)):
        return None

    def parse(value: Any) -> datetime | None:
        raw = str(value or "").strip()
        if not raw or raw in {"--:--", "Indisponible"}:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=now.tzinfo)
            return parsed
        except ValueError:
            pass
        try:
            hh, mm = raw.split(":", 2)[:2]
            return now.replace(hour=int(hh), minute=int(mm), second=0, microsecond=0)
        except (TypeError, ValueError):
            return None

    start = parse(getattr(forecast, "start", None))
    end = parse(getattr(forecast, "end", None))
    if start is None or end is None:
        return None
    if end <= start:
        end += timedelta(days=1)
    if end <= now:
        start += timedelta(days=1)
        end += timedelta(days=1)
    return ScheduleWindow(start, end)


def _overlap_ratio(start: datetime, end: datetime, window: ScheduleWindow | None) -> float:
    if window is None or end <= start:
        return 0.0
    overlap_start = max(start, window.start)
    overlap_end = min(end, window.end)
    if overlap_end <= overlap_start:
        return 0.0
    return max(0.0, min(1.0, (overlap_end - overlap_start).total_seconds() / (end - start).total_seconds()))


def _position(price: float, pmin: float, pmax: float) -> float:
    if pmax <= pmin:
        return 50.0
    return max(0.0, min(100.0, (price - pmin) / (pmax - pmin) * 100.0))


def _group_price_zones(
    points: list[PricePoint],
    *,
    now: datetime,
    pmin: float,
    pmax: float,
    low_threshold_pct: float,
    high_threshold_pct: float,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    future = sorted((p for p in points if p.at >= now.replace(minute=0, second=0, microsecond=0)), key=lambda p: p.at)
    if not future:
        return None, None

    def first_block(predicate: Any, label: str) -> dict[str, Any] | None:
        block: list[PricePoint] = []
        for point in future:
            if predicate(_position(point.price, pmin, pmax)):
                if block and point.at - block[-1].at > timedelta(minutes=90):
                    break
                block.append(point)
            elif block:
                break
        if not block:
            return None
        end = block[-1].at + timedelta(hours=1)
        return {
            "type": label,
            "start": block[0].at.isoformat(),
            "end": end.isoformat(),
            "min_price_eur_kwh": round(min(p.price for p in block), 6),
            "max_price_eur_kwh": round(max(p.price for p in block), 6),
            "average_price_eur_kwh": round(sum(p.price for p in block) / len(block), 6),
            "position_min_pct": round(min(_position(p.price, pmin, pmax) for p in block), 2),
            "position_max_pct": round(max(_position(p.price, pmin, pmax) for p in block), 2),
        }

    valley = first_block(lambda pct: pct <= low_threshold_pct, "CREUX")
    peak = first_block(lambda pct: pct >= high_threshold_pct, "PIC")
    return valley, peak


def _machine_profile(machine: MachineDefinition, learning: dict[str, Any]) -> tuple[float, float | None, str]:
    profile = learning.get(machine.machine_id, {}) if isinstance(learning, dict) else {}
    duration_s = profile.get("average_duration_s_10")
    energy_wh = profile.get("average_energy_wh_10")
    if isinstance(duration_s, (int, float)) and duration_s > 0:
        duration_h = max(float(duration_s) / 3600.0, 0.25)
        source = "APPRENTISSAGE_10_CYCLES"
    else:
        duration_h = max(float(machine.cycle_duration_minutes) / 60.0, 0.25)
        source = "DUREE_CONFIGUREE"
    energy_kwh = float(energy_wh) / 1000.0 if isinstance(energy_wh, (int, float)) and energy_wh > 0 else None
    return duration_h, energy_kwh, source


def _best_machine_candidate(
    *,
    machine: MachineDefinition,
    now: datetime,
    horizon_end: datetime,
    duration_h: float,
    import_points: list[PricePoint],
    export_points: list[PricePoint],
    pmin: float,
    pmax: float,
    threshold_pct: float,
    solar_window: ScheduleWindow | None,
    solar_preference: bool,
) -> Candidate | None:
    duration = timedelta(hours=duration_h)
    candidates: list[Candidate] = []
    for window in _machine_windows(machine, now, horizon_end):
        for start in _candidate_starts(window, duration):
            avg_buy = average_price(import_points, start, duration_h)
            if avg_buy is None:
                continue
            end = start + duration
            avg_export = average_price(export_points, start, duration_h) if export_points else None
            pos = _position(avg_buy, pmin, pmax)
            solar_overlap = _overlap_ratio(start, end, solar_window) if solar_preference else 0.0
            candidates.append(
                Candidate(
                    start=start,
                    end=end,
                    average_buy=float(avg_buy),
                    average_export=float(avg_export) if avg_export is not None else None,
                    position_pct=pos,
                    solar_overlap_pct=solar_overlap * 100.0,
                    favorable=pos <= threshold_pct,
                )
            )
    if not candidates:
        return None

    # User windows are sovereign. Inside them we first prefer a favorable Day-Ahead
    # block, then a solar-overlap window, and finally the cheapest average purchase.
    return min(
        candidates,
        key=lambda c: (
            0 if c.favorable else 1,
            -round(c.solar_overlap_pct, 3),
            c.average_buy,
            c.start,
        ),
    )


def build_dynamic_schedule(
    *,
    now: datetime,
    snapshot: EnergySnapshot,
    settings: dict[str, Any],
    mode_dynamic_active: bool,
    import_points: list[PricePoint],
    export_points: list[PricePoint],
    machines: list[MachineDefinition],
    learning: dict[str, Any],
    cycles: dict[str, dict[str, Any]],
    market_decision: dict[str, Any],
    solar_forecast: SolarForecast | None,
    tomorrow_available: bool,
) -> dict[str, Any]:
    """Build the V1.6.159 planner. It is intentionally inert outside Dynamic mode."""
    threshold_pct = max(5.0, min(60.0, float(settings.get("dynamic_favorable_position_pct", 30.0))))
    high_threshold_pct = max(threshold_pct, min(95.0, float(settings.get("dynamic_high_position_pct", 70.0))))
    if not mode_dynamic_active:
        return {
            "active": False,
            "reason": "Planificateur Day-Ahead inactif hors mode Dynamique.",
            "threshold_pct": threshold_pct,
            "tomorrow_available": bool(tomorrow_available),
            "machines": {},
        }

    points = sorted(import_points, key=lambda p: p.at)
    if not points:
        return {
            "active": True,
            "ready": False,
            "reason": "Courbe Luminus Dynamic indisponible.",
            "threshold_pct": threshold_pct,
            "tomorrow_available": bool(tomorrow_available),
            "machines": {},
        }

    future = [p for p in points if p.at >= now - timedelta(hours=1)]
    pmin = min(p.price for p in future)
    pmax = max(p.price for p in future)
    current_position = market_decision.get("dynamic_curve_position_pct")
    if not isinstance(current_position, (int, float)):
        current_buy = market_decision.get("current_buy_eur_kwh")
        current_position = _position(float(current_buy), pmin, pmax) if isinstance(current_buy, (int, float)) else None
    favorable_now = bool(isinstance(current_position, (int, float)) and float(current_position) <= threshold_pct)

    last_point = max(p.at for p in points)
    horizon_end = min(last_point + timedelta(hours=1), now + timedelta(hours=36))
    actual_horizon_h = max((horizon_end - now).total_seconds() / 3600.0, 0.0)
    solar_window = _parse_forecast_window(now, solar_forecast)
    solar_preference = bool(settings.get("solar_forecast_arbitrage", True))
    valley, peak = _group_price_zones(
        points,
        now=now,
        pmin=pmin,
        pmax=pmax,
        low_threshold_pct=threshold_pct,
        high_threshold_pct=high_threshold_pct,
    )

    machine_plans: dict[str, Any] = {}
    for machine in machines:
        duration_h, energy_kwh, duration_source = _machine_profile(machine, learning)
        duration = timedelta(hours=duration_h)
        current_windows = _machine_windows(machine, now, now + duration + timedelta(minutes=1))
        user_window_now = any(window.start <= now and now + duration <= window.end for window in current_windows)
        cycle = cycles.get(machine.machine_id, {})
        protected = bool(cycle.get("protected", False))
        avg_power_w = (energy_kwh / duration_h * 1000.0) if energy_kwh is not None and duration_h > 0 else None
        solar_fraction_now = (
            max(0.0, min(1.0, float(snapshot.export_w) / max(avg_power_w, 1.0)))
            if avg_power_w is not None else 0.0
        )
        solar_start_now = bool(user_window_now and solar_fraction_now >= 0.50)
        boiler_priority = bool(market_decision.get("boiler_comfort_priority"))

        best = _best_machine_candidate(
            machine=machine,
            now=now,
            horizon_end=horizon_end,
            duration_h=duration_h,
            import_points=points,
            export_points=export_points,
            pmin=pmin,
            pmax=pmax,
            threshold_pct=threshold_pct,
            solar_window=solar_window,
            solar_preference=solar_preference,
        )

        if protected:
            allow_now = True
            decision = "CYCLE_EN_COURS"
            reason = "Cycle déjà démarré : protection MachineCycleManager prioritaire."
        elif not user_window_now:
            allow_now = False
            decision = "HORS_PLAGE_UTILISATEUR"
            reason = "Le cycle complet ne peut pas tenir dans la plage utilisateur actuelle."
        elif boiler_priority:
            allow_now = False
            decision = "PRIORITE_ECS"
            reason = "Le confort ECS minimal est prioritaire avant un nouveau cycle flexible."
        elif solar_start_now:
            allow_now = True
            decision = "DEMARRAGE_AUTOCONSOMMATION"
            reason = f"Surplus actuel estimé couvrant {solar_fraction_now*100:.0f} % de la puissance moyenne apprise."
        elif favorable_now:
            allow_now = True
            decision = "DEMARRAGE_PRIX_FAVORABLE"
            reason = f"Position Day-Ahead {float(current_position):.1f} % <= seuil utilisateur {threshold_pct:.1f} %."
        else:
            allow_now = False
            decision = "PLANIFIE"
            reason = "Prix hors seuil et surplus solaire actuel insuffisant : attente du meilleur créneau autorisé."

        machine_plans[machine.machine_id] = {
            "name": machine.name,
            "decision": decision,
            "allow_start_now": allow_now,
            "reason": reason,
            "protected": protected,
            "user_window_now": user_window_now,
            "duration_h": round(duration_h, 3),
            "duration_source": duration_source,
            "learned_energy_kwh": round(energy_kwh, 4) if energy_kwh is not None else None,
            "average_power_w": round(avg_power_w, 1) if avg_power_w is not None else None,
            "solar_fraction_now_pct": round(solar_fraction_now * 100.0, 1),
            "best_start": best.start.isoformat() if best else None,
            "best_end": best.end.isoformat() if best else None,
            "best_average_buy_eur_kwh": round(best.average_buy, 6) if best else None,
            "best_average_export_eur_kwh": round(best.average_export, 6) if best and best.average_export is not None else None,
            "best_position_pct": round(best.position_pct, 2) if best else None,
            "best_solar_overlap_pct": round(best.solar_overlap_pct, 1) if best else None,
            "best_favorable": bool(best.favorable) if best else False,
            "window_1": f"{machine.on_1}–{machine.off_1}",
            "window_2": f"{machine.on_2}–{machine.off_2}",
        }

    return {
        "active": True,
        "ready": True,
        "reason": "Planificateur Day-Ahead actif exclusivement en mode Dynamique.",
        "threshold_pct": threshold_pct,
        "high_threshold_pct": high_threshold_pct,
        "current_position_pct": round(float(current_position), 2) if isinstance(current_position, (int, float)) else None,
        "favorable_now": favorable_now,
        "curve_min_eur_kwh": round(pmin, 6),
        "curve_max_eur_kwh": round(pmax, 6),
        "horizon_hours": round(actual_horizon_h, 2),
        "tomorrow_available": bool(tomorrow_available),
        "next_valley": valley,
        "next_peak": peak,
        "solar_window": {
            "available": solar_window is not None,
            "start": solar_window.start.isoformat() if solar_window else None,
            "end": solar_window.end.isoformat() if solar_window else None,
            "confidence_pct": round(float(getattr(solar_forecast, "confidence", 0.0) or 0.0), 1),
        },
        "machines": machine_plans,
    }
