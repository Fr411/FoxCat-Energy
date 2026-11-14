"""Systèmes de chauffage (pompes à chaleur) : modèle de données et validation.

Aucun import Home Assistant : tout est testable unitairement.

Un système = un groupe extérieur de pompe à chaleur, avec :
- un capteur de puissance (obligatoire) ;
- un capteur de tension (optionnel) ;
- la phase du réseau sur laquelle il est raccordé (optionnelle) ;
- uniquement pour une PAC air/air : de 0 à 5 unités intérieures (``climate.*``).
  Les PAC eau/eau et air/eau n'ont pas d'unités intérieures à lier.
"""
from __future__ import annotations

from typing import Any, Iterable

# Clé de stockage dans les options de l'entrée de configuration.
CONF_HEATING_SYSTEMS = "heating_systems_v1"

TYPE_AIR_AIR = "air_air"
TYPE_WATER_WATER = "water_water"
TYPE_AIR_WATER = "air_water"
SYSTEM_TYPES = (TYPE_AIR_AIR, TYPE_WATER_WATER, TYPE_AIR_WATER)
SYSTEM_TYPE_LABELS = {
    TYPE_AIR_AIR: "Pompe à chaleur air/air",
    TYPE_WATER_WATER: "Pompe à chaleur eau/eau",
    TYPE_AIR_WATER: "Pompe à chaleur air/eau",
}

PHASES = ("L1", "L2", "L3")
# Un groupe air/air peut desservir au plus ce nombre d'unités intérieures.
MAX_INDOOR_UNITS = 5

ERR_INVALID = "invalid_heating_system"
ERR_TOO_MANY_UNITS = "heating_too_many_indoor_units"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def indoor_units_from(value: Any) -> list[str]:
    """Liste d'identifiants ``climate.*`` sans vides ni doublons, ordre conservé."""
    if value is None:
        return []
    items: Iterable[Any] = [value] if isinstance(value, str) else value
    seen: list[str] = []
    for item in items:
        entity_id = _text(item)
        if entity_id and entity_id not in seen:
            seen.append(entity_id)
    return seen


def normalise_system(user_input: dict[str, Any], system_id: str) -> tuple[dict[str, Any] | None, str | None]:
    """Valide une saisie et retourne ``(enregistrement, None)`` ou ``(None, code_erreur)``."""
    name = _text(user_input.get("name"))
    system_type = _text(user_input.get("system_type")).lower()
    power_sensor = _text(user_input.get("power_sensor"))
    if not name or system_type not in SYSTEM_TYPES or not power_sensor:
        return None, ERR_INVALID

    phase = _text(user_input.get("phase")).upper()
    if phase not in PHASES:
        phase = ""

    units: list[str] = []
    if system_type == TYPE_AIR_AIR:
        units = indoor_units_from(user_input.get("indoor_units"))
        if len(units) > MAX_INDOOR_UNITS:
            return None, ERR_TOO_MANY_UNITS

    return {
        "id": system_id,
        "name": name,
        "system_type": system_type,
        "power_sensor": power_sensor,
        "voltage_sensor": _text(user_input.get("voltage_sensor")),
        "phase": phase,
        "indoor_units": units,
    }, None


def records_from(options: dict[str, Any]) -> list[dict[str, Any]]:
    """Enregistrements valides stockés dans les options (les autres sont ignorés)."""
    raw = options.get(CONF_HEATING_SYSTEMS)
    if not isinstance(raw, list):
        return []
    records: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict) or not _text(item.get("id")):
            continue
        record, _error = normalise_system(item, _text(item.get("id")))
        if record is not None:
            records.append(record)
    return records


def summary(record: dict[str, Any]) -> str:
    """Libellé court pour les menus : « Salon — PAC air/air (3 unités) »."""
    label = SYSTEM_TYPE_LABELS.get(record.get("system_type"), "PAC")
    units = len(record.get("indoor_units") or [])
    extra = f" ({units} unité{'s' if units > 1 else ''})" if record.get("system_type") == TYPE_AIR_AIR and units else ""
    return f"{record.get('name')} — {label}{extra}"
