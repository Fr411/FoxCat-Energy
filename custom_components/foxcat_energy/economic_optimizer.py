from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from datetime import datetime, timedelta
from typing import Any, Iterable

from .const import (
    DYNAMIC_ARBITRAGE_HORIZON_HOURS,
    DYNAMIC_POSITION_HIGH,
    DYNAMIC_POSITION_LOW,
    NETWORK_POLICY_COMPENSATION,
    TARIFF_DYNAMIC,
    TARIFF_FIXED,
    TARIFF_TOU,
)
from .engine.models import EnergySnapshot
from .engine.tariff import tariff_period


@dataclass(frozen=True)
class PricePoint:
    at: datetime
    price: float
    source: str = "UNKNOWN"


@dataclass(frozen=True)
class EconomicDecision:
    code: str
    label: str
    reason: str
    regime: str
    confidence: str
    flexible_start: bool
    prefer_self_consumption: bool
    prefer_export: bool
    current_buy_eur_kwh: float | None
    export_value_eur_kwh: float | None
    best_future_buy_eur_kwh: float | None
    best_future_at: datetime | None
    saving_vs_now_eur_kwh: float | None
    horizon_hours: int
    forecast_points: int
    application: str = "DEMARRAGES_AUTOMATIQUES_MACHINES"
    dynamic_price_index: float | None = None
    dynamic_price_band: str | None = None
    dynamic_price_min_eur_kwh: float | None = None
    dynamic_price_max_eur_kwh: float | None = None
    dynamic_curve_position_pct: float | None = None
    dynamic_curve_rank: int | None = None
    dynamic_curve_points: int = 0
    dynamic_curve_trend: str | None = None
    self_consumption_advantage_eur_kwh: float | None = None
    boiler_effective_cost_eur_h: float | None = None
    boiler_grid_power_needed_w: float | None = None
    boiler_energy_missing_kwh: float | None = None
    boiler_heating_duration_h: float | None = None
    boiler_reserved_start: datetime | None = None
    boiler_reserved_end: datetime | None = None
    boiler_reserved_avg_price_eur_kwh: float | None = None
    boiler_charge_now: bool = False
    boiler_comfort_priority: bool = False
    boiler_comfort_needed: bool = False
    dynamic_fallback: bool = False

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        for key in ("best_future_at", "boiler_reserved_start", "boiler_reserved_end"):
            value = data.get(key)
            data[key] = value.isoformat() if value else None
        return data


_PRICE_KEYS = (
    "price", "value", "total", "price_eur_kwh", "eur_kwh", "eur_per_kwh",
    "import_price", "export_price", "marketprice", "prijs",
)
_TIME_KEYS = (
    "start", "datetime", "time", "timestamp", "starts_at", "start_time", "date", "hour",
)
_SERIES_KEYS = (
    "prices", "forecast", "hourly", "data", "values", "entries",
    "raw_today", "raw_tomorrow", "today", "tomorrow",
)


def _float(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any, now: datetime) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, (int, float)):
        raw = float(value)
        if raw > 10_000_000_000:  # milliseconds
            raw /= 1000.0
        try:
            dt = datetime.fromtimestamp(raw, tz=now.tzinfo)
        except (ValueError, OSError, OverflowError):
            return None
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            # "14:00" / "14:00:00" means today in the HA timezone.
            try:
                parts = text.split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                dt = now.replace(hour=hour % 24, minute=minute % 60, second=0, microsecond=0)
            except (ValueError, IndexError):
                return None
    else:
        return None
    if dt.tzinfo is None and now.tzinfo is not None:
        dt = dt.replace(tzinfo=now.tzinfo)
    return dt


def extract_price_points(
    raw: Any,
    now: datetime,
    *,
    source: str,
    horizon_hours: int = 36,
    preferred_price_keys: Iterable[str] | None = None,
) -> list[PricePoint]:
    """Extract a future price series from common Home Assistant attributes.

    V1.6.158 adds provider-aware key priority. Luminus Dynamic exposes its
    all-in purchase curve as ``all_in`` and its export curve as ``injection``.
    Callers can therefore select the financial series they need without mixing
    purchase and export values when both are present in the same attribute row.
    Generic providers keep the historical fallback keys.
    """
    horizon_end = now + timedelta(hours=max(int(horizon_hours), 1))
    found: list[PricePoint] = []
    preferred = tuple(preferred_price_keys or ())
    price_keys = tuple(dict.fromkeys((*preferred, *_PRICE_KEYS)))

    def add(at: datetime | None, price: float | None) -> None:
        if at is None or price is None:
            return
        # Keep a small look-back so the current slot can still be represented.
        if at < now - timedelta(hours=1) or at > horizon_end:
            return
        found.append(PricePoint(at=at, price=price, source=source))

    def walk(value: Any, base_at: datetime | None = None) -> None:
        if isinstance(value, dict):
            price = next((_float(value.get(key)) for key in price_keys if key in value and _float(value.get(key)) is not None), None)
            at = next((_parse_datetime(value.get(key), now) for key in _TIME_KEYS if key in value and _parse_datetime(value.get(key), now) is not None), None)
            if price is not None:
                add(at or base_at, price)
            for key in _SERIES_KEYS:
                if key in value:
                    series_base = base_at
                    if key in {"today", "raw_today"}:
                        series_base = now.replace(hour=0, minute=0, second=0, microsecond=0)
                    elif key in {"tomorrow", "raw_tomorrow"}:
                        series_base = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
                    walk(value[key], series_base)
            return
        if isinstance(value, (list, tuple)):
            if len(value) == 2 and not isinstance(value[0], (list, tuple, dict)):
                at = _parse_datetime(value[0], now)
                price = _float(value[1])
                if at is not None and price is not None:
                    add(at, price)
                    return
            # Plain numeric lists are interpreted as hourly values starting at
            # the beginning of the current hour.
            numeric = all(_float(item) is not None for item in value) if value else False
            if numeric:
                start = base_at or now.replace(minute=0, second=0, microsecond=0)
                for idx, item in enumerate(value):
                    add(start + timedelta(hours=idx), _float(item))
                return
            for item in value:
                walk(item, base_at)

    walk(raw)
    unique: dict[datetime, PricePoint] = {}
    for point in found:
        unique[point.at] = point
    return sorted(unique.values(), key=lambda p: p.at)


def build_hphc_points(
    now: datetime,
    settings: dict[str, Any],
    hp_price: float | None,
    hc_price: float | None,
    *,
    horizon_hours: int = 24,
    step_minutes: int = 15,
) -> list[PricePoint]:
    if hp_price is None or hc_price is None:
        return []
    step = max(int(step_minutes), 5)
    start = now.replace(second=0, microsecond=0)
    # Align on the previous step boundary to make comparisons deterministic.
    start = start.replace(minute=(start.minute // step) * step)
    count = int(max(horizon_hours, 1) * 60 / step) + 1
    return [
        PricePoint(
            at=start + timedelta(minutes=idx * step),
            price=float(hp_price if tariff_period(start + timedelta(minutes=idx * step), settings) == "HP" else hc_price),
            source="HP_HC",
        )
        for idx in range(count)
    ]


def merge_price_points(*series: Iterable[PricePoint]) -> list[PricePoint]:
    merged: dict[datetime, PricePoint] = {}
    for points in series:
        for point in points:
            merged[point.at] = point
    return sorted(merged.values(), key=lambda p: p.at)


def _price_at(points: list[PricePoint], at: datetime) -> float | None:
    if not points:
        return None
    candidate: PricePoint | None = None
    for point in points:
        if point.at <= at:
            candidate = point
        else:
            break
    if candidate is not None:
        return candidate.price
    return points[0].price


def average_price(points: list[PricePoint], start: datetime, duration_hours: float, *, sample_minutes: int = 15) -> float | None:
    if not points:
        return None
    duration_minutes = max(int(round(max(duration_hours, 0.1) * 60)), sample_minutes)
    samples: list[float] = []
    for minute in range(0, duration_minutes, sample_minutes):
        price = _price_at(points, start + timedelta(minutes=minute))
        if price is None:
            return None
        samples.append(price)
    return sum(samples) / len(samples) if samples else None


def best_start_window(
    points: list[PricePoint],
    now: datetime,
    duration_hours: float,
    horizon_hours: int,
) -> tuple[datetime | None, float | None]:
    if not points:
        return None, None
    horizon_end = now + timedelta(hours=max(horizon_hours, 1))
    candidates = [p.at for p in points if now <= p.at <= horizon_end]
    if now not in candidates:
        candidates.insert(0, now)
    best_at: datetime | None = None
    best_price: float | None = None
    for start in candidates:
        avg = average_price(points, start, duration_hours)
        if avg is None:
            continue
        if best_price is None or avg < best_price:
            best_at, best_price = start, avg
    return best_at, best_price



def _dynamic_day_ahead_points(
    points: list[PricePoint], now: datetime, *, horizon_hours: int = DYNAMIC_ARBITRAGE_HORIZON_HOURS
) -> list[PricePoint]:
    """Return unique hourly Day-Ahead points for the next dynamic horizon only."""
    start = now.replace(minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=max(int(horizon_hours), 1))
    hourly: dict[datetime, PricePoint] = {}
    for point in points:
        slot = point.at.replace(minute=0, second=0, microsecond=0)
        if start <= slot < end:
            hourly[slot] = PricePoint(slot, float(point.price), point.source)
    return [hourly[key] for key in sorted(hourly)]


def _best_consecutive_dynamic_window(
    points: list[PricePoint], now: datetime, duration_hours: float
) -> tuple[datetime | None, datetime | None, float | None]:
    """Find the cheapest *consecutive* hourly Day-Ahead block.

    The reservation is deliberately hour-based because Belgian Day-Ahead
    prices are hourly in the supported baseline. Missing hours invalidate a
    candidate instead of silently carrying a stale value forward.
    """
    if duration_hours <= 0:
        return None, None, None
    hourly = _dynamic_day_ahead_points(points, now)
    blocks = max(1, int(math.ceil(duration_hours)))
    if len(hourly) < blocks:
        return None, None, None
    by_at = {p.at: p for p in hourly}
    best_start: datetime | None = None
    best_end: datetime | None = None
    best_avg: float | None = None
    for point in hourly:
        start = point.at
        expected = [start + timedelta(hours=i) for i in range(blocks)]
        if any(slot not in by_at for slot in expected):
            continue
        values = [by_at[slot].price for slot in expected]
        avg = sum(values) / len(values)
        if best_avg is None or avg < best_avg:
            best_start = start
            best_end = start + timedelta(hours=blocks)
            best_avg = avg
    return best_start, best_end, best_avg


def _legacy_dynamic_decision(
    *,
    now: datetime,
    snapshot: EnergySnapshot,
    prices: dict[str, Any],
    settings: dict[str, Any],
    import_points: list[PricePoint],
    current_buy: float,
    export_value: float | None,
    best_at: datetime | None,
    best_buy: float | None,
    saving: float | None,
    confidence: str,
    horizon: int,
    forecast_count: int,
    reason_prefix: str = "",
) -> EconomicDecision:
    """Exact V1.6.156-style dynamic fallback used when prediction is disabled/unavailable."""
    min_saving = float(settings.get("economic_min_saving_eur_kwh", 0.02))
    export_margin = float(settings.get("economic_export_margin_eur_kwh", 0.01))
    surplus_min = float(settings.get("economic_solar_surplus_min_w", 250.0))
    has_surplus = snapshot.export_w >= surplus_min
    prefix = f"{reason_prefix} " if reason_prefix else ""

    if has_surplus and export_value is not None and export_value < 0:
        return EconomicDecision(
            "ABSORBER_SURPLUS", "Autoconsommer maintenant",
            prefix + f"La réinjection coûte {abs(export_value):.3f} €/kWh : absorber le surplus est prioritaire.",
            TARIFF_DYNAMIC, confidence, True, True, False, current_buy, export_value,
            best_buy, best_at, saving, horizon, forecast_count, dynamic_fallback=True,
        )
    if has_surplus and export_value is not None and best_buy is not None and export_value > best_buy + export_margin:
        return EconomicDecision(
            "EXPORTER_ET_REPORTER", "Exporter maintenant, consommer plus tard",
            prefix + f"Réinjection {export_value:.3f} €/kWh > meilleur achat futur {best_buy:.3f} €/kWh + marge.",
            TARIFF_DYNAMIC, confidence, False, False, True, current_buy, export_value,
            best_buy, best_at, saving, horizon, forecast_count, dynamic_fallback=True,
        )
    if has_surplus and (export_value is None or export_value + export_margin < current_buy):
        return EconomicDecision(
            "AUTOCONSOMMER", "Autoconsommer le solaire",
            prefix + "Le coût d'opportunité du solaire est inférieur au prix d'achat réseau actuel.",
            TARIFF_DYNAMIC, confidence, True, True, False, current_buy, export_value,
            best_buy, best_at, saving, horizon, forecast_count, dynamic_fallback=True,
        )
    if current_buy < 0:
        return EconomicDecision(
            "PRIX_ACHAT_NEGATIF", "Consommer maintenant",
            prefix + f"Prix d'achat négatif ({current_buy:.3f} €/kWh) : consommation réseau économiquement favorable.",
            TARIFF_DYNAMIC, confidence, True, False, False, current_buy, export_value,
            best_buy, best_at, saving, horizon, forecast_count, dynamic_fallback=True,
        )
    if saving is not None and saving > min_saving and best_at is not None and best_at > now + timedelta(minutes=10):
        return EconomicDecision(
            "ATTENDRE_MEILLEUR_PRIX", "Attendre un meilleur prix",
            prefix + f"Économie potentielle {saving:.3f} €/kWh en différant jusqu'au meilleur créneau connu.",
            TARIFF_DYNAMIC, confidence, False, False, False, current_buy, export_value,
            best_buy, best_at, saving, horizon, forecast_count, dynamic_fallback=True,
        )
    return EconomicDecision(
        "CONSOMMER_MAINTENANT", "Consommer maintenant",
        prefix + "Le prix actuel est proche du meilleur prix connu sur l'horizon analysé.",
        TARIFF_DYNAMIC, confidence, True, False, False, current_buy, export_value,
        best_buy, best_at, saving, horizon, forecast_count, dynamic_fallback=True,
    )


def _evaluate_dynamic_market(
    *,
    now: datetime,
    snapshot: EnergySnapshot,
    prices: dict[str, Any],
    settings: dict[str, Any],
    import_points: list[PricePoint],
    export_points: list[PricePoint],
    current_buy: float,
    export_value: float | None,
    boiler_thermal: dict[str, Any] | None,
) -> EconomicDecision:
    """Arbitrage Luminus Day-Ahead, strictement réservé au régime DYNAMIQUE."""
    horizon = DYNAMIC_ARBITRAGE_HORIZON_HOURS
    current_slot = now.replace(minute=0, second=0, microsecond=0)
    day_points = _dynamic_day_ahead_points(import_points, now, horizon_hours=horizon)
    day_points = _dynamic_day_ahead_points(
        merge_price_points(day_points, [PricePoint(current_slot, current_buy, "DYNAMIC_CURRENT")]),
        now,
        horizon_hours=horizon,
    )
    export_day_points = _dynamic_day_ahead_points(export_points, now, horizon_hours=horizon)
    if export_value is not None:
        export_day_points = _dynamic_day_ahead_points(
            merge_price_points(
                export_day_points,
                [PricePoint(current_slot, float(export_value), "DYNAMIC_EXPORT_CURRENT")],
            ),
            now,
            horizon_hours=horizon,
        )

    forecast_count = len(day_points)
    best_at, best_buy = best_start_window(day_points, now, 1.0, horizon)
    saving = (current_buy - best_buy) if best_buy is not None else None
    confidence = "HAUTE" if forecast_count >= 18 else ("MOYENNE" if forecast_count >= 6 else "FAIBLE")

    if not bool(settings.get("predictive_pricing_enabled", True)):
        return _legacy_dynamic_decision(
            now=now, snapshot=snapshot, prices=prices, settings=settings,
            import_points=import_points, current_buy=current_buy, export_value=export_value,
            best_at=best_at, best_buy=best_buy, saving=saving, confidence=confidence,
            horizon=horizon, forecast_count=forecast_count,
            reason_prefix="Prédictif prix dynamique désactivé : repli standard.",
        )
    if forecast_count < 6:
        return _legacy_dynamic_decision(
            now=now, snapshot=snapshot, prices=prices, settings=settings,
            import_points=import_points, current_buy=current_buy, export_value=export_value,
            best_at=best_at, best_buy=best_buy, saving=saving, confidence=confidence,
            horizon=horizon, forecast_count=forecast_count,
            reason_prefix="Courbe Luminus Dynamic insuffisante : repli standard.",
        )

    pmin = min(p.price for p in day_points)
    pmax = max(p.price for p in day_points)
    amplitude = pmax - pmin
    index = 0.5 if amplitude <= 1e-9 else max(0.0, min(1.0, (current_buy - pmin) / amplitude))
    position_pct = index * 100.0
    # V1.7.0 : les seuils Day-Ahead appartiennent au contrat Dynamique, pas au
    # comportement Éco/Confort.
    low_pct = max(5.0, min(60.0, float(settings.get("dynamic_favorable_position_pct", 30.0))))
    high_pct = max(low_pct, min(95.0, float(settings.get("dynamic_high_position_pct", 65.0))))
    low = low_pct / 100.0
    high = high_pct / 100.0
    if index <= low:
        band = "BAS"
    elif index >= high:
        band = "HAUT"
    else:
        band = "MEDIAN"

    ordered_prices = sorted(float(p.price) for p in day_points)
    rank = 1 + sum(1 for value in ordered_prices if value < current_buy)
    trend_threshold = max(float(settings.get("dynamic_price_significant_delta", 0.01)), 0.0)
    future_slots = [p.price for p in day_points if p.at > current_slot][:3]
    curve_trend = "STABLE"
    if future_slots:
        future_mean = sum(future_slots) / len(future_slots)
        if future_mean > current_buy + trend_threshold:
            curve_trend = "HAUSSE"
        elif future_mean < current_buy - trend_threshold:
            curve_trend = "BAISSE"

    self_consumption_advantage = current_buy - export_value if export_value is not None else current_buy
    export_margin = float(settings.get("economic_export_margin_eur_kwh", 0.01))
    export_profitable = export_value is not None and export_value > 0
    export_costly = export_value is not None and export_value < 0
    has_surplus = snapshot.export_w >= float(settings.get("economic_solar_surplus_min_w", 250.0))
    prefer_export = bool(
        has_surplus and export_profitable and self_consumption_advantage < -export_margin
    )
    prefer_self_consumption = bool(
        has_surplus and (
            export_value is None or export_costly or self_consumption_advantage >= -export_margin
        )
    )

    thermal = boiler_thermal or {}
    energy_missing = max(float(thermal.get("energy_missing_kwh") or 0.0), 0.0)
    heating_h = max(float(thermal.get("heating_duration_h") or 0.0), 0.0)
    temp_c = thermal.get("measured_temp_c")
    start_c = thermal.get("comfort_min_c")
    element_w = max(float(thermal.get("element_power_w") or settings.get("boiler_power_w", 1800.0)), 1.0)
    comfort_needed = (
        isinstance(temp_c, (int, float))
        and isinstance(start_c, (int, float))
        and float(temp_c) < float(start_c)
        and energy_missing > 0
    )
    reserved_start, reserved_end, reserved_avg = _best_consecutive_dynamic_window(day_points, now, heating_h)
    reservation_active = bool(
        energy_missing > 0 and reserved_start is not None and reserved_end is not None
        and reserved_start <= current_slot < reserved_end
    )

    solar_for_boiler_w = min(max(float(snapshot.export_w), 0.0), element_w)
    boiler_grid_needed_w = max(element_w - solar_for_boiler_w, 0.0)
    solar_opportunity = float(export_value) if export_value is not None else 0.0
    boiler_effective_cost_h = (
        boiler_grid_needed_w / 1000.0 * current_buy
        + solar_for_boiler_w / 1000.0 * solar_opportunity
    )
    future_full_grid_cost_h = element_w / 1000.0 * best_buy if best_buy is not None else None
    financial_now = bool(
        future_full_grid_cost_h is not None
        and boiler_effective_cost_h <= future_full_grid_cost_h + export_margin * (element_w / 1000.0)
    )
    solar_only_now = bool(
        snapshot.export_w >= element_w
        and (export_value is None or export_value <= (best_buy if best_buy is not None else current_buy) + export_margin)
    )
    charge_now = bool(reservation_active and index <= low)
    if energy_missing > 0 and band == "MEDIAN" and has_surplus and financial_now:
        charge_now = True
    if energy_missing > 0 and solar_only_now:
        charge_now = True

    common = dict(
        regime=TARIFF_DYNAMIC,
        confidence=confidence,
        current_buy_eur_kwh=current_buy,
        export_value_eur_kwh=export_value,
        best_future_buy_eur_kwh=best_buy,
        best_future_at=best_at,
        saving_vs_now_eur_kwh=saving,
        horizon_hours=horizon,
        forecast_points=forecast_count,
        application="ARBITRAGE_DYNAMIQUE_COURBE_LUMINUS",
        dynamic_price_index=index,
        dynamic_price_band=band,
        dynamic_price_min_eur_kwh=pmin,
        dynamic_price_max_eur_kwh=pmax,
        dynamic_curve_position_pct=position_pct,
        dynamic_curve_rank=rank,
        dynamic_curve_points=forecast_count,
        dynamic_curve_trend=curve_trend,
        self_consumption_advantage_eur_kwh=self_consumption_advantage,
        boiler_energy_missing_kwh=energy_missing,
        boiler_heating_duration_h=heating_h,
        boiler_reserved_start=reserved_start,
        boiler_reserved_end=reserved_end,
        boiler_reserved_avg_price_eur_kwh=reserved_avg,
        boiler_charge_now=charge_now,
        # 1.7.0 : un simple manque de confort n'est plus une priorité absolue.
        # Le moteur Boiler flexible décide selon confiance sondes, solaire et contrat.
        boiler_comfort_priority=False,
        boiler_comfort_needed=comfort_needed,
        boiler_effective_cost_eur_h=boiler_effective_cost_h,
        boiler_grid_power_needed_w=boiler_grid_needed_w,
    )

    reservation = ""
    if energy_missing > 0:
        if reserved_start and reserved_end and reserved_avg is not None:
            reservation = (
                f" Boiler: {energy_missing:.2f} kWh à fournir (~{heating_h:.2f} h), "
                f"créneau réseau réservé {reserved_start.strftime('%H:%M')}–{reserved_end.strftime('%H:%M')} "
                f"à {reserved_avg:.3f} €/kWh moyen."
            )
        else:
            reservation = f" Boiler: {energy_missing:.2f} kWh à fournir (~{heating_h:.2f} h), créneau complet non disponible."
    finance = (
        f" Position courbe {position_pct:.1f} % (seuil favorable {low_pct:.1f} %), achat {current_buy:.3f} €/kWh"
        + (f", réinjection {export_value:.3f} €/kWh" if export_value is not None else "")
        + f", avantage autoconsommation {self_consumption_advantage:.3f} €/kWh."
    )

    if band == "BAS":
        return EconomicDecision(
            code="DYNAMIC_BAS", label="Prix Day-Ahead favorable",
            reason="Position sous le seuil utilisateur : achats flexibles autorisés." + finance + reservation,
            flexible_start=not charge_now,
            prefer_self_consumption=prefer_self_consumption,
            prefer_export=prefer_export,
            **common,
        )
    if band == "MEDIAN":
        return EconomicDecision(
            code="DYNAMIC_MEDIAN", label="Arbitrage solaire / réseau",
            reason="Zone médiane : priorité à l'autoconsommation et comparaison du coût marginal." + finance + reservation,
            flexible_start=has_surplus and not charge_now,
            prefer_self_consumption=prefer_self_consumption,
            prefer_export=prefer_export,
            **common,
        )
    return EconomicDecision(
        code="DYNAMIC_HAUT", label="Pic Day-Ahead — achats limités",
        reason="Zone haute : nouveaux achats opportunistes bloqués; autoconsommation locale conservée." + finance + reservation,
        flexible_start=False,
        prefer_self_consumption=prefer_self_consumption,
        prefer_export=prefer_export,
        **common,
    )

def evaluate_market(
    *,
    now: datetime,
    snapshot: EnergySnapshot,
    prices: dict[str, Any],
    settings: dict[str, Any],
    import_points: list[PricePoint],
    export_points: list[PricePoint] | None = None,
    boiler_thermal: dict[str, Any] | None = None,
) -> EconomicDecision:
    regime = str(prices.get("regime") or TARIFF_TOU)
    current_buy = _float(prices.get("active_buy"))
    export_value = _float(prices.get("export_value"))
    horizon = int(float(settings.get("economic_horizon_hours", 24.0)))
    min_saving = float(settings.get("economic_min_saving_eur_kwh", 0.02))
    export_margin = float(settings.get("economic_export_margin_eur_kwh", 0.01))
    surplus_min = float(settings.get("economic_solar_surplus_min_w", 250.0))

    best_at, best_buy = best_start_window(import_points, now, 1.0, horizon)
    saving = (current_buy - best_buy) if current_buy is not None and best_buy is not None else None
    forecast_count = len(import_points)
    confidence = "HAUTE" if (regime == TARIFF_TOU and current_buy is not None) or forecast_count >= 6 else ("MOYENNE" if forecast_count >= 2 else "FAIBLE")

    if not bool(settings.get("economic_optimizer_enabled", True)):
        return EconomicDecision(
            "DESACTIVE", "Optimisation économique désactivée",
            "La couche économique est désactivée par l'utilisateur.", regime, "HAUTE", True,
            False, False, current_buy, export_value, best_buy, best_at, saving, horizon, forecast_count,
            application="DESACTIVE",
        )

    # Compensation is deliberately global and precedes dynamic arbitrage.
    if str(settings.get("network_policy")) == NETWORK_POLICY_COMPENSATION and regime != TARIFF_DYNAMIC:
        return EconomicDecision(
            "COMPENSATION_MAX_PV", "Produire au maximum",
            "Politique Compensation : la production photovoltaïque disponible doit rester libérée à 100 %.",
            regime, confidence, True, False, True, current_buy, export_value, best_buy, best_at, saving,
            horizon, forecast_count,
        )

    if current_buy is None:
        return EconomicDecision(
            "PRIX_INDISPONIBLE", "Attendre les tarifs",
            "Prix d'achat indisponible : FoxCat refuse une décision économique non chiffrée.",
            regime, "FAIBLE", False, False, False, None, export_value, best_buy, best_at, None,
            horizon, forecast_count,
        )

    # The new Day-Ahead engine is strictly isolated to DYNAMIC.
    if regime == TARIFF_DYNAMIC:
        return _evaluate_dynamic_market(
            now=now, snapshot=snapshot, prices=prices, settings=settings,
            import_points=import_points, export_points=list(export_points or []), current_buy=current_buy,
            export_value=export_value, boiler_thermal=boiler_thermal,
        )

    # ---------------- CONTRAT FIXE / MONOHORAIRE ----------------
    # Aucune pseudo-période HP/HC ne doit apparaître ici. Le prix d'achat est
    # constant ; FoxCat arbitre seulement l'autoconsommation, l'export et les
    # contraintes de distribution indépendantes (Impact, capacité, etc.).
    if regime == TARIFF_FIXED:
        has_surplus = snapshot.export_w >= surplus_min
        prefer_export = bool(
            has_surplus and export_value is not None
            and export_value > current_buy + export_margin
        )
        prefer_self = bool(
            has_surplus and (export_value is None or export_value <= current_buy + export_margin)
        )
        return EconomicDecision(
            "FIXE", "Contrat fixe — charge flexible disponible",
            "Prix d'achat constant : aucun report HP/HC n'est appliqué ; "
            "les contraintes de distribution et le surplus solaire restent pris en compte.",
            regime, "HAUTE", True, prefer_self, prefer_export, current_buy, export_value,
            current_buy, now, 0.0, horizon, forecast_count, application="CONTRAT_FIXE",
        )

    # ---------------- HP/HC BASELINE (unchanged V1.6.156 semantics) ----------------
    has_surplus = snapshot.export_w >= surplus_min
    if has_surplus and export_value is not None and export_value < 0:
        return EconomicDecision(
            "ABSORBER_SURPLUS", "Autoconsommer maintenant",
            f"La réinjection coûte {abs(export_value):.3f} €/kWh : absorber le surplus est prioritaire.",
            regime, confidence, True, True, False, current_buy, export_value, best_buy, best_at, saving,
            horizon, forecast_count,
        )
    if has_surplus and export_value is not None and best_buy is not None and export_value > best_buy + export_margin:
        return EconomicDecision(
            "EXPORTER_ET_REPORTER", "Exporter maintenant, consommer plus tard",
            f"Réinjection {export_value:.3f} €/kWh > meilleur achat futur {best_buy:.3f} €/kWh + marge : l'export est économiquement supérieur.",
            regime, confidence, False, False, True, current_buy, export_value, best_buy, best_at, saving,
            horizon, forecast_count,
        )
    if has_surplus and (export_value is None or export_value + export_margin < current_buy):
        return EconomicDecision(
            "AUTOCONSOMMER", "Autoconsommer le solaire",
            "Le coût d'opportunité de l'énergie solaire est inférieur au prix d'achat réseau actuel.",
            regime, confidence, True, True, False, current_buy, export_value, best_buy, best_at, saving,
            horizon, forecast_count,
        )

    period = str(prices.get("period") or tariff_period(now, settings))
    if period == "HC":
        return EconomicDecision(
            "CONSOMMER_HC", "Profiter des heures creuses",
            "Période HC active : les charges flexibles peuvent fonctionner au tarif bas.",
            regime, "HAUTE", True, False, False, current_buy, export_value, best_buy, best_at, saving,
            horizon, forecast_count,
        )
    if saving is not None and saving > min_saving:
        return EconomicDecision(
            "ATTENDRE_HC", "Attendre les heures creuses",
            f"Le prochain meilleur créneau réduit le coût estimé de {saving:.3f} €/kWh.",
            regime, "HAUTE", False, False, False, current_buy, export_value, best_buy, best_at, saving,
            horizon, forecast_count,
        )
    return EconomicDecision(
        "HP_ACCEPTABLE", "Consommer si nécessaire",
        "L'écart HP/HC ne dépasse pas la marge économique configurée.",
        regime, "HAUTE", True, False, False, current_buy, export_value, best_buy, best_at, saving,
        horizon, forecast_count,
    )


def recommend_flexible_load(
    *,
    now: datetime,
    snapshot: EnergySnapshot,
    prices: dict[str, Any],
    settings: dict[str, Any],
    import_points: list[PricePoint],
    duration_hours: float | None,
    energy_kwh: float | None,
    active: bool,
    market_decision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare a machine start now with future starts without interrupting active cycles."""
    if active:
        return {
            "decision": "CYCLE_EN_COURS",
            "label": "Cycle en cours — ne pas interrompre",
            "allow_start": True,
            "reason": "Un cycle actif/protégé reste souverain sur l'optimisation économique.",
            "confidence": "HAUTE",
        }

    duration = max(float(duration_hours or 1.0), 0.25)
    energy = max(float(energy_kwh or 1.0), 0.05)
    avg_power_w = energy / duration * 1000.0
    current_buy = _float(prices.get("active_buy"))
    export_value = _float(prices.get("export_value"))
    horizon = int(float(settings.get("economic_horizon_hours", 24.0)))
    min_saving = float(settings.get("economic_min_saving_eur_kwh", 0.02))
    export_margin = float(settings.get("economic_export_margin_eur_kwh", 0.01))

    if current_buy is None:
        return {
            "decision": "PRIX_INDISPONIBLE", "label": "Prix indisponible", "allow_start": False,
            "reason": "Pas de prix d'achat fiable pour comparer le cycle.", "confidence": "FAIBLE",
            "duration_h": round(duration, 3), "energy_kwh": round(energy, 3),
        }

    best_at, best_cost = best_start_window(import_points, now, duration, horizon)
    grid_now_cost = average_price(import_points, now, duration) or current_buy
    solar_fraction = min(max(snapshot.export_w, 0.0), avg_power_w) / avg_power_w if avg_power_w > 0 else 0.0
    solar_fraction = max(0.0, min(solar_fraction, 1.0))
    pv_opportunity = export_value if export_value is not None else 0.0
    effective_now = solar_fraction * pv_opportunity + (1.0 - solar_fraction) * grid_now_cost
    saving = (effective_now - best_cost) if best_cost is not None else 0.0
    confidence = "HAUTE" if len(import_points) >= 6 or str(prices.get("regime")) == TARIFF_TOU else ("MOYENNE" if len(import_points) >= 2 else "FAIBLE")

    # New relative-index rules apply to DYNAMIC only and only when enabled.
    if str(prices.get("regime")) == TARIFF_DYNAMIC and bool(settings.get("predictive_pricing_enabled", True)):
        market = market_decision or {}
        if bool(market.get("boiler_charge_now")) and float(market.get("boiler_energy_missing_kwh") or 0.0) > 0:
            allow, decision, label = False, "RESERVATION_BOILER", "Reporter — créneau Boiler réservé"
            reason = "Le créneau courant est réservé au Boiler par le planificateur Day-Ahead; les charges secondaires attendent."
        else:
            band = str(market.get("dynamic_price_band") or "")
            full_surplus = snapshot.export_w >= max(avg_power_w, 1.0)
            # Coût marginal réel du démarrage : la part solaire vaut son coût
            # d'opportunité de réinjection, la part réseau vaut le prix d'achat.
            # On compare ce coût au meilleur créneau futur connu.
            future_reference = best_cost if best_cost is not None else grid_now_cost
            financially_better_now = effective_now <= future_reference + min_saving
            solar_present = solar_fraction > 0.0

            if band == "HAUT":
                allow = bool(solar_present and financially_better_now)
                decision = "AUTOCONSO_HAUT_FINANCIERE" if allow else "DELESTAGE_PRIX_HAUT"
                label = "Démarrer — solaire financièrement préférable" if allow else "Reporter — prix dynamique élevé"
                reason = (
                    f"Haut de courbe mais coût marginal actuel {effective_now:.3f} €/kWh <= meilleur coût futur {future_reference:.3f} €/kWh grâce au solaire/réinjection."
                    if allow else
                    f"Haut de courbe : coût marginal actuel {effective_now:.3f} €/kWh > référence future {future_reference:.3f} €/kWh; démarrage reporté."
                )
            elif band == "MEDIAN":
                allow = bool(full_surplus or (solar_present and financially_better_now))
                decision = "SURPLUS_STRICT" if full_surplus else ("AUTOCONSO_HYBRIDE" if allow else "REPORTER_MEDIAN")
                label = "Démarrer sur surplus" if full_surplus else ("Démarrer — solaire + réseau optimisés" if allow else "Reporter — coût marginal défavorable")
                reason = (
                    "Plage médiane : surplus local intégral, démarrage sans achat réseau supplémentaire."
                    if full_surplus else
                    (f"Plage médiane : combinaison solaire/réseau à {effective_now:.3f} €/kWh plus pertinente que le meilleur créneau futur {future_reference:.3f} €/kWh."
                     if allow else
                     f"Plage médiane : coût marginal {effective_now:.3f} €/kWh supérieur à la référence future {future_reference:.3f} €/kWh.")
                )
            elif band == "BAS":
                allow = bool(financially_better_now or best_cost is None)
                decision = "DEMARRER_BAS" if allow else "REPORTER_BAS"
                label = "Démarrer — bas de courbe" if allow else "Reporter — meilleur créneau encore attendu"
                reason = (
                    f"Bas de courbe : coût marginal actuel {effective_now:.3f} €/kWh, référence future {future_reference:.3f} €/kWh."
                )
            else:
                # Decision fallback: keep V1.6.156 behavior below.
                allow = None
        if allow is not None:
            return {
                "decision": decision, "label": label, "allow_start": allow, "reason": reason,
                "confidence": market.get("confidence", confidence),
                "duration_h": round(duration, 3), "energy_kwh": round(energy, 3),
                "average_power_w": round(avg_power_w, 1),
                "solar_fraction_now": round(solar_fraction, 3),
                "effective_cost_now_eur_kwh": round(effective_now, 5),
                "best_future_cost_eur_kwh": round(best_cost, 5) if best_cost is not None else None,
                "best_future_at": best_at.isoformat() if best_at else None,
                "saving_eur_kwh": round(max(saving, 0.0), 5),
                "dynamic_price_index": market.get("dynamic_price_index"),
                "dynamic_price_band": market.get("dynamic_price_band"),
            }

    # Baseline generic behavior (HP/HC unchanged; dynamic standard fallback).
    if solar_fraction >= 0.5 and export_value is not None and export_value < 0:
        allow = True
        decision = "ABSORBER_SURPLUS"
        reason = "Le cycle absorbe un surplus dont la réinjection est actuellement payante/défavorable."
    elif solar_fraction >= 0.5 and export_value is not None and best_cost is not None and export_value > best_cost + export_margin:
        allow = False
        decision = "EXPORTER_ET_REPORTER"
        reason = "Vendre le surplus maintenant puis exécuter le cycle au meilleur prix futur est plus favorable."
    elif best_cost is not None and saving > min_saving and best_at is not None and best_at > now + timedelta(minutes=10):
        allow = False
        decision = "REPORTER"
        reason = f"Reporter le cycle économise environ {saving:.3f} €/kWh sur son profil moyen."
    else:
        allow = True
        decision = "DEMARRER"
        reason = "Le coût du démarrage immédiat est compétitif sur l'horizon analysé."

    return {
        "decision": decision,
        "label": {
            "ABSORBER_SURPLUS": "Démarrer pour absorber le surplus",
            "EXPORTER_ET_REPORTER": "Exporter maintenant et reporter",
            "REPORTER": "Reporter le démarrage",
            "DEMARRER": "Démarrer maintenant",
        }.get(decision, decision),
        "allow_start": allow,
        "reason": reason,
        "confidence": confidence,
        "duration_h": round(duration, 3),
        "energy_kwh": round(energy, 3),
        "average_power_w": round(avg_power_w, 1),
        "solar_fraction_now": round(solar_fraction, 3),
        "effective_cost_now_eur_kwh": round(effective_now, 5),
        "best_future_cost_eur_kwh": round(best_cost, 5) if best_cost is not None else None,
        "best_future_at": best_at.isoformat() if best_at else None,
        "saving_eur_kwh": round(max(saving, 0.0), 5),
    }
