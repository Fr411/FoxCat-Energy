"""Constantes et codes de décision officiels du module Virtual Assets Core."""
from __future__ import annotations

SCHEMA_VERSION = 1
ALGORITHM_VERSION = "1.7.4-va1"

MODE_SHADOW = "shadow"
MODE_COUNTERFACTUAL = "counterfactual"

EV_MODE_AUTO = "auto"
EV_MODE_MANUAL = "manual"
EV_MODES = (EV_MODE_AUTO, EV_MODE_MANUAL)

DEFAULT_BATTERY_CAPACITY_KWH = 10.0
DEFAULT_BATTERY_INITIAL_SOC_PCT = 50.0
DEFAULT_BATTERY_MIN_SOC_PCT = 10.0
DEFAULT_BATTERY_MAX_SOC_PCT = 100.0
DEFAULT_BATTERY_RESERVE_SOC_PCT = 20.0
DEFAULT_BATTERY_MAX_CHARGE_KW = 5.0
DEFAULT_BATTERY_MAX_DISCHARGE_KW = 5.0
DEFAULT_BATTERY_CHARGE_EFF_PCT = 95.0
DEFAULT_BATTERY_DISCHARGE_EFF_PCT = 95.0

DEFAULT_EV_CAPACITY_KWH = 80.0
DEFAULT_EV_INITIAL_SOC_PCT = 50.0
DEFAULT_EV_TARGET_SOC_PCT = 80.0
DEFAULT_EV_MIN_SAFETY_SOC_PCT = 15.0
DEFAULT_EV_MOBILITY_RESERVE_PCT = 20.0
DEFAULT_EV_TRIP_KWH = 15.0
DEFAULT_EV_MAX_CHARGE_KW = 7.4
DEFAULT_EV_CHARGE_EFF_PCT = 90.0

REASON_SOLAR_SURPLUS_AVAILABLE = "SOLAR_SURPLUS_AVAILABLE"
REASON_LOW_IMPORT_PRICE = "LOW_IMPORT_PRICE"
REASON_HIGH_IMPORT_PRICE = "HIGH_IMPORT_PRICE"
REASON_EV_DEPART_DEADLINE = "EV_DEPART_DEADLINE"
REASON_SOC_RESERVE_REQUIRED = "SOC_RESERVE_REQUIRED"
REASON_INSUFFICIENT_TARIFF_DATA = "INSUFFICIENT_TARIFF_DATA"
REASON_FORECAST_UNAVAILABLE = "FORECAST_UNAVAILABLE"
REASON_NO_ECONOMIC_GAIN = "NO_ECONOMIC_GAIN"
REASON_ASSET_LIMIT_REACHED = "ASSET_LIMIT_REACHED"

REASON_DESCRIPTIONS: dict[str, str] = {
    REASON_SOLAR_SURPLUS_AVAILABLE: "Surplus photovoltaïque disponible valorisé dans les actifs virtuels.",
    REASON_LOW_IMPORT_PRICE: "Prix final d'importation bas permettant un arbitrage économique positif.",
    REASON_HIGH_IMPORT_PRICE: "Prix final d'importation élevé : décharge ou maintien de réserve pour éviter l'import coûteux.",
    REASON_EV_DEPART_DEADLINE: "Échéance de départ du véhicule électrique prioritaire.",
    REASON_SOC_RESERVE_REQUIRED: "Préservation du SOC de réserve ou du seuil minimal de sécurité.",
    REASON_INSUFFICIENT_TARIFF_DATA: "Données tarifaires finales absentes ou incomplètes : arbitrage désactivé.",
    REASON_FORECAST_UNAVAILABLE: "Prévisions non disponibles : repli sur les seules mesures observées.",
    REASON_NO_ECONOMIC_GAIN: "Gain économique net insuffisant après pertes de rendement et coût d'usure.",
    REASON_ASSET_LIMIT_REACHED: "Limite physique virtuelle de puissance ou de capacité atteinte.",
}

INTERNAL_TO_OFFICIAL_REASON: dict[str, str] = {
    "solar_surplus_to_battery": REASON_SOLAR_SURPLUS_AVAILABLE,
    "ev_solar": REASON_SOLAR_SURPLUS_AVAILABLE,
    "tariff_arbitrage": REASON_LOW_IMPORT_PRICE,
    "import_reduction": REASON_HIGH_IMPORT_PRICE,
    "holdback_for_higher_price": REASON_HIGH_IMPORT_PRICE,
    "ev_departure_need": REASON_EV_DEPART_DEADLINE,
    "reserve_preserved": REASON_SOC_RESERVE_REQUIRED,
    "price_missing_no_arbitrage": REASON_INSUFFICIENT_TARIFF_DATA,
    "price_missing_ev_must_charge": REASON_INSUFFICIENT_TARIFF_DATA,
    "wear_exceeds_price": REASON_NO_ECONOMIC_GAIN,
    "wear_unknown": REASON_NO_ECONOMIC_GAIN,
}


def map_official_reasons(internal_reasons: tuple[str, ...] | list[str]) -> list[str]:
    """Traduit les raisons internes du planificateur en codes officiels stables."""
    codes: list[str] = []
    for r in internal_reasons:
        code = INTERNAL_TO_OFFICIAL_REASON.get(r, r.upper())
        if code not in codes:
            codes.append(code)
    if not codes:
        codes.append(REASON_NO_ECONOMIC_GAIN)
    return codes


def describe_reasons(codes: list[str] | tuple[str, ...]) -> str:
    """Retourne une explication humaine lisible à partir des codes officiels."""
    return " | ".join(REASON_DESCRIPTIONS.get(c, c) for c in codes)
