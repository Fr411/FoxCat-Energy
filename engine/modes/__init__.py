from __future__ import annotations

from datetime import datetime

from ...const import MODE_COMFORT, MODE_DYNAMIC, MODE_ECO, MODE_ECS, MODE_MANUAL, MODE_ZERO, BOILER_NONE
from ..models import BoilerIntent, EnergySnapshot, SolarForecast
from .dynamic import evaluate_dynamic
from .eco import evaluate_eco
from .ecs_solar import evaluate_ecs_solar
from .manual import evaluate_manual
from .zero_injection import evaluate_zero_injection


def evaluate_mode(
    mode: str,
    snapshot: EnergySnapshot,
    t0: EnergySnapshot,
    settings: dict[str, object],
    now: datetime,
    boiler_on_seconds: float,
    current_demand: str,
    prices: dict[str, object],
    solar: SolarForecast,
) -> BoilerIntent:
    if mode == MODE_MANUAL:
        return evaluate_manual(snapshot, settings)
    if mode == MODE_ZERO:
        return evaluate_zero_injection(snapshot, settings)
    if mode in {MODE_ECO, MODE_COMFORT}:
        return evaluate_eco(snapshot, t0, settings, now, boiler_on_seconds, current_demand)
    if mode == MODE_ECS:
        return evaluate_ecs_solar(snapshot, t0, settings, now, boiler_on_seconds, current_demand)
    if mode == MODE_DYNAMIC:
        return evaluate_dynamic(snapshot, t0, settings, now, prices, solar)
    return BoilerIntent(BOILER_NONE, "Mode inconnu : aucune action.", "AUCUNE")


__all__ = ["evaluate_mode"]
