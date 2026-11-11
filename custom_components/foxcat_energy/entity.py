from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VERSION
from .devices_layout import HUB_DEVICE, device_name, resolve_device
from .runtime.coordinator import FoxCatEnergyCoordinator


class FoxCatEntity(CoordinatorEntity[FoxCatEnergyCoordinator]):
    _attr_has_entity_name = True

    # MÉTHODE : FoxCatEntity.__init__ — méthode spéciale __init__
    def __init__(
        self,
        coordinator: FoxCatEnergyCoordinator,
        key: str,
        name: str,
        icon: str | None = None,
        device: str = "ems",
        *,
        enabled_default: bool | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_icon = icon
        self._device = device
        if enabled_default is not None:
            self._attr_entity_registry_enabled_default = enabled_default

    # MÉTHODE : FoxCatEntity.device_info — Device info
    @property
    def device_info(self) -> DeviceInfo:
        # Le classement est résolu ici (et non à la construction) car certains
        # modules réassignent ``_device`` après coup.
        device = resolve_device(self._key, self._device)
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.entry.entry_id}:{device}")},
            name=device_name(device),
            manufacturer="FoxCat Energy",
            model="EMS Python",
            sw_version=VERSION,
            via_device=(DOMAIN, f"{self.coordinator.entry.entry_id}:{HUB_DEVICE}") if device != HUB_DEVICE else None,
        )
