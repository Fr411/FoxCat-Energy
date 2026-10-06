from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VERSION
from .coordinator import FoxCatEnergyCoordinator


class FoxCatEntity(CoordinatorEntity[FoxCatEnergyCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: FoxCatEnergyCoordinator, key: str, name: str, icon: str | None = None, device: str = "ems") -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_icon = icon
        self._device = device

    @property
    def device_info(self) -> DeviceInfo:
        names = {
            "sources": "FoxCat Energy – Sources énergétiques",
            "energy": "FoxCat Energy – Énergie",
            "pri": "FoxCat Energy – Onduleur",
            "inverter": "FoxCat Energy – Onduleur",
            "ems": "FoxCat Energy – EMS",
            "energy_bus": "FoxCat Energy – Energy Bus",
            "machines": "FoxCat Energy – Machines",
            "machine_learning": "FoxCat Energy – Machine Learning",
            "ai": "FoxCat Energy – IA",
            "boiler": "FoxCat Energy – Boiler",
            "pricing": "FoxCat Energy – Tarification",
            "metronome": "FoxCat Energy – Métronome",
            "diagnostic": "FoxCat Energy – Diagnostic",
            "user_functions": "FoxCat Energy – Fonctions utilisateur",
            "solar": "FoxCat Energy – IA",
            "accounting": "FoxCat Energy – Énergie",
        }
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.entry.entry_id}:{self._device}")},
            name=names.get(self._device, "FoxCat Energy"),
            manufacturer="FoxCat Energy",
            model="EMS Python",
            sw_version=VERSION,
            via_device=(DOMAIN, f"{self.coordinator.entry.entry_id}:ems") if self._device != "ems" else None,
        )
