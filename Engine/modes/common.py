from __future__ import annotations
from datetime import datetime
from typing import Any
from ..models import EnergySnapshot
from ..tariff import minute_of_day, _time_minutes

def coverage(grid_net_w: float, boiler_power_w: float) -> float:
    if boiler_power_w <= 0: return 0.0
    return max(grid_net_w, 0.0) / boiler_power_w * 100.0

def thermal_deadline(snapshot: EnergySnapshot, settings: dict[str, Any], now: datetime) -> bool:
    normal = float(settings.get("boiler_temp_normal_c", 45.0))
    delta = max(normal - snapshot.boiler_temp_c, 0.0)
    need_minutes = delta / 10.0 * 60.0 + 30.0
    m = minute_of_day(now)
    # Dynamic reading instead of 420/1020
    s1 = _time_minutes(settings.get("tariff_hp_start_1"), "07:00:00")
    s2 = _time_minutes(settings.get("tariff_hp_start_2"), "17:00:00")
    
    if m < s1: available = s1 - m
    elif m < s2: available = s2 - m
    else: available = (1440 - m) + s1
    
    return snapshot.boiler_temp_c < normal and available <= need_minutes

def ecs_last_departure(snapshot: EnergySnapshot, settings: dict[str, Any], now: datetime) -> bool:
    m = minute_of_day(now)
    s1 = _time_minutes(settings.get("tariff_hp_start_1"), "07:00:00")
    e1 = _time_minutes(settings.get("tariff_hp_end_1"), "11:00:00")
    s2 = _time_minutes(settings.get("tariff_hp_start_2"), "17:00:00")
    
    if 0 <= m < s1: minutes_end = s1 - m
    elif e1 <= m < s2: minutes_end = s2 - m
    elif s2 <= m < 1440: minutes_end = (1440 - m) + s1
    else: return False
    
    normal = float(settings.get("boiler_temp_normal_c", 45.0))
    projected_end = snapshot.boiler_temp_c - 0.5 * (minutes_end / 60.0)
    heating_minutes = max(0.0, (normal - projected_end) / 10.0 * 60.0)
    return minutes_end - heating_minutes - 30.0 <= 0
