from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import FoxCatEnergyCoordinator
from .entity import FoxCatEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    c: FoxCatEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FoxCatBinary(c, "donnees_valides", "Données énergétiques valides", "mdi:database-check-outline", "energy", lambda d: d["snapshot"].valid, BinarySensorDeviceClass.CONNECTIVITY),
            FoxCatBinary(c, "machine_protegee_active", "Machine protégée active", "mdi:shield-home-outline", "machines", lambda d: d["snapshot"].machine_active),
            FoxCatBinary(c, "haute_consommation_active", "Délestage haute consommation actif", "mdi:flash-alert", "ems", lambda d: d["load_shed"].get("active"), BinarySensorDeviceClass.PROBLEM),
            FoxCatBinary(c, "boiler_autorise_cycle_protege", "Chauffe-eau autorisé pendant cycle protégé", "mdi:shield-check-outline", "machines", lambda d: d["machine_guard"].get("boiler_allowed")),
            FoxCatBinary(c, "boiler_physique", "Boiler physique", "mdi:water-boiler", "boiler", lambda d: d["snapshot"].boiler_on, BinarySensorDeviceClass.POWER),
            FoxCatBinary(c, "securite_thermique_boiler", "Sécurité thermique résistance", "mdi:thermometer-alert", "boiler", lambda d: d["snapshot"].boiler_safety_temp_c >= float(c.settings.get("boiler_temp_safety_c", 68.0)), BinarySensorDeviceClass.PROBLEM),
            FoxCatBinary(c, "fenetre_solaire", "Fenêtre solaire exploitable", "mdi:weather-sunny", "ai", lambda d: d["solar"].available),
            FoxCatBinary(c, "conflit_legacy", "Automatisation FoxCat legacy active", "mdi:alert-decagram-outline", "diagnostic", lambda d: d["legacy_conflict"], BinarySensorDeviceClass.PROBLEM),
            FoxCatBinary(c, "fenetre_machines", "Fenêtre alimentation machines", "mdi:clock-check-outline", "machines", lambda d: any(d["machine_window"].values())),
        ]
    )


class FoxCatBinary(FoxCatEntity, BinarySensorEntity):
    def __init__(self, coordinator, key, name, icon, device, getter, device_class=None):
        super().__init__(coordinator, key, name, icon, device)
        self._getter = getter
        self._attr_device_class = device_class

    @property
    def is_on(self) -> bool:
        try:
            return bool(self._getter(self.coordinator.data))
        except Exception:
            return False
