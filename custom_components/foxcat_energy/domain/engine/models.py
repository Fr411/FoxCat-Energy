from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class EnergySnapshot:
    timestamp: datetime
    pv_w: float
    house_w: float
    export_w: float
    import_w: float
    grid_net_w: float
    boiler_temp_c: float
    boiler_safety_temp_c: float
    boiler_power_w: float
    inverter_power_w: float
    boiler_on: bool
    boiler_setpoint_c: float
    machine_active: bool
    valid: bool = True
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BoilerIntent:
    action: str
    reason: str
    origin: str = "AUCUNE"


@dataclass(slots=True)
class PriDecision:
    direction: str
    current_level: int
    target_level: int
    reason: str
    score_current: float = 0.0
    score_target: float = 0.0
    house_target_level: int | None = None


@dataclass(slots=True)
class SolarForecast:
    available: bool = False
    start: str = "--:--"
    end: str = "--:--"
    confidence: float = 0.0
    potential: str = "Aucun"
    trend: str = "NOUVELLE"
    reason: str = "Aucune analyse disponible."
    raw: str = ""
