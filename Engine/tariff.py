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
    except (Exception):
        h, m = default.split(":")[:2]
        return int(h) * 60 + int(m)

def _within(now_minute: float, start_minute: int, stop_minute: int) -> bool:
    if start_minute == stop_minute: return False
    if start_minute < stop_minute: return start_minute <= now_minute < stop_minute
    return now_minute >= start_minute or now_minute < stop_minute

def is_peak(now: datetime, settings: dict[str, Any] | None = None) -> bool:
    settings = settings or {}
    m = minute_of_day(now)
    s1 = _time_minutes(settings.get("tariff_hp_start_1"), "07:00:00")
    e1 = _time_minutes(settings.get("tariff_hp_end_1"), "11:00:00")
    s2 = _time_minutes(settings.get("tariff_hp_start_2"), "17:00:00")
    e2 = _time_minutes(settings.get("tariff_hp_end_2"), "22:00:00")
    return _within(m, s1, e1) or _within(m, s2, e2)

def is_offpeak(now: datetime, settings: dict[str, Any] | None = None) -> bool:
    return not is_peak(now, settings)

def is_offpeak_day(now: datetime, settings: dict[str, Any] | None = None) -> bool:
    settings = settings or {}
    m = minute_of_day(now)
    e1 = _time_minutes(settings.get("tariff_hp_end_1"), "11:00:00")
    s2 = _time_minutes(settings.get("tariff_hp_start_2"), "17:00:00")
    return _within(m, e1, s2)

def is_offpeak_night(now: datetime, settings: dict[str, Any] | None = None) -> bool:
    settings = settings or {}
    m = minute_of_day(now)
    e2 = _time_minutes(settings.get("tariff_hp_end_2"), "22:00:00")
    s1 = _time_minutes(settings.get("tariff_hp_start_1"), "07:00:00")
    return _within(m, e2, s1)

def tariff_period(now: datetime, settings: dict[str, Any] | None = None) -> str:
    return "HP" if is_peak(now, settings) else "HC"

def distribution_period(now: datetime, settings: dict[str, Any] | None = None) -> str:
    # Correction: added to avoid crash in flexible_boiler.py
    # By default in Wallonia, Peak is typically 17h-22h
    settings = settings or {}
    m = minute_of_day(now)
    s2 = _time_minutes(settings.get("tariff_hp_start_2"), "17:00:00")
    e2 = _time_minutes(settings.get("tariff_hp_end_2"), "22:00:00")
    if _within(m, s2, e2): return "PIC"
    return "NORMAL"
