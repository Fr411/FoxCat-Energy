from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    DISTRIBUTION_PROFILE_BI,
    DISTRIBUTION_PROFILE_IMPACT,
    DISTRIBUTION_PROFILE_SIMPLE,
    DISTRIBUTION_PROFILES,
    DYNAMIC_STRUCTURES,
    MODE_MANUAL,
    MODES,
    NETWORK_POLICIES,
    NETWORK_POLICY_COMPENSATION,
    PRICE_SOURCE_CONTRACT,
    PRICE_SOURCE_DYNAMIC,
    PRICE_SOURCE_INTEGRATION,
    PRICE_SOURCE_VARIABLE,
    TARIFF_BI,
    TARIFF_DYNAMIC,
    TARIFF_REGIMES,
)
from .domain.loads.machine_mode import MACHINE_MODE_MANUAL, MACHINE_MODES, manual_since_key, manual_until
from .domain.tariff.tariff_model import distribution_profile, tariff_dimensions
from .runtime.coordinator import FoxCatEnergyCoordinator
from .entity import FoxCatEntity
from .select_options import (
    constrained_option,
    mode_option,
    network_policy_option,
    tariff_regime_option,
)


# FONCTION ASYNCHRONE : async_setup_entry — traitement asynchrone : setup entry
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: FoxCatEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            FoxCatModeSelect(coordinator),
            FoxCatTariffRegimeSelect(coordinator),
            FoxCatDistributionProfileSelect(coordinator),
            FoxCatDynamicStructureSelect(coordinator),
            FoxCatPriceSourceSelect(coordinator),
            FoxCatTariffStructureSelect(coordinator),
            FoxCatNetworkPolicySelect(coordinator),
            FoxCatPriManualLevelSelect(coordinator),
            FoxCatDashboardVersionSelect(coordinator),
            *[FoxCatMachineModeSelect(coordinator, machine) for machine in coordinator.controllable_machines],
        ]
    )


class FoxCatMachineModeSelect(FoxCatEntity, SelectEntity):
    """Mode d'une machine : Automatique (planificateur), Manuel (prise commandée à la main, 24 h) ou Arrêt."""

    _attr_options = list(MACHINE_MODES)

    # MÉTHODE : FoxCatMachineModeSelect.__init__ — méthode spéciale __init__
    def __init__(self, coordinator: FoxCatEnergyCoordinator, machine) -> None:
        self.machine = machine
        super().__init__(coordinator, f"machine_{machine.machine_id}_mode", f"Mode {machine.name}", "mdi:state-machine", "machines")

    # MÉTHODE : FoxCatMachineModeSelect.current_option — Mode courant
    @property
    def current_option(self) -> str:
        return self.coordinator.machine_mode(self.machine)

    # MÉTHODE : FoxCatMachineModeSelect.extra_state_attributes — Retour automatique prévu
    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        since = self.coordinator.settings.get(manual_since_key(self.machine.machine_id))
        return {"retour_automatique_le": manual_until(since) if self.current_option == MACHINE_MODE_MANUAL else None}

    # MÉTHODE : FoxCatMachineModeSelect.async_select_option — Choix du mode
    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_set_machine_mode(self.machine.machine_id, option)


class FoxCatDescribedSelect:
    # MÉTHODE : FoxCatDescribedSelect.extra_state_attributes — Extra state attributes
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

    # MÉTHODE : FoxCatModeSelect.__init__ — méthode spéciale __init__
    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "mode_ems", "Mode EMS", "mdi:home-lightning-bolt", "ems")

    # MÉTHODE : FoxCatModeSelect.current_option — Current option
    @property
    def current_option(self) -> str | None:
        return mode_option(self.coordinator.settings)

    # MÉTHODE : FoxCatModeSelect.async_select_option — traitement asynchrone : select option
    async def async_select_option(self, option: str) -> None:
        if option not in MODES:
            return
        await self.coordinator.async_set_mode(option)


class FoxCatBaseSelect(FoxCatEntity, SelectEntity):
    # MÉTHODE : FoxCatBaseSelect.__init__ — méthode spéciale __init__
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

    # MÉTHODE : FoxCatBaseSelect.current_option — Current option
    @property
    def current_option(self) -> str | None:
        value = self.coordinator.settings.get(self._setting_key)
        return str(value) if value in self._attr_options else None

    # MÉTHODE : FoxCatBaseSelect.async_select_option — traitement asynchrone : select option
    async def async_select_option(self, option: str) -> None:
        if option not in self._attr_options:
            return
        await self.coordinator.async_set_setting(self._setting_key, option)
        self.async_write_ha_state()


# Les listes de tarif reprennent exactement les choix de l'écran « Contrat et réseau » :
# deux axes indépendants, le contrat (source des prix) et la structure du réseau.
PRICE_SOURCE_CHOICES = [PRICE_SOURCE_CONTRACT, PRICE_SOURCE_VARIABLE, PRICE_SOURCE_DYNAMIC]
STRUCTURE_CHOICES = ["Simple", "Bi-horaire", "Impact"]
# Ancien nom conservé pour les imports existants.
DYNAMIC_STRUCTURE_CHOICES = STRUCTURE_CHOICES


class FoxCatPriceSourceSelect(FoxCatEntity, SelectEntity):
    """Contrat : même liste que l'écran « Contrat et réseau »."""

    # MÉTHODE : FoxCatPriceSourceSelect.__init__ — méthode spéciale __init__
    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "source_prix", "Source du prix", "mdi:database-clock-outline", "pricing")

    # MÉTHODE : FoxCatPriceSourceSelect.options — Options (« Intégration externe » seulement si déjà active)
    @property
    def options(self) -> list[str]:
        options = list(PRICE_SOURCE_CHOICES)
        if self.coordinator.settings.get("price_source") == PRICE_SOURCE_INTEGRATION:
            options.append(PRICE_SOURCE_INTEGRATION)
        return options

    # MÉTHODE : FoxCatPriceSourceSelect.current_option — Current option
    @property
    def current_option(self) -> str | None:
        value = self.coordinator.settings.get("price_source", PRICE_SOURCE_VARIABLE)
        return value if value in self.options else None

    # MÉTHODE : FoxCatPriceSourceSelect.async_select_option — traitement asynchrone : select option
    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            return
        await self.coordinator.async_set_setting("price_source", option)
        self.async_write_ha_state()


class FoxCatTariffStructureSelect(FoxCatEntity, SelectEntity):
    """Structure du réseau : mono, bi-horaire ou Impact, avec tous les contrats."""

    _attr_options = STRUCTURE_CHOICES

    # MÉTHODE : FoxCatTariffStructureSelect.__init__ — méthode spéciale __init__
    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "structure_tarifaire", "Structure tarifaire", "mdi:timeline-clock-outline", "pricing")

    # MÉTHODE : FoxCatTariffStructureSelect.current_option — Current option
    @property
    def current_option(self) -> str:
        structure = tariff_dimensions(self.coordinator.settings).structure
        return structure if structure in STRUCTURE_CHOICES else "Simple"

    # MÉTHODE : FoxCatTariffStructureSelect.async_select_option — traitement asynchrone : select option
    async def async_select_option(self, option: str) -> None:
        if option not in STRUCTURE_CHOICES:
            return
        await self.coordinator.async_set_setting("tariff_structure", option)
        self.async_write_ha_state()


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

    # MÉTHODE : FoxCatTariffRegimeSelect.__init__ — méthode spéciale __init__
    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(
            coordinator,
            "regime_tarifaire",
            "Régime Tarifaire",
            "mdi:file-document-outline",
            "tariff_regime",
            TARIFF_REGIMES,
        )

    # MÉTHODE : FoxCatTariffRegimeSelect.current_option — Current option
    @property
    def current_option(self) -> str | None:
        return tariff_regime_option(self.coordinator.settings)

    # MÉTHODE : FoxCatTariffRegimeSelect.async_select_option — traitement asynchrone : select option
    async def async_select_option(self, option: str) -> None:
        await super().async_select_option(option)


class FoxCatDistributionProfileSelect(FoxCatDescribedSelect, FoxCatBaseSelect):
    _attr_options = DISTRIBUTION_PROFILES
    option_descriptions = {
        DISTRIBUTION_PROFILE_SIMPLE: "Un tarif de distribution identique à toute heure.",
        DISTRIBUTION_PROFILE_BI: "Profil de comptage jour/nuit, indépendant du contrat d’énergie.",
        DISTRIBUTION_PROFILE_IMPACT: "Profil wallon PIC, MEDIUM et ECO selon les plages configurées.",
    }
    option_icons = {
        DISTRIBUTION_PROFILE_SIMPLE: "mdi:clock-outline",
        DISTRIBUTION_PROFILE_BI: "mdi:clock-time-eight-outline",
        DISTRIBUTION_PROFILE_IMPACT: "mdi:chart-sankey",
    }

    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(
            coordinator,
            "profil_distribution_belgique",
            "Profil distribution Belgique",
            "mdi:transmission-tower",
            "distribution_profile",
            DISTRIBUTION_PROFILES,
        )

    @property
    def current_option(self) -> str | None:
        return distribution_profile(self.coordinator.settings)


class FoxCatDynamicStructureSelect(FoxCatBaseSelect):
    # MÉTHODE : FoxCatDynamicStructureSelect.__init__ — méthode spéciale __init__
    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(
            coordinator,
            "structure_dynamique",
            "Structure (Si Dynamique)",
            "mdi:chart-bell-curve-cumulative",
            "dynamic_structure",
            list(DYNAMIC_STRUCTURES),
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

    # MÉTHODE : FoxCatNetworkPolicySelect.__init__ — méthode spéciale __init__
    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "politique_reseau", "Politique réseau", "mdi:transmission-tower", "pricing")

    # MÉTHODE : FoxCatNetworkPolicySelect.current_option — Current option
    @property
    def current_option(self) -> str | None:
        return network_policy_option(self.coordinator.settings)

    # MÉTHODE : FoxCatNetworkPolicySelect.async_select_option — traitement asynchrone : select option
    async def async_select_option(self, option: str) -> None:
        if option not in NETWORK_POLICIES:
            return
        await self.coordinator.async_set_setting("network_policy", option)


class FoxCatDashboardVersionSelect(FoxCatEntity, SelectEntity):
    # MÉTHODE : FoxCatDashboardVersionSelect.options — Options
    @property
    def options(self) -> list[str]:
        from .dashboard.dashboard import cached_dashboard_label, cached_dashboard_options

        return [cached_dashboard_label(option) for option in cached_dashboard_options()]

    # MÉTHODE : FoxCatDashboardVersionSelect.__init__ — méthode spéciale __init__
    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "dashboard_version", "Version du dashboard", "mdi:view-dashboard", "diagnostic")

    # MÉTHODE : FoxCatDashboardVersionSelect.current_option — Current option
    @property
    def current_option(self) -> str | None:
        from .dashboard.dashboard import cached_dashboard_label, cached_dashboard_status

        active = cached_dashboard_status().get("active_version")
        active = cached_dashboard_label(active) if active else active
        return active if active in self.options else (self.options[0] if self.options else None)

    # MÉTHODE : FoxCatDashboardVersionSelect.async_select_option — traitement asynchrone : select option
    async def async_select_option(self, option: str) -> None:
        if option not in self.options:
            return
        from .dashboard.dashboard import (
            CUSTOM_DASHBOARD_OPTION,
            async_switch_dashboard,
            dashboard_version_for_label,
            refresh_dashboard_cache,
        )

        if option == CUSTOM_DASHBOARD_OPTION:
            return

        try:
            await async_switch_dashboard(
                self.coordinator.hass,
                self.coordinator.entry,
                self.coordinator.config,
                dashboard_version_for_label(option),
            )
        except ValueError as err:
            from homeassistant.components import persistent_notification

            persistent_notification.async_create(
                self.coordinator.hass,
                str(err),
                title="Dashboard FoxCat Energy",
            )
            return
        await self.coordinator.hass.async_add_executor_job(refresh_dashboard_cache, self.coordinator.hass)
        self.coordinator.async_set_updated_data(self.coordinator._build_data())


class FoxCatPriManualLevelSelect(FoxCatEntity, SelectEntity):
    _attr_options = [f"{level} %" for level in range(0, 101, 10)]

    # MÉTHODE : FoxCatPriManualLevelSelect.__init__ — méthode spéciale __init__
    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "pri_niveau_manuel", "Niveau réduction puissance onduleur manuel", "mdi:tune-vertical", "pri")

    # MÉTHODE : FoxCatPriManualLevelSelect.current_option — Current option
    @property
    def current_option(self) -> str | None:
        level = self.coordinator._rrcr_level()
        return f"{level} %" if level in range(0, 101, 10) else None

    # MÉTHODE : FoxCatPriManualLevelSelect.async_select_option — traitement asynchrone : select option
    async def async_select_option(self, option: str) -> None:
        if str(self.coordinator.settings.get("mode")) != MODE_MANUAL:
            await self.coordinator.async_set_pri_manual_level(-1)
            return
        try:
            level = int(option.replace("%", "").strip())
        except ValueError:
            return
        await self.coordinator.async_set_pri_manual_level(level)
