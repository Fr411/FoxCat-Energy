"""Heuristic VPP decisions shared by financial trading and vehicle peak support."""
from __future__ import annotations

from collections.abc import Iterable
import math
from typing import Any


def _finite_number(value: Any, default: float | None = None) -> float | None:
    if isinstance(value, bool):
        return default
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    return result if math.isfinite(result) else default


def evaluate_trade(
    current_buy_eur_kwh: float | None,
    future_sell_prices_eur_kwh: Iterable[float],
    *,
    battery_wear_eur_kwh: float = 0.0,
    vehicle_wear_eur_kwh: float = 0.0,
) -> dict[str, Any]:
    """Compare the best future resale price with today's purchase and asset wear."""
    current_buy = _finite_number(current_buy_eur_kwh)
    future_prices = [
        parsed for value in future_sell_prices_eur_kwh
        if (parsed := _finite_number(value)) is not None
    ]
    future_sell = max(future_prices) if future_prices else None
    spread = (
        future_sell - current_buy
        if future_sell is not None and current_buy is not None
        else None
    )
    battery_wear = max(_finite_number(battery_wear_eur_kwh, 0.0) or 0.0, 0.0)
    vehicle_wear = max(_finite_number(vehicle_wear_eur_kwh, 0.0) or 0.0, 0.0)
    return {
        "current_buy_eur_kwh": current_buy,
        "best_future_sell_eur_kwh": future_sell,
        "spread_eur_kwh": spread,
        "battery_trade_profitable": spread is not None and spread > battery_wear,
        "vehicle_trade_profitable": spread is not None and spread > vehicle_wear,
        "battery_wear_eur_kwh": battery_wear,
        "vehicle_wear_eur_kwh": vehicle_wear,
    }


def evaluate_v2h(
    *,
    enabled: bool,
    price_status: str,
    house_w: float,
    breaker_limit_w: float | None,
    max_power_w: float,
    soc_pct: float | None,
    min_soc_pct: float,
    peak_shaving_armed: bool = True,
) -> dict[str, Any]:
    """Return a V2H request without issuing a hardware command."""
    breaker_limit_w = _finite_number(breaker_limit_w)
    max_power_w = max(_finite_number(max_power_w, 0.0) or 0.0, 0.0)
    soc_pct = _finite_number(soc_pct)
    min_soc_pct = _finite_number(min_soc_pct, 25.0) or 25.0
    house_w = max(_finite_number(house_w, 0.0) or 0.0, 0.0)
    peak_trigger_w = (
        max(breaker_limit_w, 0.0) * 0.9
        if breaker_limit_w is not None and breaker_limit_w > 0
        else None
    )
    peak_shaving = (
        peak_shaving_armed
        and peak_trigger_w is not None
        and house_w >= peak_trigger_w
    )
    tariff_shield = price_status == "TRÈS ÉLEVÉ"
    allowed = enabled and (peak_shaving or tariff_shield)

    if not enabled:
        reason = "V2H désactivé"
    elif not (peak_shaving or tariff_shield):
        reason = "Aucun signal de pointe ni prix très élevé"
    elif soc_pct is None:
        allowed = False
        reason = "SoC du véhicule indisponible : commande bloquée"
    elif soc_pct < min_soc_pct:
        allowed = False
        reason = "Réserve de mobilité du véhicule atteinte"
    else:
        reason = "Écrêtement de pointe" if peak_shaving else "Bouclier tarifaire"

    target_w = 0.0
    if allowed:
        if peak_shaving and breaker_limit_w is not None:
            target_w = max(house_w - breaker_limit_w * 0.8, 0.0)
        else:
            target_w = max(house_w, 0.0)
        target_w = min(target_w, max_power_w)

    return {
        "enabled": enabled,
        "active": allowed,
        "reason": reason,
        "peak_shaving": peak_shaving,
        "tariff_shield": tariff_shield,
        "peak_trigger_w": peak_trigger_w,
        "target_power_w": target_w,
        "soc_pct": soc_pct,
        "min_soc_pct": min_soc_pct,
        "thermal_interlock": allowed,
    }
