from __future__ import annotations

from datetime import datetime

from ..models import EnergySnapshot
from ..tariff import is_offpeak, minute_of_day


def coverage(grid_net_w: float, boiler_power_w: float) -> float:
    if boiler_power_w <= 0:
        return 0.0
    return max(grid_net_w, 0.0) / boiler_power_w * 100.0


def thermal_deadline(snapshot: EnergySnapshot, settings: dict[str, object], now: datetime) -> bool:
    """Prudent last-safe-start model kept from the validated FoxCat baseline."""
    normal = float(settings["boiler_temp_normal_c"])
    delta = max(normal - snapshot.boiler_temp_c, 0.0)
    heating_rate_c_h = 10.0
    margin_minutes = 30.0
    need_minutes = delta / heating_rate_c_h * 60.0 + margin_minutes
    m = minute_of_day(now)
    # Baseline AIESH last-safe-start calculation. The generic tariff schedule is
    # used for normal HP/HC decisions; this thermal model remains unchanged in
    # V1.2.0 to avoid silently altering the validated predictor.
    if m < 420:
        available = 420 - m
    elif m < 1020:
        available = 1020 - m
    else:
        available = (1440 - m) + 420
    return snapshot.boiler_temp_c < normal and available <= need_minutes


def ecs_last_departure(snapshot: EnergySnapshot, settings: dict[str, object], now: datetime) -> bool:
    m = minute_of_day(now)
    if 0 <= m < 420:
        minutes_end = 420 - m
    elif 660 <= m < 1020:
        minutes_end = 1020 - m
    elif 1320 <= m < 1440:
        minutes_end = (1440 - m) + 420
    else:
        return False
    normal = float(settings["boiler_temp_normal_c"])
    projected_end = snapshot.boiler_temp_c - 0.5 * (minutes_end / 60.0)
    heating_minutes = max(0.0, (normal - projected_end) / 10.0 * 60.0)
    return minutes_end - heating_minutes - 30.0 <= 0
