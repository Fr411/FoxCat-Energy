from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .runtime.coordinator import FoxCatEnergyCoordinator
from .entity import FoxCatEntity


# FONCTION ASYNCHRONE : async_setup_entry — traitement asynchrone : setup entry
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    c: FoxCatEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FoxCatBinary(c, "alerte_foxcat", "Alerte de panne FoxCat", "mdi:alert-circle-outline", "ems", lambda d: d["health"]["count"] > 0, BinarySensorDeviceClass.PROBLEM, attributes=lambda d: {"gravite": d["health"]["status"], "alertes": d["health"]["alerts"]}),
            FoxCatBinary(c, "internet_en_ligne", "Internet en ligne", "mdi:web", "ems", lambda d: d["connectivity"]["online"], BinarySensorDeviceClass.CONNECTIVITY, attributes=lambda d: {"depuis": d["connectivity"]["since"], "mode_backup_actif": d["connectivity"]["backup_active"]}),
            FoxCatBinary(c, "mode_backup_actif", "Mode Backup actif", "mdi:cloud-off-outline", "ems", lambda d: d["connectivity"]["backup_active"], BinarySensorDeviceClass.RUNNING, attributes=lambda d: {"mode_backup_active": d["connectivity"]["backup_enabled"], "prises_memorisees": d["connectivity"]["saved_machines"]}),
            FoxCatBinary(c, "donnees_valides", "Données énergétiques valides", "mdi:database-check-outline", "energy", lambda d: d["snapshot"].valid, BinarySensorDeviceClass.CONNECTIVITY),
            FoxCatBinary(c, "machine_protegee_active", "Machine protégée active", "mdi:shield-home-outline", "machines", lambda d: d["snapshot"].machine_active),
            FoxCatBinary(c, "chauffage_decalage_actif", "Décalage actif", "mdi:radiator", "ems", lambda d: float(d["heating_boost"].get("offset_c") or 0.0) > 0.0),
            FoxCatBinary(c, "haute_consommation_active", "Délestage haute consommation actif", "mdi:flash-alert", "ems", lambda d: d["load_shed"].get("active"), BinarySensorDeviceClass.PROBLEM),
            FoxCatBinary(c, "boiler_autorise_cycle_protege", "Chauffe-eau autorisé pendant cycle protégé", "mdi:shield-check-outline", "machines", lambda d: d["machine_guard"].get("boiler_allowed")),
            FoxCatBinary(c, "boiler_physique", "Boiler physique", "mdi:water-boiler", "boiler", lambda d: d["snapshot"].boiler_on, BinarySensorDeviceClass.POWER),
            FoxCatBinary(c, "securite_thermique_boiler", "Sécurité thermique résistance", "mdi:thermometer-alert", "boiler", lambda d: d["snapshot"].boiler_safety_temp_c >= float(c.settings.get("boiler_temp_safety_c", 68.0)), BinarySensorDeviceClass.PROBLEM),
            FoxCatBinary(c, "fenetre_solaire", "Fenêtre solaire exploitable", "mdi:weather-sunny", "ai", lambda d: d["solar"].available),
            FoxCatBinary(c, "conflit_legacy", "Automatisation FoxCat legacy active", "mdi:alert-decagram-outline", "diagnostic", lambda d: d["legacy_conflict"], BinarySensorDeviceClass.PROBLEM),
            FoxCatBinary(c, "fenetre_machines", "Fenêtre alimentation machines", "mdi:clock-check-outline", "machines", lambda d: any(d["machine_window"].values())),
            FoxCatBinary(c, "fenetre_prix_favorable_day_ahead", "Fenêtre prix favorable Day-Ahead", "mdi:cash-clock", "pricing", lambda d: bool(d.get("economic", {}).get("day_ahead", {}).get("active") and d.get("economic", {}).get("day_ahead", {}).get("favorable_now"))),
        ]
    )


class FoxCatBinary(FoxCatEntity, BinarySensorEntity):
    # MÉTHODE : FoxCatBinary.__init__ — méthode spéciale __init__
    def __init__(self, coordinator, key, name, icon, device, getter, device_class=None, attributes=None):
        super().__init__(coordinator, key, name, icon, device)
        self._getter = getter
        self._attr_device_class = device_class
        self._attributes_getter = attributes

    # MÉTHODE : FoxCatBinary.extra_state_attributes — Attributs optionnels
    @property
    def extra_state_attributes(self):
        if self._attributes_getter is None:
            return None
        try:
            return dict(self._attributes_getter(self.coordinator.data) or {})
        except Exception:
            return None

    # MÉTHODE : FoxCatBinary.is_on — Is on
    @property
    def is_on(self) -> bool:
        try:
            return bool(self._getter(self.coordinator.data))
        except Exception:
            return False
