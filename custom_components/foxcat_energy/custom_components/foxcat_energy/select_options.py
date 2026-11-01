from __future__ import annotations

from typing import Any

from .const import (
    MODE_ALIASES,
    MODE_MANUAL,
    MODES,
    NETWORK_POLICIES,
    NETWORK_POLICY_COMPENSATION,
    PRICE_SOURCES,
    TARIFF_REGIMES,
    TARIFF_STRUCTURES,
)
from .runtime.migration import compatibility_tariff_regime


# FONCTION : mode_option — Mode option
def mode_option(settings: dict[str, Any]) -> str:
    value = str(settings.get("mode", MODE_MANUAL))
    canonical = MODE_ALIASES.get(value, value)
    return canonical if canonical in MODES else MODE_MANUAL


# FONCTION : tariff_regime_option — Tariff regime option
def tariff_regime_option(settings: dict[str, Any]) -> str:
    value = compatibility_tariff_regime(settings)
    return value if value in TARIFF_REGIMES else TARIFF_REGIMES[0]


# FONCTION : network_policy_option — Network policy option
def network_policy_option(settings: dict[str, Any]) -> str:
    value = str(settings.get("network_policy", NETWORK_POLICY_COMPENSATION))
    return value if value in NETWORK_POLICIES else NETWORK_POLICY_COMPENSATION


# FONCTION : constrained_option — Constrained option
def constrained_option(settings: dict[str, Any], key: str, options: list[str]) -> str:
    value = settings.get(key)
    return value if value in options else options[0]


# FONCTION : select_options_are_valid — Select options are valid
def select_options_are_valid() -> bool:
    return all(
        options and len(options) == len(set(options))
        for options in (MODES, TARIFF_REGIMES, NETWORK_POLICIES, PRICE_SOURCES, TARIFF_STRUCTURES)
    )
