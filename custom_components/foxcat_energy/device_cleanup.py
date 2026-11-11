"""Nettoyage des anciens appareils FoxCat devenus vides après le reclassement."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .devices_layout import OBSOLETE_DEVICES

_LOGGER = logging.getLogger(__name__)


# FONCTION : async_remove_obsolete_devices — Retire les anciens appareils FoxCat devenus vides
def async_remove_obsolete_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Retire les anciens appareils (EMS, Énergie, Energy Bus, IA en double…) une fois vidés.

    Les entités ont été rattachées au classement actuel ; seul un appareil qui ne
    porte plus aucune entité est supprimé, jamais un appareil encore utilisé.
    """
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    obsolete = {f"{entry.entry_id}:{key}" for key in OBSOLETE_DEVICES}
    for device in dr.async_entries_for_config_entry(devices, entry.entry_id):
        identifiers = {value for domain, value in device.identifiers if domain == DOMAIN}
        if not identifiers & obsolete:
            continue
        if er.async_entries_for_device(entities, device.id, include_disabled_entities=True):
            continue
        _LOGGER.info("Appareil FoxCat obsolète retiré : %s", device.name_by_user or device.name)
        devices.async_update_device(device.id, remove_config_entry_id=entry.entry_id)
