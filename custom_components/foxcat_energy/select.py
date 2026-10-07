from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    DYNAMIC_STRUCTURES,
    MODE_MANUAL,
    MODES,
    NETWORK_POLICIES,
    NETWORK_POLICY_COMPENSATION,
    PRICE_SOURCES,
    TARIFF_REGIMES,
    TARIFF_STRUCTURES,
)
from .coordinator import FoxCatEnergyCoordinator
from .entity import FoxCatEntity
from .select_options import (
    constrained_option,
    mode_option,
    network_policy_option,
    tariff_regime_option,
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: FoxCatEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FoxCatModeSelect(coordinator),
            FoxCatTariffRegimeSelect(coordinator),
            FoxCatDynamicStructureSelect(coordinator),
            FoxCatPriceSourceSelect(coordinator),
            FoxCatTariffStructureSelect(coordinator),
            FoxCatNetworkPolicySelect(coordinator),
            FoxCatPriManualLevelSelect(coordinator),
            FoxCatDashboardVersionSelect(coordinator),
        ]
    )


class FoxCatDescribedSelect:
    @property
    def extra_state_attributes(self) -> dict[str, dict[str, str]]:
        return {
            "options_descriptions": self.option_descriptions,
            "options_icons": self.option_icons,
        }


class FoxCatModeSelect(FoxCatDescribedSelect, FoxCatEntity, SelectEntity):
    _attr_options = MODES
    option_descriptions = {
        "Éco": "Priorité à l’autoconsommation et à l’optimisation automatique.",
        "Confort": "Privilégie le confort tout en conservant les sécurités EMS.",
        "Manuel": "Suspend les actions automatiques sur les charges.",
    }
    option_icons = {"Éco": "mdi:leaf", "Confort": "mdi:sofa", "Manuel": "mdi:hand"}

    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "mode_ems", "Mode EMS", "mdi:home-lightning-bolt", "ems")

    @property
    def current_option(self) -> str | None:
        return mode_option(self.coordinator.settings)

    async def async_select_option(self, option: str) -> None:
        if option not in MODES:
            return
        await self.coordinator.async_set_mode(option)


class FoxCatBaseSelect(FoxCatEntity, SelectEntity):
    def __init__(
        self,
        coordinator: FoxCatEnergyCoordinator,
        key: str,
        name: str,
        icon: str,
        setting_key: str,
        options: list[str],
    ) -> None:
        super().__init__(coordinator, key, name, icon, "pricing")
        self._setting_key = setting_key
        self._attr_options = options

    @property
    def current_option(self) -> str | None:
        value = self.coordinator.settings.get(self._setting_key)
        return str(value) if value in self._attr_options else None

    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            return
        await self.coordinator.async_set_setting(self._setting_key, option)
        self.async_write_ha_state()


class FoxCatPriceSourceSelect(FoxCatEntity, SelectEntity):
    _attr_options = PRICE_SOURCES

    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "source_prix", "Source du prix", "mdi:database-clock-outline", "pricing")

    @property
    def current_option(self) -> str:
        return constrained_option(self.coordinator.settings, "price_source", PRICE_SOURCES)

    async def async_select_option(self, option: str) -> None:
        if option in PRICE_SOURCES:
            await self.coordinator.async_set_setting("price_source", option)


class FoxCatTariffStructureSelect(FoxCatEntity, SelectEntity):
    _attr_options = TARIFF_STRUCTURES

    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "structure_tarifaire", "Structure tarifaire", "mdi:timeline-clock-outline", "pricing")

    @property
    def current_option(self) -> str:
        return constrained_option(self.coordinator.settings, "tariff_structure", TARIFF_STRUCTURES)

    async def async_select_option(self, option: str) -> None:
        if option in TARIFF_STRUCTURES:
            await self.coordinator.async_set_setting("tariff_structure", option)


class FoxCatTariffRegimeSelect(FoxCatDescribedSelect, FoxCatBaseSelect):
    option_descriptions = {
        "Mono-horaire": "Applique un prix fixe unique, sans plages HP/HC.",
        "Bi-horaire (HP/HC)": "Applique les prix et plages horaires heures pleines / heures creuses.",
        "Dynamique": "Utilise les prix variables disponibles dans Home Assistant.",
    }
    option_icons = {
        "Mono-horaire": "mdi:cash",
        "Bi-horaire (HP/HC)": "mdi:clock-time-eight-outline",
        "Dynamique": "mdi:chart-timeline-variant",
    }

    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(
            coordinator,
            "regime_tarifaire",
            "Régime Tarifaire",
            "mdi:file-document-outline",
            "tariff_regime",
            TARIFF_REGIMES,
        )

    @property
    def current_option(self) -> str | None:
        return tariff_regime_option(self.coordinator.settings)

    async def async_select_option(self, option: str) -> None:
        await super().async_select_option(option)


class FoxCatDynamicStructureSelect(FoxCatBaseSelect):
    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(
            coordinator,
            "structure_dynamique",
            "Structure (Si Dynamique)",
            "mdi:chart-bell-curve-cumulative",
            "dynamic_structure",
            DYNAMIC_STRUCTURES,
        )

class FoxCatNetworkPolicySelect(FoxCatDescribedSelect, FoxCatEntity, SelectEntity):
    _attr_options = NETWORK_POLICIES
    option_descriptions = {
        "Compensation": "Valorise le prélèvement et l’injection dans le bilan réseau.",
        "Injection tarifée": "L’injection est rémunérée au tarif configuré.",
        "Injection non valorisée": "L’injection est comptabilisée sans recette.",
        "Zéro injection": "Limite la production pour éviter la réinjection réseau.",
    }
    option_icons = {
        "Compensation": "mdi:swap-horizontal",
        "Injection tarifée": "mdi:cash-plus",
        "Injection non valorisée": "mdi:transmission-tower-export",
        "Zéro injection": "mdi:transmission-tower-off",
    }

    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "politique_reseau", "Politique réseau", "mdi:transmission-tower", "pricing")

    @property
    def current_option(self) -> str | None:
        return network_policy_option(self.coordinator.settings)

    async def async_select_option(self, option: str) -> None:
        if option not in NETWORK_POLICIES:
            return
        await self.coordinator.async_set_setting("network_policy", option)


class FoxCatDashboardVersionSelect(FoxCatEntity, SelectEntity):
    @property
    def options(self) -> list[str]:
        from .dashboard import dashboard_select_options

        return dashboard_select_options(self.coordinator.hass)

    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "dashboard_version", "Version du dashboard", "mdi:view-dashboard", "diagnostic")

    @property
    def current_option(self) -> str | None:
        from .dashboard import dashboard_status

        active = dashboard_status(self.coordinator.hass).get("active_version")
        return active if active in self.options else (self.options[0] if self.options else None)

    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            return
        from .dashboard import CUSTOM_DASHBOARD_OPTION, async_switch_dashboard

        if option == CUSTOM_DASHBOARD_OPTION:
            return

        try:
            await async_switch_dashboard(
                self.coordinator.hass,
                self.coordinator.entry,
                self.coordinator.config,
                option,
            )
        except ValueError as err:
            from homeassistant.components import persistent_notification

            persistent_notification.async_create(
                self.coordinator.hass,
                str(err),
                title="Dashboard FoxCat Energy",
            )
            return
        self.coordinator.async_set_updated_data(self.coordinator._build_data())


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
