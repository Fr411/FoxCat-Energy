from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODE_MANUAL, MODES, TARIFF_REGIMES, NETWORK_POLICIES, NETWORK_POLICY_COMPENSATION, PRICE_SOURCES, TARIFF_STRUCTURES
from .coordinator import FoxCatEnergyCoordinator
from .entity import FoxCatEntity
from .migration import compatibility_tariff_regime


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: FoxCatEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FoxCatModeSelect(coordinator),
            FoxCatTariffRegimeSelect(coordinator), FoxCatPriceSourceSelect(coordinator), FoxCatTariffStructureSelect(coordinator),
            FoxCatNetworkPolicySelect(coordinator),
            FoxCatPriManualLevelSelect(coordinator),
        ]
    )


class FoxCatModeSelect(FoxCatEntity, SelectEntity):
    _attr_options = MODES

    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "mode_ems", "Mode EMS", "mdi:home-lightning-bolt", "ems")

    @property
    def current_option(self) -> str | None:
        value = str(self.coordinator.settings.get("mode"))
        return value if value in MODES else MODE_MANUAL

    async def async_select_option(self, option: str) -> None:
        if option not in MODES:
            return
        await self.coordinator.async_set_mode(option)



class FoxCatPriceSourceSelect(FoxCatEntity, SelectEntity):
    _attr_options=PRICE_SOURCES
    def __init__(self,c): super().__init__(c,"source_prix","Source du prix","mdi:database-clock-outline","pricing")
    @property
    def current_option(self): return self.coordinator.settings.get("price_source")
    async def async_select_option(self,option):
        if option in PRICE_SOURCES: await self.coordinator.async_set_setting("price_source",option)
class FoxCatTariffStructureSelect(FoxCatEntity, SelectEntity):
    _attr_options=TARIFF_STRUCTURES
    def __init__(self,c): super().__init__(c,"structure_tarifaire","Structure tarifaire","mdi:timeline-clock-outline","pricing")
    @property
    def current_option(self): return self.coordinator.settings.get("tariff_structure")
    async def async_select_option(self,option):
        if option in TARIFF_STRUCTURES: await self.coordinator.async_set_setting("tariff_structure",option)

class FoxCatTariffRegimeSelect(FoxCatEntity, SelectEntity):
    _attr_options = TARIFF_REGIMES

    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "regime_tarifaire", "Régime tarifaire", "mdi:cash-sync", "pricing")

    @property
    def current_option(self) -> str | None:
        value = compatibility_tariff_regime(self.coordinator.settings)
        return value if value in TARIFF_REGIMES else None

    async def async_select_option(self, option: str) -> None:
        if option not in TARIFF_REGIMES:
            return
        await self.coordinator.async_set_setting("tariff_regime", option)


class FoxCatNetworkPolicySelect(FoxCatEntity, SelectEntity):
    _attr_options = NETWORK_POLICIES

    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "politique_reseau", "Politique réseau", "mdi:transmission-tower", "pricing")

    @property
    def current_option(self) -> str | None:
        value = str(self.coordinator.settings.get("network_policy", NETWORK_POLICY_COMPENSATION))
        return value if value in NETWORK_POLICIES else NETWORK_POLICY_COMPENSATION

    async def async_select_option(self, option: str) -> None:
        if option not in NETWORK_POLICIES:
            return
        await self.coordinator.async_set_setting("network_policy", option)


class FoxCatPriManualLevelSelect(FoxCatEntity, SelectEntity):
    _attr_options = [f"{level} %" for level in range(0, 101, 10)]

    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "pri_niveau_manuel", "Niveau réduction puissance onduleur manuel", "mdi:tune-vertical", "pri")

    @property
    def current_option(self) -> str | None:
        level = self.coordinator._rrcr_level()
        return f"{level} %" if level in range(0, 101, 10) else None

    async def async_select_option(self, option: str) -> None:
        if str(self.coordinator.settings.get("mode")) != MODE_MANUAL:
            await self.coordinator.async_set_pri_manual_level(-1)
            return
        try:
            level = int(option.replace("%", "").strip())
        except ValueError:
            return
        await self.coordinator.async_set_pri_manual_level(level)
