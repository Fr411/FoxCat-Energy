"""Suivi de l'origine de l'énergie stockée dans la batterie (lecture seule).

Le module ne modifie jamais le ledger : il ventile chaque kWh chargé entre
solaire direct et réseau, et trace la condition de recharge réseau.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from ._validation import KWH_TOLERANCE, finite, number

COND_PV = "pv_surplus"
COND_NEGATIVE_PRICE = "negative_price"
COND_OFF_PEAK = "off_peak"
COND_GRID_OTHER = "grid_other"
CONDITIONS = (COND_PV, COND_NEGATIVE_PRICE, COND_OFF_PEAK, COND_GRID_OTHER)


def _day() -> dict[str, Any]:
    return {"total_kwh": 0.0, "solar_kwh": 0.0, "grid_kwh": 0.0,
            "grid_cost_eur": 0.0, "conditions_kwh": {c: 0.0 for c in CONDITIONS}}


class BatteryOriginTracker:
    """Origine journalière (solaire/réseau) des charges de batterie."""

    def __init__(self) -> None:
        self.day_key = ""
        self.today = _day()
        self.last_ts: datetime | None = None

    def update(self, now: datetime, *, charge_w: float, pv_w: float, house_w: float,
               buy_price: float | None = None, period: str = "", regime: str = "") -> None:
        d = now.strftime("%Y-%m-%d")
        if self.day_key != d:
            self.day_key, self.today = d, _day()
        last, self.last_ts = self.last_ts, now
        if last is None:
            return
        dt = (now - last).total_seconds()
        if dt <= 0 or dt > 90 or not finite(charge_w) or charge_w <= 0:
            return
        hours = dt / 3600.0
        total = charge_w / 1000.0 * hours
        surplus = max(number(pv_w) - max(number(house_w), 0.0), 0.0) / 1000.0 * hours
        solar = min(total, surplus)
        grid = total - solar
        t = self.today
        t["total_kwh"] += total
        t["solar_kwh"] += solar
        t["grid_kwh"] += grid
        t["conditions_kwh"][COND_PV] += solar
        if grid > 0:
            if buy_price is not None and buy_price < 0:
                cond = COND_NEGATIVE_PRICE
            elif period == "HC":
                cond = COND_OFF_PEAK
            else:
                cond = COND_GRID_OTHER
            t["conditions_kwh"][cond] += grid
            if buy_price is not None:
                t["grid_cost_eur"] += grid * buy_price

    def validate(self) -> dict[str, Any]:
        """Totaux : solaire + réseau = total ; somme des conditions = total."""
        t, errors = self.today, []
        if abs(t["solar_kwh"] + t["grid_kwh"] - t["total_kwh"]) > KWH_TOLERANCE:
            errors.append("battery: solaire + réseau ≠ total chargé")
        if abs(sum(t["conditions_kwh"].values()) - t["total_kwh"]) > KWH_TOLERANCE:
            errors.append("battery: somme des conditions ≠ total chargé")
        return {"status": "error" if errors else "ok", "errors": errors}

    def view(self) -> dict[str, Any]:
        t = self.today
        total = t["total_kwh"]
        return {
            "day": self.day_key,
            "total_kwh": round(total, 6),
            "solar_kwh": round(t["solar_kwh"], 6),
            "grid_kwh": round(t["grid_kwh"], 6),
            "solar_pct": round(t["solar_kwh"] / total * 100, 2) if total > 0 else 0.0,
            "grid_pct": round(t["grid_kwh"] / total * 100, 2) if total > 0 else 0.0,
            "grid_cost_eur": round(t["grid_cost_eur"], 6),
            "conditions_kwh": {k: round(v, 6) for k, v in t["conditions_kwh"].items()},
            "checks": self.validate(),
        }

    def dump(self) -> dict[str, Any]:
        return {"day_key": self.day_key, "today": self.today}

    def restore(self, raw: Any) -> None:
        if not isinstance(raw, dict) or not isinstance(raw.get("today"), dict):
            return
        base = _day()
        src = raw["today"]
        for k in ("total_kwh", "solar_kwh", "grid_kwh", "grid_cost_eur"):
            base[k] = number(src.get(k))
        conds = src.get("conditions_kwh") if isinstance(src.get("conditions_kwh"), dict) else {}
        for c in CONDITIONS:
            base["conditions_kwh"][c] = number(conds.get(c))
        self.day_key, self.today = str(raw.get("day_key", "")), base
