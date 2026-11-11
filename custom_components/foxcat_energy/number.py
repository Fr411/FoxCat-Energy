from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import heating_boost as heating
from .const import DOMAIN, NUMBER_DEFINITIONS
from .runtime.coordinator import FoxCatEnergyCoordinator
from .entity import FoxCatEntity


# FONCTION : _device_for — Device for
def _device_for(key: str) -> str:
    if key.startswith("metronome"):
        return "metronome"
    if key.startswith("boiler") or key in {"coverage_solar_min_percent", "import_boiler_max_w", "surplus_pv_min_agressivite_w", "autoconsommation_cible_percent", "autoconsommation_min_percent"}:
        return "boiler"
    if key.startswith("pri") or key == "inverter_power_w":
        return "pri"
    if key.startswith("solar_"):
        return "ai"
    if key.startswith("dynamic_") or key.startswith("tariff_") or key.startswith("economic_"):
        return "pricing"
    return "ems"


# FONCTION ASYNCHRONE : async_setup_entry — traitement asynchrone : setup entry
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: FoxCatEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [FoxCatSettingNumber(coordinator, key, *definition) for key, definition in NUMBER_DEFINITIONS.items()]
        + [FoxCatHeatingAppliedNumber(coordinator)]
    )


class FoxCatHeatingAppliedNumber(FoxCatEntity, NumberEntity):
    """Décalage actuellement inclus dans les presets du thermostat.

    Créé et conservé par FoxCat (aucun helper à créer à la main). Ce n'est pas un
    réglage : il est volontairement absent des profils et de « Réinitialiser les
    réglages », car une remise à zéro ne retirerait pas le décalage des presets.
    """

    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0.0
    _attr_native_max_value = heating.APPLIED_MAX_C
    _attr_native_step = heating.APPLIED_STEP_C
    _attr_native_unit_of_measurement = "°C"

    # MÉTHODE : FoxCatHeatingAppliedNumber.__init__ — méthode spéciale __init__
    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(
            coordinator, "heating_applied_c", "Décalage appliqué aux presets", "mdi:thermometer-check", "ems"
        )

    # MÉTHODE : FoxCatHeatingAppliedNumber.native_value — Native value
    @property
    def native_value(self) -> float:
        return float(self.coordinator.heating_applied_c)

    # MÉTHODE : FoxCatHeatingAppliedNumber.async_set_native_value — traitement asynchrone : set native value
    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_heating_applied(value)


class FoxCatSettingNumber(FoxCatEntity, NumberEntity):
    _attr_mode = NumberMode.BOX

    # MÉTHODE : FoxCatSettingNumber.__init__ — méthode spéciale __init__
    def __init__(self, coordinator: FoxCatEnergyCoordinator, key: str, name: str, minimum: float, maximum: float, step: float, unit: str | None, icon: str) -> None:
        super().__init__(coordinator, key, name, icon, _device_for(key))
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        if key == "dynamic_favorable_position_pct":
            self._attr_suggested_object_id = "foxcat_seuil_prix_dynamique"

    # MÉTHODE : FoxCatSettingNumber.native_value — Native value
    @property
    def native_value(self) -> float:
        return float(self.coordinator.settings.get(self._key, 0.0))

    # MÉTHODE : FoxCatSettingNumber.async_set_native_value — traitement asynchrone : set native value
    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_setting(self._key, float(value))
