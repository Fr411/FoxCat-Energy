"""Validated configuration for the read-only virtual-assets simulator."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .models import VirtualAssetsError, require_number

CONF_ENABLED = "virtual_assets_enabled"
CONF_SHADOW = "virtual_assets_shadow"
CONF_BATTERY_CAPACITY = "virtual_battery_capacity_kwh"
CONF_BATTERY_MAX_CHARGE = "virtual_battery_max_charge_kw"
CONF_BATTERY_MAX_DISCHARGE = "virtual_battery_max_discharge_kw"
CONF_BATTERY_CHARGE_EFFICIENCY = "virtual_battery_charge_efficiency_pct"
CONF_BATTERY_DISCHARGE_EFFICIENCY = "virtual_battery_discharge_efficiency_pct"
CONF_BATTERY_RESERVE = "virtual_battery_reserve_soc_pct"
CONF_EV_ENABLED = "virtual_ev_enabled"
CONF_EV_CAPACITY = "virtual_ev_capacity_kwh"
CONF_EV_MAX_CHARGE = "virtual_ev_max_charge_kw"
CONF_EV_CHARGE_EFFICIENCY = "virtual_ev_charge_efficiency_pct"


@dataclass(frozen=True, slots=True)
class BatterySpec:
    capacity_kwh: float = 10.0
    max_charge_kw: float = 5.0
    max_discharge_kw: float = 5.0
    charge_efficiency: float = 0.95
    discharge_efficiency: float = 0.95
    min_soc_pct: float = 10.0
    max_soc_pct: float = 100.0
    reserve_soc_pct: float = 20.0
    capex_eur: float | None = None
    rated_throughput_kwh: float | None = None
    degradation_pct_per_year: float | None = None

    def __post_init__(self) -> None:
        require_number("capacity_kwh", self.capacity_kwh, minimum=0, exclusive_min=True)
        require_number("max_charge_kw", self.max_charge_kw, minimum=0)
        require_number("max_discharge_kw", self.max_discharge_kw, minimum=0)
        require_number("charge_efficiency", self.charge_efficiency, minimum=0, maximum=1, exclusive_min=True)
        require_number("discharge_efficiency", self.discharge_efficiency, minimum=0, maximum=1, exclusive_min=True)
        require_number("min_soc_pct", self.min_soc_pct, minimum=0, maximum=100)
        require_number("max_soc_pct", self.max_soc_pct, minimum=0, maximum=100)
        require_number("reserve_soc_pct", self.reserve_soc_pct, minimum=0, maximum=100)
        if not self.min_soc_pct <= self.reserve_soc_pct <= self.max_soc_pct:
            raise VirtualAssetsError("reserve_soc_pct doit être compris entre min_soc_pct et max_soc_pct")
        if self.min_soc_pct >= self.max_soc_pct:
            raise VirtualAssetsError("min_soc_pct doit être inférieur à max_soc_pct")
        if self.capex_eur is not None:
            require_number("capex_eur", self.capex_eur, minimum=0)
        if self.rated_throughput_kwh is not None:
            require_number("rated_throughput_kwh", self.rated_throughput_kwh, minimum=0, exclusive_min=True)
        if self.degradation_pct_per_year is not None:
            require_number("degradation_pct_per_year", self.degradation_pct_per_year, minimum=0, maximum=100)


@dataclass(frozen=True, slots=True)
class EVSpec:
    capacity_kwh: float = 80.0
    max_charge_kw: float = 7.4
    charge_efficiency: float = 0.9
    initial_soc_pct: float = 50.0
    min_safety_soc_pct: float = 15.0
    mobility_reserve_pct: float = 20.0
    trip_kwh: float = 15.0

    def __post_init__(self) -> None:
        require_number("capacity_kwh", self.capacity_kwh, minimum=0, exclusive_min=True)
        require_number("max_charge_kw", self.max_charge_kw, minimum=0, exclusive_min=True)
        require_number("charge_efficiency", self.charge_efficiency, minimum=0, maximum=1, exclusive_min=True)
        require_number("initial_soc_pct", self.initial_soc_pct, minimum=0, maximum=100)
        require_number("min_safety_soc_pct", self.min_safety_soc_pct, minimum=0, maximum=100)
        require_number("mobility_reserve_pct", self.mobility_reserve_pct, minimum=0, maximum=100)
        require_number("trip_kwh", self.trip_kwh, minimum=0)


@dataclass(frozen=True, slots=True)
class PlannerConfig:
    horizon_slots: int = 48
    min_arbitrage_margin_eur_kwh: float = 0.02
    wear_cost_eur_per_kwh: float | None = None
    allow_grid_arbitrage: bool = True
    allow_export_arbitrage: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.horizon_slots, bool) or not isinstance(self.horizon_slots, int) or self.horizon_slots < 1:
            raise VirtualAssetsError("horizon_slots doit être un entier positif")
        require_number("min_arbitrage_margin_eur_kwh", self.min_arbitrage_margin_eur_kwh, minimum=0)
        if self.wear_cost_eur_per_kwh is not None:
            require_number("wear_cost_eur_per_kwh", self.wear_cost_eur_per_kwh, minimum=0)
        if not isinstance(self.allow_grid_arbitrage, bool):
            raise VirtualAssetsError("allow_grid_arbitrage doit être un booléen")
        if not isinstance(self.allow_export_arbitrage, bool):
            raise VirtualAssetsError("allow_export_arbitrage doit être un booléen")


@dataclass(frozen=True, slots=True)
class VirtualAssetsConfig:
    enabled: bool = False
    shadow_mode: bool = True
    battery: BatterySpec = field(default_factory=BatterySpec)
    ev: EVSpec | None = None
    planner: PlannerConfig = field(default_factory=PlannerConfig)

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool) or not isinstance(self.shadow_mode, bool):
            raise VirtualAssetsError("Les modes du module doivent être des booléens")


def _setting_number(settings: Mapping[str, Any], key: str, default: float) -> float:
    value = settings.get(key, default)
    return require_number(key, value)


def config_from_settings(settings: Mapping[str, Any] | None) -> VirtualAssetsConfig:
    """Build a validated simulator configuration; enablement is opt-in and strict."""
    values = settings if isinstance(settings, Mapping) else {}
    battery = BatterySpec(
        capacity_kwh=_setting_number(values, CONF_BATTERY_CAPACITY, 10.0),
        max_charge_kw=_setting_number(values, CONF_BATTERY_MAX_CHARGE, 5.0),
        max_discharge_kw=_setting_number(values, CONF_BATTERY_MAX_DISCHARGE, 5.0),
        charge_efficiency=_setting_number(values, CONF_BATTERY_CHARGE_EFFICIENCY, 95.0) / 100.0,
        discharge_efficiency=_setting_number(values, CONF_BATTERY_DISCHARGE_EFFICIENCY, 95.0) / 100.0,
        reserve_soc_pct=_setting_number(values, CONF_BATTERY_RESERVE, 20.0),
    )
    ev = None
    if values.get(CONF_EV_ENABLED) is True:
        ev = EVSpec(
            capacity_kwh=_setting_number(values, CONF_EV_CAPACITY, 80.0),
            max_charge_kw=_setting_number(values, CONF_EV_MAX_CHARGE, 7.4),
            charge_efficiency=_setting_number(values, CONF_EV_CHARGE_EFFICIENCY, 90.0) / 100.0,
            initial_soc_pct=_setting_number(values, "virtual_ev_initial_soc_pct", 50.0),
        )
    return VirtualAssetsConfig(
        enabled=values.get(CONF_ENABLED) is True,
        shadow_mode=values.get(CONF_SHADOW, True) is not False,
        battery=battery,
        ev=ev,
        planner=PlannerConfig(
            wear_cost_eur_per_kwh=(
                None
                if values.get("battery_degradation_cost_eur_kwh") is None
                else _setting_number(values, "battery_degradation_cost_eur_kwh", 0.0)
            ),
            allow_export_arbitrage=(
                values.get("tariff_regime") == "Dynamique"
                or values.get("price_source") in {"dynamic", "integration"}
            )
        ),
    )
