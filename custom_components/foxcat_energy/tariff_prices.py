"""Structure Tarif → Prix associés.

Chaque tarif sélectionné à l'installation (famille + structure) possède sa
propre liste de capteurs de prix externes. Les capteurs d'un autre tarif sont
ignorés par le coordinateur, le registre et le dashboard.
"""
from __future__ import annotations

from typing import Any

from .const import (
    CONF_PRICE_AVG_TODAY,
    CONF_PRICE_AVG_TOMORROW,
    CONF_PRICE_CURRENT,
    CONF_PRICE_FORECAST_EXPORT,
    CONF_PRICE_FORECAST_IMPORT,
    CONF_PRICE_INJECTION,
    CONF_PRICE_MAX_TODAY,
    CONF_PRICE_MAX_TOMORROW,
    CONF_PRICE_MIN_TODAY,
    CONF_PRICE_MIN_TOMORROW,
    CONF_PRICE_NEXT,
    CONF_PRICE_TOMORROW_AVAILABLE,
    CONF_TARIFF_FIXED_INJECTION_PRICE_SENSOR,
    CONF_TARIFF_HC_PRICE_SENSOR,
    CONF_TARIFF_HP_PRICE_SENSOR,
)

CONF_TARIFF_FAMILY = "tariff_family"
CONF_TARIFF_STRUCTURE = "tariff_structure"
CONF_TARIFF_MONO_PRICE_SENSOR = "tariff_mono_price_sensor"

FAMILY_HPHC = "hphc"
FAMILY_DYNAMIQUE = "dynamique"

TARIFF_HPHC_MONO = "hphc_mono"
TARIFF_HPHC_BI = "hphc_bi"
TARIFF_DYNAMIQUE = "dynamique"

DYNAMIC_PRICE_KEYS: tuple[str, ...] = (
    CONF_PRICE_CURRENT, CONF_PRICE_NEXT, CONF_PRICE_INJECTION,
    CONF_PRICE_MIN_TODAY, CONF_PRICE_MAX_TODAY, CONF_PRICE_AVG_TODAY,
    CONF_PRICE_MIN_TOMORROW, CONF_PRICE_MAX_TOMORROW, CONF_PRICE_AVG_TOMORROW,
    CONF_PRICE_TOMORROW_AVAILABLE, CONF_PRICE_FORECAST_IMPORT, CONF_PRICE_FORECAST_EXPORT,
)

# Tarif → clés de configuration des prix qui lui sont associés.
TARIFF_PRICE_KEYS: dict[str, tuple[str, ...]] = {
    TARIFF_HPHC_MONO: (CONF_TARIFF_MONO_PRICE_SENSOR, CONF_TARIFF_FIXED_INJECTION_PRICE_SENSOR),
    TARIFF_HPHC_BI: (
        CONF_TARIFF_HP_PRICE_SENSOR, CONF_TARIFF_HC_PRICE_SENSOR,
        CONF_TARIFF_FIXED_INJECTION_PRICE_SENSOR,
    ),
    TARIFF_DYNAMIQUE: DYNAMIC_PRICE_KEYS,
}

ALL_PRICE_KEYS: frozenset[str] = frozenset(k for keys in TARIFF_PRICE_KEYS.values() for k in keys)


def active_tariff(config: dict[str, Any]) -> str | None:
    """Return the selected tariff id, or None for legacy entries."""
    family = config.get(CONF_TARIFF_FAMILY)
    if family == FAMILY_DYNAMIQUE:
        return TARIFF_DYNAMIQUE
    if family == FAMILY_HPHC:
        if config.get(CONF_TARIFF_STRUCTURE) == "Mono-horaire":
            return TARIFF_HPHC_MONO
        return TARIFF_HPHC_BI
    return None


def allowed_price_keys(config: dict[str, Any]) -> frozenset[str] | None:
    tariff = active_tariff(config)
    return None if tariff is None else frozenset(TARIFF_PRICE_KEYS[tariff])


def foreign_price_keys(config: dict[str, Any]) -> frozenset[str]:
    """Price keys that belong to another tariff than the selected one."""
    allowed = allowed_price_keys(config)
    return frozenset() if allowed is None else ALL_PRICE_KEYS - allowed


def scoped_config(config: dict[str, Any]) -> dict[str, Any]:
    """Drop price sensors that do not belong to the selected tariff."""
    foreign = foreign_price_keys(config)
    return {k: v for k, v in config.items() if k not in foreign} if foreign else dict(config)
