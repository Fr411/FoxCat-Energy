from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml

from .hardware_catalog import (
    INVERTER_CATALOG,
    METER_CATALOG,
    models_for_inverter,
    models_for_meter,
)

_DEVICE_DIR = Path(__file__).parent / "devices"
_DEVICE_ID = re.compile(r"^[a-z][a-z0-9_]*$")
_CATEGORIES = {"inverter", "meter", "boiler", "machines"}
_TEMPLATE_FILES = ("inverter.yaml", "meter.yaml", "boiler.yaml", "machines.yaml")


@dataclass(frozen=True, slots=True)
class DeviceDefinition:
    device_id: str
    name: str
    category: str
    enabled_setting: str
    disable_strategy: str
    configuration: dict[str, Any]


def _validate_device(raw: Any, source: str) -> DeviceDefinition:
    if not isinstance(raw, dict):
        raise ValueError(f"{source}: la clé device doit contenir un objet YAML.")
    device_id = str(raw.get("id", ""))
    category = str(raw.get("category", ""))
    setting = str(raw.get("enabled_setting", ""))
    if not _DEVICE_ID.fullmatch(device_id):
        raise ValueError(f"{source}: identifiant d'appareil invalide.")
    if category not in _CATEGORIES:
        raise ValueError(f"{source}: catégorie d'appareil inconnue ({category}).")
    if setting != f"device_{device_id}_enabled":
        raise ValueError(f"{source}: enabled_setting doit être device_{device_id}_enabled.")

    brand = str(raw.get("brand") or "")
    model = str(raw.get("model") or "")
    if category == "inverter" and brand:
        if brand not in INVERTER_CATALOG or (model and model not in models_for_inverter(brand)):
            raise ValueError(f"{source}: marque ou modèle d'onduleur absent du catalogue.")
    if category == "meter" and brand:
        if brand not in METER_CATALOG or (model and model not in models_for_meter(brand)):
            raise ValueError(f"{source}: marque ou modèle de compteur absent du catalogue.")

    return DeviceDefinition(
        device_id=device_id,
        name=str(raw.get("name") or device_id),
        category=category,
        enabled_setting=setting,
        disable_strategy=str(raw.get("disable_strategy") or ""),
        configuration={key: value for key, value in raw.items() if key not in {"id", "name", "category", "enabled_setting", "disable_strategy"}},
    )


def load_device_templates() -> tuple[DeviceDefinition, ...]:
    definitions = []
    for filename in _TEMPLATE_FILES:
        path = _DEVICE_DIR / filename
        with path.open(encoding="utf-8") as template:
            raw = yaml.safe_load(template)
        if not isinstance(raw, dict) or set(raw) != {"device"}:
            raise ValueError(f"{path.name}: format de template invalide.")
        definitions.append(_validate_device(raw["device"], path.name))
    ids = [item.device_id for item in definitions]
    if len(ids) != len(set(ids)):
        raise ValueError("Les identifiants des templates d'appareils doivent être uniques.")
    return tuple(definitions)


def device_definitions() -> tuple[DeviceDefinition, ...]:
    return load_device_templates()


def apply_device_toggle(settings: dict[str, Any], device_id: str, enabled: bool) -> str | None:
    definition = next(
        (item for item in device_definitions() if item.device_id == device_id),
        None,
    )
    if definition is None:
        raise ValueError(f"Appareil FoxCat inconnu : {device_id}")
    enabled = bool(enabled)
    settings[definition.enabled_setting] = enabled
    if device_id == "inverter":
        settings["pri_enabled"] = enabled
        return "release_inverter" if not enabled else None
    if device_id == "meter" and not enabled:
        settings["regulation_active"] = False
        return "stop_regulation"
    if device_id == "boiler" and not enabled:
        return "stop_boiler"
    if device_id == "machines":
        return "reconcile_machines"
    return None
