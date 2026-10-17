"""Adaptateur d'entrées en lecture seule depuis EnergySnapshot et les tarifs FoxCat."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping

from ..economic_optimizer import PricePoint
from .models import DataQuality, Slot
from .tariff_adapter import PriceQuote, TariffAdapter, make_slot


def build_slot_from_snapshot(
    *,
    timestamp: datetime,
    dt_hours: float,
    house_w: float | None,
    pv_w: float | None,
    prices: Mapping[str, Any],
    settings: Mapping[str, Any],
) -> Slot | None:
    if dt_hours <= 0 or dt_hours > 24.0:
        return None

    adapter = TariffAdapter(settings)
    load_kwh = max(0.0, float(house_w)) * dt_hours / 1000.0 if isinstance(house_w, (int, float)) else None
    pv_kwh = max(0.0, float(pv_w)) * dt_hours / 1000.0 if isinstance(pv_w, (int, float)) else None

    buy_price = prices.get("current")
    sell_price = prices.get("injection")

    imp_quote: PriceQuote = adapter.classify(
        buy_price, timestamp, timestamp, direction="import", is_final=True
    )
    exp_quote: PriceQuote = adapter.classify(
        sell_price, timestamp, timestamp, direction="export", is_final=True
    )

    return make_slot(
        start=timestamp,
        hours=dt_hours,
        load_kwh=load_kwh,
        pv_kwh=pv_kwh,
        import_quote=imp_quote,
        export_quote=exp_quote,
        load_quality=DataQuality.MEASURED if load_kwh is not None else DataQuality.MISSING,
        pv_quality=DataQuality.MEASURED if pv_kwh is not None else DataQuality.MISSING,
    )


def build_forecast_slots(
    *,
    now: datetime,
    import_points: Iterable[PricePoint],
    export_points: Iterable[PricePoint],
    settings: Mapping[str, Any],
    expected_house_w: float = 500.0,
) -> list[Slot]:
    adapter = TariffAdapter(settings)
    exp_by_ts = {p.at: p.price for p in export_points}
    future_slots: list[Slot] = []

    sorted_pts = sorted((p for p in import_points if p.at > now), key=lambda x: x.at)
    for idx, pt in enumerate(sorted_pts[:48]):
        hours = 1.0
        if idx + 1 < len(sorted_pts):
            diff_h = (sorted_pts[idx + 1].at - pt.at).total_seconds() / 3600.0
            if 0.0 < diff_h <= 6.0:
                hours = diff_h
        imp_q = adapter.classify(pt.price, pt.at, now, direction="import", is_final=True)
        exp_raw = exp_by_ts.get(pt.at)
        exp_q = adapter.classify(exp_raw, pt.at, now, direction="export", is_final=True)
        load_est = max(0.0, float(expected_house_w)) * hours / 1000.0
        future_slots.append(
            Slot(
                start=pt.at,
                hours=hours,
                load_kwh=load_est,
                pv_kwh=0.0,
                import_price=imp_q.value if imp_q.usable else None,
                export_price=exp_q.value if exp_q.usable else None,
                load_quality=DataQuality.ESTIMATED,
                pv_quality=DataQuality.ESTIMATED,
                price_quality=DataQuality.ESTIMATED if imp_q.usable else DataQuality.MISSING,
                price_is_future=True,
            )
        )
    return future_slots
