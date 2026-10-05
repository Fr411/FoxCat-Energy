from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN, MODE_ECO, MODE_MANUAL, MODES, TARIFF_REGIMES, NETWORK_POLICIES,
    NETWORK_POLICY_BILLED_EXPORT, DISTRIBUTION_PROFILES, DISTRIBUTION_WALLONIA_TOU,
)
from .coordinator import FoxCatEnergyCoordinator
from .entity import FoxCatEntity


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: FoxCatEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FoxCatModeSelect(coordinator),
            FoxCatTariffRegimeSelect(coordinator),
            FoxCatNetworkPolicySelect(coordinator),
            FoxCatDistributionProfileSelect(coordinator),
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
        return value if value in MODES else MODE_ECO

    async def async_select_option(self, option: str) -> None:
        if option not in MODES:
            return
        await self.coordinator.async_set_mode(option)


class FoxCatTariffRegimeSelect(FoxCatEntity, SelectEntity):
    _attr_options = TARIFF_REGIMES

    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "regime_tarifaire", "Contrat énergie", "mdi:cash-sync", "pricing")

    @property
    def current_option(self) -> str | None:
        value = str(self.coordinator.settings.get("tariff_regime"))
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
        value = str(self.coordinator.settings.get("network_policy", NETWORK_POLICY_BILLED_EXPORT))
        return value if value in NETWORK_POLICIES else NETWORK_POLICY_BILLED_EXPORT

    async def async_select_option(self, option: str) -> None:
        if option not in NETWORK_POLICIES:
            return
        await self.coordinator.async_set_setting("network_policy", option)


class FoxCatDistributionProfileSelect(FoxCatEntity, SelectEntity):
    _attr_options = DISTRIBUTION_PROFILES

    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "profil_distribution", "Profil distribution Belgique", "mdi:transmission-tower-export", "pricing")

    @property
    def current_option(self) -> str | None:
        value = str(self.coordinator.settings.get("distribution_profile", DISTRIBUTION_WALLONIA_TOU))
        return value if value in DISTRIBUTION_PROFILES else DISTRIBUTION_WALLONIA_TOU

    async def async_select_option(self, option: str) -> None:
        if option not in DISTRIBUTION_PROFILES:
            return
        await self.coordinator.async_set_setting("distribution_profile", option)


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
