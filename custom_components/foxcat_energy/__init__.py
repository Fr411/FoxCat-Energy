from __future__ import annotations

import logging
from pathlib import Path

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_SETTINGS, DOMAIN, NUMBER_DEFINITIONS, PLATFORMS, SWITCH_DEFINITIONS, TIME_SETTING_KEYS
from .coordinator import FoxCatEnergyCoordinator
from .dashboard import async_ensure_dashboard
from .profiles import read_settings_profile, write_settings_profile

_LOGGER = logging.getLogger(__name__)

_PROFILE_SCHEMA = vol.Schema(
    {vol.Optional("name", default="default"): str}
)


def _profile_directory(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(DOMAIN, "profiles"))


def _profile_setting_keys(coordinator: FoxCatEnergyCoordinator) -> set[str]:
    return (
        set(DEFAULT_SETTINGS)
        | set(NUMBER_DEFINITIONS)
        | set(SWITCH_DEFINITIONS)
        | set(TIME_SETTING_KEYS)
        | {machine.setting_key for machine in coordinator.machines}
    )


def _coordinator(hass: HomeAssistant) -> FoxCatEnergyCoordinator:
    coordinators = hass.data.get(DOMAIN, {})
    if not coordinators:
        raise HomeAssistantError("FoxCat Energy n’est pas configuré.")
    return next(iter(coordinators.values()))


def _async_register_profile_services(hass: HomeAssistant) -> None:
    async def save_profile(call: ServiceCall) -> None:
        coordinator = _coordinator(hass)
        allowed = _profile_setting_keys(coordinator)
        settings = {key: value for key, value in coordinator.settings.items() if key in allowed}
        try:
            await hass.async_add_executor_job(
                write_settings_profile,
                _profile_directory(hass),
                call.data["name"],
                settings,
                allowed,
            )
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    async def load_profile(call: ServiceCall) -> None:
        coordinator = _coordinator(hass)
        try:
            values = await hass.async_add_executor_job(
                read_settings_profile,
                _profile_directory(hass),
                call.data["name"],
                _profile_setting_keys(coordinator),
            )
            await coordinator.async_apply_settings_profile(values)
        except ValueError as err:
            raise HomeAssistantError(str(err)) from err

    async def reset_settings(call: ServiceCall) -> None:
        coordinator = _coordinator(hass)
        defaults = dict(DEFAULT_SETTINGS)
        defaults.update(
            {machine.setting_key: machine.automatic_default for machine in coordinator.machines}
        )
        await coordinator.async_apply_settings_profile(defaults)

    services = (
        ("save_settings_profile", save_profile),
        ("load_settings_profile", load_profile),
        ("reset_settings", reset_settings),
    )
    for service, handler in services:
        if not hass.services.has_service(DOMAIN, service):
            hass.services.async_register(DOMAIN, service, handler, schema=_PROFILE_SCHEMA)


def _async_remove_profile_services(hass: HomeAssistant) -> None:
    for service in ("save_settings_profile", "load_settings_profile", "reset_settings"):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    coordinator = FoxCatEnergyCoordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_initialize()
    _async_register_profile_services(hass)

    # Les plateformes sont chargées avant la génération du dashboard afin que
    # le registre Home Assistant connaisse déjà les unique_id FoxCat.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Génère le dashboard officiel uniquement s'il n'existe pas encore.
    # Un dashboard déjà personnalisé n'est jamais écrasé au démarrage.
    try:
        created, dashboard_path = await async_ensure_dashboard(hass, entry, coordinator.config)
        if created:
            _LOGGER.info("Dashboard FoxCat Energy créé depuis le registre: %s", dashboard_path)
        else:
            _LOGGER.debug("Dashboard FoxCat Energy déjà présent: %s", dashboard_path)
    except (OSError, FileNotFoundError) as err:
        # Une erreur de dashboard ne doit jamais empêcher l'EMS de démarrer.
        _LOGGER.warning("Impossible de générer le dashboard FoxCat Energy: %s", err)

    entry.async_on_unload(
        entry.add_update_listener(_async_reload_entry)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry,
        PLATFORMS,
    )

    if unload_ok:
        coordinator: FoxCatEnergyCoordinator = hass.data[DOMAIN].pop(
            entry.entry_id
        )
        await coordinator.async_shutdown()
        if not hass.data[DOMAIN]:
            _async_remove_profile_services(hass)

    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
