from __future__ import annotations

from datetime import datetime, timedelta
from statistics import median
from typing import Any, Iterable

from .economic_optimizer import PricePoint

REACTIVE = "REACTIVE"
PREDICTIVE = "PREDICTIVE"
BEFORE_FAVORABLE_WINDOW = "BEFORE_FAVORABLE_WINDOW"
IN_FAVORABLE_WINDOW = "IN_FAVORABLE_WINDOW"
AFTER_FAVORABLE_WINDOW = "AFTER_FAVORABLE_WINDOW"


def _unique(points: Iterable[PricePoint]) -> list[PricePoint]:
    return sorted({point.at: point for point in points}.values(), key=lambda point: point.at)


def _granularity(points: list[PricePoint]) -> int:
    minutes = [
        (right.at - left.at).total_seconds() / 60
        for left, right in zip(points, points[1:])
        if 1 <= (right.at - left.at).total_seconds() / 60 <= 360
    ]
    return max(1, int(round(median(minutes)))) if minutes else 60


def _position(value: float, minimum: float, maximum: float) -> float:
    if maximum <= minimum:
        return 50.0
    return max(0.0, min(100.0, (value - minimum) / (maximum - minimum) * 100.0))


def _stats(points: list[PricePoint]) -> dict[str, Any]:
    prices = [point.price for point in points]
    return {
        "available": bool(prices),
        "minimum": min(prices, default=None),
        "maximum": max(prices, default=None),
        "average": sum(prices) / len(prices) if prices else None,
        "points": len(prices),
    }


def _point_hours(points: list[PricePoint], index: int, granularity: int) -> float:
    """Use provider timestamps, with the observed granularity for the last slot."""
    if index + 1 < len(points):
        minutes = (points[index + 1].at - points[index].at).total_seconds() / 60
        if 0 < minutes <= granularity * 1.5:
            return minutes / 60
    return granularity / 60


def _window(start: datetime, end: datetime) -> dict[str, Any]:
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "duration_h": (end - start).total_seconds() / 3600,
    }


def analyze_price_curve(
    *,
    now: datetime,
    import_points: Iterable[PricePoint],
    export_points: Iterable[PricePoint] = (),
    settings: dict[str, Any],
    tomorrow_available: bool = False,
    current_buy: float | None = None,
) -> dict[str, Any]:
    """Summarize known dynamic prices without fabricating missing future values."""
    points = _unique(import_points)
    exports = {point.at: point for point in _unique(export_points)}
    granularity = _granularity(points)
    today = now.date()
    tomorrow = today + timedelta(days=1)
    yesterday = today - timedelta(days=1)
    today_points = [point for point in points if point.at.date() == today]
    tomorrow_points = [point for point in points if point.at.date() == tomorrow]
    yesterday_points = [point for point in points if point.at.date() == yesterday]
    future = [point for point in points if point.at >= now - timedelta(minutes=granularity)]

    current = (
        float(current_buy)
        if isinstance(current_buy, (int, float)) and not isinstance(current_buy, bool)
        else next((point.price for point in reversed(points) if point.at <= now), None)
    )
    reference_prices = [point.price for point in future]
    minimum = min(reference_prices, default=None)
    maximum = max(reference_prices, default=None)
    position = (
        _position(current, minimum, maximum)
        if current is not None and minimum is not None and maximum is not None
        else None
    )
    rank = 1 + sum(price < current for price in reference_prices) if current is not None else None

    threshold = max(0.0, min(100.0, float(settings.get("dynamic_favorable_position_pct", 30))))
    peak_threshold = max(0.0, min(100.0, float(settings.get("dynamic_high_position_pct", 70))))
    max_favorable_hours = max(0.0, float(settings.get("dynamic_favorable_max_hours", 4)))
    day_min = min((point.price for point in today_points), default=None)
    day_max = max((point.price for point in today_points), default=None)

    favorable = [
        point
        for point in today_points
        if day_min is not None
        and day_max is not None
        and _position(point.price, day_min, day_max) <= threshold
    ]
    favorable_order = sorted(favorable, key=lambda point: (point.price, point.at))
    selected_at: set[datetime] = set()
    selected_hours = 0.0
    indexes = {point.at: index for index, point in enumerate(today_points)}
    for point in favorable_order:
        hours = _point_hours(today_points, indexes[point.at], granularity)
        if selected_hours + hours > max_favorable_hours + 1e-9:
            continue
        selected_at.add(point.at)
        selected_hours += hours

    selected = [point for point in today_points if point.at in selected_at]
    windows: list[tuple[datetime, datetime]] = []
    block_start: datetime | None = None
    block_end: datetime | None = None
    for point in selected:
        index = indexes[point.at]
        end = point.at + timedelta(hours=_point_hours(today_points, index, granularity))
        if block_end is None or point.at > block_end + timedelta(minutes=granularity * 0.5):
            if block_start is not None and block_end is not None:
                windows.append((block_start, block_end))
            block_start = point.at
            block_end = end
        else:
            block_end = max(block_end, end)
    if block_start is not None and block_end is not None:
        windows.append((block_start, block_end))

    current_window = next((window for window in windows if window[0] <= now < window[1]), None)
    future_windows = [window for window in windows if window[0] > now]
    state = (
        IN_FAVORABLE_WINDOW
        if current_window
        else BEFORE_FAVORABLE_WINDOW
        if future_windows
        else AFTER_FAVORABLE_WINDOW
    )

    local_maxima: list[PricePoint] = []
    for index, point in enumerate(future):
        if minimum is None or maximum is None or _position(point.price, minimum, maximum) < peak_threshold:
            continue
        previous = future[index - 1].price if index else float("-inf")
        following = future[index + 1].price if index + 1 < len(future) else float("-inf")
        if point.price >= previous and point.price >= following and (
            point.price > previous or point.price > following
        ):
            local_maxima.append(point)

    gaps = [
        (right.at - left.at).total_seconds() / 60
        for left, right in zip(future, future[1:])
        if right.at > left.at
    ]
    max_gap = max(gaps, default=0.0)
    continuity_ok = bool(future) and max_gap <= granularity * 2.5
    predictive = bool(tomorrow_available and tomorrow_points and continuity_ok)

    yesterday_reference = now - timedelta(days=1)
    yesterday_same_time = min(
        yesterday_points,
        key=lambda point: abs((point.at - yesterday_reference).total_seconds()),
        default=None,
    )
    if yesterday_same_time and abs(
        (yesterday_same_time.at - yesterday_reference).total_seconds()
    ) > granularity * 30:
        yesterday_same_time = None

    best_today = min(
        (point for point in today_points if point.at >= now),
        key=lambda point: point.price,
        default=None,
    )
    best_tomorrow = min(tomorrow_points, key=lambda point: point.price, default=None)
    best_future_price = min(
        (point.price for point in future if point.at >= now),
        default=current,
    )
    saving = current - best_future_price if current is not None and best_future_price is not None else None
    used_hours = sum(
        _point_hours(today_points, indexes[point.at], granularity)
        for point in selected
        if point.at + timedelta(hours=_point_hours(today_points, indexes[point.at], granularity)) <= now
    )
    remaining_hours = max(selected_hours - used_hours, 0.0)

    return {
        "active": True,
        "last_update": now.isoformat(),
        "mode": PREDICTIVE if predictive else REACTIVE,
        "state": state,
        "valid": bool(points) and continuity_ok,
        "granularity_minutes": granularity,
        "current_price_eur_kwh": current,
        "current_position_pct": position,
        "current_rank": rank,
        "today": _stats(today_points),
        "tomorrow": _stats(tomorrow_points),
        "yesterday": _stats(yesterday_points),
        "threshold_pct": threshold,
        "high_threshold_pct": peak_threshold,
        "favorable_max_hours": max_favorable_hours,
        "favorable_selected_hours_today": selected_hours,
        "favorable_used_hours_today": used_hours,
        "favorable_remaining_hours_today": remaining_hours,
        "current_window_remaining_h": (
            max((current_window[1] - now).total_seconds() / 3600, 0.0)
            if current_window
            else 0.0
        ),
        "next_favorable_window": (
            _window(*(current_window or future_windows[0]))
            if current_window or future_windows
            else None
        ),
        "next_peak": next(
            (point.at.isoformat() for point in local_maxima if point.at > now),
            None,
        ),
        "peaks": [point.at.isoformat() for point in local_maxima],
        "best_remaining_today": (
            {"at": best_today.at.isoformat(), "price_eur_kwh": best_today.price}
            if best_today
            else None
        ),
        "best_tomorrow": (
            {"at": best_tomorrow.at.isoformat(), "price_eur_kwh": best_tomorrow.price}
            if best_tomorrow
            else None
        ),
        "potential_saving_eur_kwh": max(saving or 0.0, 0.0),
        "yesterday_same_time_eur_kwh": (
            yesterday_same_time.price if yesterday_same_time else None
        ),
        "delta_vs_yesterday_same_time_pct": (
            (current - yesterday_same_time.price) / abs(yesterday_same_time.price) * 100
            if current is not None and yesterday_same_time and yesterday_same_time.price
            else None
        ),
        "delta_vs_yesterday_average_eur_kwh": (
            current - _stats(yesterday_points)["average"]
            if current is not None and _stats(yesterday_points)["average"] is not None
            else None
        ),
        "freshness": {
            "continuity_ok": continuity_ok,
            "maximum_gap_minutes": max_gap,
        },
        "series": [
            {
                "at": point.at.isoformat(),
                "import_eur_kwh": point.price,
                "export_eur_kwh": exports[point.at].price if point.at in exports else None,
                "favorable": point.at in selected_at,
                "peak": point in local_maxima,
            }
            for point in points
        ],
    }
