"""Classement des entités FoxCat par appareil Home Assistant.

Module pur (aucun import Home Assistant) : le même découpage sert à la page
« Entrées de l'intégration » (les appareils) et au menu d'options.

Chaque plateforme déclare encore son ancien appareil (``ems``, ``energy``…) ;
:func:`resolve_device` le traduit vers le classement actuel, en tenant compte de
la clé de l'entité. Les ``unique_id`` et les ``entity_id`` ne changent pas :
seul le rattachement à un appareil évolue, donc le dashboard et les
automatisations existantes continuent de fonctionner.
"""
from __future__ import annotations

# Appareil central : tous les autres s'y rattachent (``via_device``).
HUB_DEVICE = "system"

# Ordre = ordre d'affichage souhaité (menu et documentation).
DEVICE_NAMES: dict[str, str] = {
    "sources": "FoxCat Energy – Mesures et sources",
    "pricing": "FoxCat Energy – Tarification",
    "pri": "FoxCat Energy – Onduleur",
    "boiler": "FoxCat Energy – Boiler",
    "heating": "FoxCat Energy – Chauffage",
    "machines": "FoxCat Energy – Machines",
    "battery_ev": "FoxCat Energy – Batterie et VE",
    "protection": "FoxCat Energy – Protection",
    "ai": "FoxCat Energy – Prévisions et IA",
    "system": "FoxCat Energy – Système",
}

# Ancien appareil -> appareil actuel.
LEGACY_TO_DEVICE: dict[str, str] = {
    "sources": "sources",
    "energy": "sources",
    "metronome": "sources",
    "pricing": "pricing",
    "accounting": "pricing",
    "pri": "pri",
    "inverter": "pri",
    "boiler": "boiler",
    "user_functions": "boiler",
    "machines": "machines",
    "battery_ev": "battery_ev",
    "ai": "ai",
    "solar": "ai",
    "ems": "system",
    "energy_bus": "system",
    "diagnostic": "system",
}

# Anciens appareils qui n'existent plus : à retirer une fois vidés.
OBSOLETE_DEVICES: tuple[str, ...] = tuple(
    sorted(key for key in LEGACY_TO_DEVICE if key not in DEVICE_NAMES)
)

_PROTECTION_PREFIXES = ("high_load_", "main_breaker_", "peak_")
_PROTECTION_KEYS = frozenset(
    {
        "intensite_reseau",
        "charge_disjoncteur_pct",
        "statut_delestage",
        "haute_consommation_active",
    }
)
# Limites d'import / réinjection qui pilotent le PRI : elles vont avec l'onduleur.
_PRI_PREFIXES = ("network_billed_",)


def resolve_device(key: str, legacy_device: str) -> str:
    """Retourne l'appareil actuel d'une entité (clé ``key``, ancien appareil ``legacy_device``)."""
    if key.startswith(("heating_", "chauffage_")):
        return "heating"
    if key.startswith(_PROTECTION_PREFIXES) or key in _PROTECTION_KEYS:
        return "protection"
    if key.startswith("impact_") and key.endswith("_adder_eur_kwh"):
        return "pricing"
    if key.startswith(_PRI_PREFIXES):
        return "pri"
    if key.startswith("machine_") and legacy_device == "user_functions":
        return "machines"
    if key == "analyser_solaire":
        return "ai"
    if "revenu" in key and legacy_device == "energy":
        return "pricing"
    return LEGACY_TO_DEVICE.get(legacy_device, "system")


def device_name(device: str) -> str:
    """Nom affiché de l'appareil."""
    return DEVICE_NAMES.get(device, "FoxCat Energy")
