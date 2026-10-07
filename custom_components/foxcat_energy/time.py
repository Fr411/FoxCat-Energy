from __future__ import annotations

from datetime import time

from homeassistant.components.time import TimeEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, TIME_SETTING_KEYS
from .coordinator import FoxCatEnergyCoordinator
from .entity import FoxCatEntity

_TIME_NAMES = {
    "washer_on_1": "Lave-linge · début plage 1",
    "washer_off_1": "Lave-linge · fin plage 1",
    "washer_on_2": "Lave-linge · début plage 2",
    "washer_off_2": "Lave-linge · fin plage 2",
    "dryer_on_1": "Sèche-linge · début plage 1",
    "dryer_off_1": "Sèche-linge · fin plage 1",
    "dryer_on_2": "Sèche-linge · début plage 2",
    "dryer_off_2": "Sèche-linge · fin plage 2",
    "dishwasher_on_1": "Lave-vaisselle · début plage 1",
    "dishwasher_off_1": "Lave-vaisselle · fin plage 1",
    "dishwasher_on_2": "Lave-vaisselle · début plage 2",
    "dishwasher_off_2": "Lave-vaisselle · fin plage 2",
    "tariff_hp_start_1": "Heures pleines · début plage 1",
    "tariff_hp_end_1": "Heures pleines · fin plage 1",
    "tariff_hp_start_2": "Heures pleines · début plage 2",
    "tariff_hp_end_2": "Heures pleines · fin plage 2",
    "impact_eco_start_1": "Impact · début période éco 1",
    "impact_eco_end_1": "Impact · fin période éco 1",
    "impact_eco_start_2": "Impact · début période éco 2",
    "impact_eco_end_2": "Impact · fin période éco 2",
    "impact_peak_start": "Impact · début période de pointe",
    "impact_peak_end": "Impact · fin période de pointe",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: FoxCatEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        FoxCatSettingTime(coordinator, key)
        for key in TIME_SETTING_KEYS
    )


class FoxCatSettingTime(FoxCatEntity, TimeEntity):
    def __init__(self, coordinator: FoxCatEnergyCoordinator, key: str) -> None:
        self._setting_key = key
        name = _TIME_NAMES.get(key, key.replace("_", " ").capitalize())
        super().__init__(coordinator, f"heure_{key}", name, "mdi:clock-outline", "pricing" if key.startswith(("tariff_", "impact_")) else "machines")

    @property
    def native_value(self) -> time | None:
        try:
            return time.fromisoformat(str(self.coordinator.settings[self._setting_key]))
        except (KeyError, TypeError, ValueError):
            return None

    async def async_set_value(self, value: time) -> None:
        await self.coordinator.async_set_setting(self._setting_key, value.isoformat())
