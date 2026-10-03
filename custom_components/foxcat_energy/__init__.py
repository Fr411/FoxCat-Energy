from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS
from .coordinator import FoxCatEnergyCoordinator
from .dashboard import async_ensure_dashboard

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    coordinator = FoxCatEnergyCoordinator(hass, entry)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_initialize()

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

    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
