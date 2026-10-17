"""Configuration du module Virtual Assets. Désactivé par défaut."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .models import VirtualAssetsError, require_number

CONF_ENABLED = "virtual_assets_enabled"
CONF_SHADOW = "virtual_assets_shadow_mode"


@dataclass(frozen=True, slots=True)
class BatterySpec:
    """Défauts : 10 kWh utile, 5 kW, rendements 95 % / 95 %, réserve 20 %."""

    capacity_kwh: float = 10.0
    max_charge_kw: float = 5.0
    max_discharge_kw: float = 5.0
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95
    min_soc_pct: float = 10.0       # plancher physique
    max_soc_pct: float = 100.0
    reserve_soc_pct: float = 20.0   # réserve préservée pour l'arbitrage
    rated_throughput_kwh: float | None = None   # énergie cumulée garantie (usure)
    capex_eur: float | None = None
    degradation_pct_per_year: float | None = None

    def __post_init__(self) -> None:
        require_number("capacity_kwh", self.capacity_kwh, minimum=0, exclusive_min=True)
        require_number("max_charge_kw", self.max_charge_kw, minimum=0, exclusive_min=True)
        require_number("max_discharge_kw", self.max_discharge_kw, minimum=0, exclusive_min=True)
        for n in ("charge_efficiency", "discharge_efficiency"):
            require_number(n, getattr(self, n), minimum=0, maximum=1, exclusive_min=True)
        lo = require_number("min_soc_pct", self.min_soc_pct, minimum=0, maximum=100)
        hi = require_number("max_soc_pct", self.max_soc_pct, minimum=0, maximum=100)
        res = require_number("reserve_soc_pct", self.reserve_soc_pct, minimum=0, maximum=100)
        if not lo < hi:
            raise VirtualAssetsError("min_soc_pct doit être < max_soc_pct")
        if not lo <= res <= hi:
            raise VirtualAssetsError("reserve_soc_pct doit être entre min_soc_pct et max_soc_pct")
        for n in ("rated_throughput_kwh", "capex_eur", "degradation_pct_per_year"):
            v = getattr(self, n)
            if v is not None:
                require_number(n, v, minimum=0, exclusive_min=(n == "rated_throughput_kwh"))


@dataclass(frozen=True, slots=True)
class EVSpec:
    """Défauts : 50 kWh, charge AC 7.4 kW, rendement 90 %, pas de V2G."""

    capacity_kwh: float = 50.0
    max_charge_kw: float = 7.4
    charge_efficiency: float = 0.90

    def __post_init__(self) -> None:
        require_number("capacity_kwh", self.capacity_kwh, minimum=0, exclusive_min=True)
        require_number("max_charge_kw", self.max_charge_kw, minimum=0, exclusive_min=True)
        require_number("charge_efficiency", self.charge_efficiency, minimum=0, maximum=1,
                       exclusive_min=True)


@dataclass(frozen=True, slots=True)
class PlannerConfig:
    horizon_slots: int = 48
    min_arbitrage_margin_eur_kwh: float = 0.02
    wear_cost_eur_per_kwh: float | None = None   # None : dérivé de capex/rated_throughput si dispo
    allow_grid_arbitrage: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.horizon_slots, bool) or not isinstance(self.horizon_slots, int) \
                or self.horizon_slots < 1:
            raise VirtualAssetsError("horizon_slots doit être un entier >= 1")
        require_number("min_arbitrage_margin_eur_kwh", self.min_arbitrage_margin_eur_kwh, minimum=0)
        if self.wear_cost_eur_per_kwh is not None:
            require_number("wear_cost_eur_per_kwh", self.wear_cost_eur_per_kwh, minimum=0)


@dataclass(frozen=True, slots=True)
class VirtualAssetsConfig:
    enabled: bool = False
    shadow_mode: bool = True
    battery: BatterySpec = field(default_factory=BatterySpec)
    ev: EVSpec | None = None
    planner: PlannerConfig = field(default_factory=PlannerConfig)


def config_from_settings(settings: Mapping[str, Any] | None) -> VirtualAssetsConfig:
    """Lit les réglages ; sans clé ``virtual_assets_enabled`` le module reste désactivé."""
    settings = settings or {}
    return VirtualAssetsConfig(
        enabled=settings.get(CONF_ENABLED) is True,
        shadow_mode=settings.get(CONF_SHADOW, True) is not False,
    )
