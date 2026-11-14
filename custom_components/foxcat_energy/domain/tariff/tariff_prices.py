"""Structure Tarif → Prix associés.

Chaque tarif sélectionné à l'installation (famille + structure) possède sa
propre liste de capteurs de prix externes. Les capteurs d'un autre tarif sont
ignorés par le coordinateur, le registre et le dashboard.
"""
from __future__ import annotations

from typing import Any

from ...const import (
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
    DYNAMIC_STRUCT_BI,
    DYNAMIC_STRUCT_IMPACT,
    DYNAMIC_STRUCT_SIMPLE,
    PRICE_SOURCE_CONTRACT,
    PRICE_SOURCE_DYNAMIC,
    PRICE_SOURCE_VARIABLE,
    TARIFF_BI,
    TARIFF_DYNAMIC,
    TARIFF_MONO,
    TARIFF_STRUCTURE_IMPACT,
    TARIFF_STRUCTURE_SIMPLE,
    TARIFF_STRUCTURE_TOU,
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


# FONCTION : active_tariff — Return the selected tariff id, or None for legacy entries.
def active_tariff(config: dict[str, Any]) -> str | None:
    """Return the selected tariff id, or None for legacy entries."""
    family = config.get(CONF_TARIFF_FAMILY)
    if family == FAMILY_DYNAMIQUE:
        return TARIFF_DYNAMIQUE
    if family == FAMILY_HPHC:
        # Bi-horaire : deux prix (HP / HC). Mono-horaire et Impact : un seul prix de base.
        if config.get(CONF_TARIFF_STRUCTURE) in {"Bi-horaire", TARIFF_STRUCTURE_TOU}:
            return TARIFF_HPHC_BI
        return TARIFF_HPHC_MONO
    return None


# FONCTION : _structure_kind — Normalise la structure réseau choisie (mono / bi / impact)
def _structure_kind(value: Any) -> str:
    """Normalise la structure réseau choisie : ``simple``, ``bi`` ou ``impact``."""
    if value in {"Impact", DYNAMIC_STRUCT_IMPACT, TARIFF_STRUCTURE_IMPACT}:
        return "impact"
    if value in {"Bi-horaire", DYNAMIC_STRUCT_BI, TARIFF_STRUCTURE_TOU}:
        return "bi"
    return "simple"


# FONCTION : apply_configured_tariff — Apply the tariff selected during setup to runtime tariff settings.
def apply_configured_tariff(settings: dict[str, Any], config: dict[str, Any]) -> None:
    """Apply the tariff selected during setup to runtime tariff settings.

    Deux axes indépendants : le contrat (famille) et la structure du réseau
    (mono, bi-horaire, Impact). Toutes les combinaisons sont possibles.
    """
    tariff = active_tariff(config)
    if tariff is None:
        return
    kind = _structure_kind(config.get(CONF_TARIFF_STRUCTURE))
    structure = {
        "simple": TARIFF_STRUCTURE_SIMPLE,
        "bi": TARIFF_STRUCTURE_TOU,
        "impact": TARIFF_STRUCTURE_IMPACT,
    }[kind]
    if tariff == TARIFF_DYNAMIQUE:
        settings.update(
            {
                "price_source": PRICE_SOURCE_DYNAMIC,
                "tariff_regime": TARIFF_DYNAMIC,
                "tariff_structure": structure,
                "dynamic_structure": {
                    "simple": DYNAMIC_STRUCT_SIMPLE,
                    "bi": DYNAMIC_STRUCT_BI,
                    "impact": DYNAMIC_STRUCT_IMPACT,
                }[kind],
            }
        )
        return
    # Famille HP/HC : prix saisis à la main (contrat fixe) ou lus depuis des entités.
    source = PRICE_SOURCE_CONTRACT if config.get("price_source") == PRICE_SOURCE_CONTRACT else PRICE_SOURCE_VARIABLE
    settings.update(
        {
            "price_source": source,
            "tariff_regime": TARIFF_BI if kind == "bi" else TARIFF_MONO,
            "tariff_structure": structure,
        }
    )


# FONCTION : allowed_price_keys — Allowed price keys
def allowed_price_keys(config: dict[str, Any]) -> frozenset[str] | None:
    tariff = active_tariff(config)
    return None if tariff is None else frozenset(TARIFF_PRICE_KEYS[tariff])


# FONCTION : foreign_price_keys — Price keys that belong to another tariff than the selected one.
def foreign_price_keys(config: dict[str, Any]) -> frozenset[str]:
    """Price keys that belong to another tariff than the selected one."""
    allowed = allowed_price_keys(config)
    return frozenset() if allowed is None else ALL_PRICE_KEYS - allowed


# FONCTION : scoped_config — Conserve toutes les entités de prix configurées (tous régimes accessibles).
def scoped_config(config: dict[str, Any]) -> dict[str, Any]:
    """Keep every configured price entity; the active tariff only drives calculation routing."""
    return dict(config)
