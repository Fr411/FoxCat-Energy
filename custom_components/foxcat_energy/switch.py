from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, SWITCH_DEFINITIONS
from .coordinator import FoxCatEnergyCoordinator
from .entity import FoxCatEntity
from .machines import MachineDefinition


def _device_for(key: str) -> str:
    if key.startswith("boiler") or key == "agressivite_ecs":
        return "boiler"
    if key.startswith("pri"):
        return "pri"
    if key in {"washer_enabled", "dryer_enabled", "dishwasher_enabled"}:
        return "machines"
    if key in {"solar_advisor_enabled", "solar_forecast_arbitrage"}:
        return "ai"
    if key == "predictive_pricing_enabled" or key.startswith("dynamic_") or key.startswith("economic_"):
        return "pricing"
    return "ems"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: FoxCatEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [FoxCatSettingSwitch(coordinator, key, name, icon) for key, (name, icon) in SWITCH_DEFINITIONS.items()]
    # V1.3 : une entité de gestion par machine extensible. Les trois machines
    # historiques conservent leurs anciens switches pour compatibilité.
    legacy_keys = {"washer_enabled", "dryer_enabled", "dishwasher_enabled"}
    entities.extend(
        FoxCatMachineManagementSwitch(coordinator, machine)
        for machine in coordinator.machines
        if machine.setting_key not in legacy_keys
    )
    async_add_entities(entities)


class FoxCatSettingSwitch(FoxCatEntity, SwitchEntity):
    def __init__(self, coordinator: FoxCatEnergyCoordinator, key: str, name: str, icon: str) -> None:
        super().__init__(coordinator, key, name, icon, _device_for(key))
        if key == "predictive_pricing_enabled":
            self._attr_suggested_object_id = "foxcat_predictive_pricing_enabled"
        elif key == "solar_forecast_arbitrage":
            self._attr_suggested_object_id = "foxcat_solar_forecast_arbitrage"

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.settings.get(self._key, False))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_setting(self._key, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_setting(self._key, False)


class FoxCatMachineManagementSwitch(FoxCatEntity, SwitchEntity):
    def __init__(self, coordinator: FoxCatEnergyCoordinator, machine: MachineDefinition) -> None:
        self.machine = machine
        super().__init__(coordinator, f"machine_{machine.machine_id}_gestion", f"Gestion {machine.name}", "mdi:power-socket-eu", "machines")

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.settings.get(self.machine.setting_key, self.machine.automatic_default))

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_machine_enabled(self.machine.machine_id, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_machine_enabled(self.machine.machine_id, False)
