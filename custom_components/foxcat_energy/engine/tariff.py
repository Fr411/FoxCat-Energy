from __future__ import annotations

from datetime import datetime, time
from typing import Any


def minute_of_day(now: datetime) -> float:
    return now.hour * 60 + now.minute + now.second / 60


def _time_minutes(value: Any, default: str) -> int:
    if isinstance(value, time):
        return value.hour * 60 + value.minute
    raw = str(value or default)
    try:
        parts = raw.split(":")
        return (int(parts[0]) % 24) * 60 + (int(parts[1]) % 60)
    except (ValueError, IndexError, TypeError):
        h, m = default.split(":")[:2]
        return int(h) * 60 + int(m)


def _within(now_minute: float, start_minute: int, stop_minute: int) -> bool:
    if start_minute == stop_minute:
        return False
    if start_minute < stop_minute:
        return start_minute <= now_minute < stop_minute
    return now_minute >= start_minute or now_minute < stop_minute


def is_peak(now: datetime, settings: dict[str, object] | None = None) -> bool:
    settings = settings or {}
    m = minute_of_day(now)
    s1 = _time_minutes(settings.get("tariff_hp_start_1"), "07:00:00")
    e1 = _time_minutes(settings.get("tariff_hp_end_1"), "11:00:00")
    s2 = _time_minutes(settings.get("tariff_hp_start_2"), "17:00:00")
    e2 = _time_minutes(settings.get("tariff_hp_end_2"), "22:00:00")
    return _within(m, s1, e1) or _within(m, s2, e2)


def is_offpeak(now: datetime, settings: dict[str, object] | None = None) -> bool:
    return not is_peak(now, settings)


def is_offpeak_day(now: datetime, settings: dict[str, object] | None = None) -> bool:
    """Return the daytime off-peak window between the two HP ranges.

    With AIESH defaults this is 11:00-17:00. If the user customises the HP
    ranges, this becomes the interval from end of HP1 to start of HP2.
    """
    settings = settings or {}
    m = minute_of_day(now)
    e1 = _time_minutes(settings.get("tariff_hp_end_1"), "11:00:00")
    s2 = _time_minutes(settings.get("tariff_hp_start_2"), "17:00:00")
    return _within(m, e1, s2)


def is_offpeak_night(now: datetime, settings: dict[str, object] | None = None) -> bool:
    settings = settings or {}
    m = minute_of_day(now)
    e2 = _time_minutes(settings.get("tariff_hp_end_2"), "22:00:00")
    s1 = _time_minutes(settings.get("tariff_hp_start_1"), "07:00:00")
    return _within(m, e2, s1)


def tariff_period(now: datetime, settings: dict[str, object] | None = None) -> str:
    return "HP" if is_peak(now, settings) else "HC"


def tariff_boundaries(settings: dict[str, object] | None = None) -> set[tuple[int, int]]:
    settings = settings or {}
    values = (
        ("tariff_hp_start_1", "07:00:00"),
        ("tariff_hp_end_1", "11:00:00"),
        ("tariff_hp_start_2", "17:00:00"),
        ("tariff_hp_end_2", "22:00:00"),
    )
    result: set[tuple[int, int]] = set()
    for key, default in values:
        minute = _time_minutes(settings.get(key), default)
        result.add((minute // 60, minute % 60))
    return result


def price_status(current: float | None, pmin: float | None, pmax: float | None, avg: float | None) -> str:
    if current is None:
        return "INDISPONIBLE"
    if current < 0:
        return "NÉGATIF"
    if pmin is None or pmax is None or pmax <= pmin:
        if avg is None:
            return "NORMAL"
        if current < avg:
            return "BAS"
        if current > avg:
            return "ÉLEVÉ"
        return "NORMAL"
    position = (current - pmin) / max(pmax - pmin, 0.001)
    if position <= 0.20:
        return "TRÈS BAS"
    if position <= 0.45:
        return "BAS"
    if position >= 0.80:
        return "TRÈS ÉLEVÉ"
    if position >= 0.60:
        return "ÉLEVÉ"
    return "NORMAL"
