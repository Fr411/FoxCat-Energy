from __future__ import annotations

import json
import math
import re
from datetime import time
from pathlib import Path
from typing import Any, Iterable

from .const import (
    DEFAULT_SETTINGS,
    MODE_ALIASES,
    MODES,
    NETWORK_POLICIES,
    PRICE_SOURCE_DYNAMIC,
    PRICE_SOURCE_VARIABLE,
    PRICE_SOURCES,
    SWITCH_DEFINITIONS,
    TARIFF_REGIMES,
    TARIFF_DYNAMIC,
    TARIFF_SIMPLE,
    TARIFF_STRUCTURE_SIMPLE,
    TARIFF_STRUCTURE_TOU,
    TARIFF_TOU,
    TARIFF_STRUCTURES,
    TIME_SETTING_KEYS,
    NUMBER_DEFINITIONS,
)
from .migration import compatibility_tariff_regime

_PROFILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


def profile_path(directory: Path, name: str) -> Path:
    if not _PROFILE_NAME.fullmatch(name):
        raise ValueError("Nom de profil invalide : utiliser 1 à 64 lettres, chiffres, _ ou -.")
    return directory / f"{name}.json"


def validate_profile_settings(
    values: Any,
    allowed_keys: Iterable[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(values, dict):
        raise ValueError("Le profil doit contenir un objet settings.")
    allowed = set(allowed_keys or DEFAULT_SETTINGS) | set(NUMBER_DEFINITIONS) | set(SWITCH_DEFINITIONS) | set(TIME_SETTING_KEYS)
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"Paramètre(s) inconnu(s) : {', '.join(sorted(unknown))}.")

    validated = dict(values)
    for key, value in validated.items():
        if key in NUMBER_DEFINITIONS:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{key} doit être un nombre fini.")
            _, minimum, maximum, _, _, _ = NUMBER_DEFINITIONS[key]
            if not minimum <= value <= maximum:
                raise ValueError(f"{key} doit être compris entre {minimum} et {maximum}.")
        elif key in TIME_SETTING_KEYS:
            if not isinstance(value, str):
                raise ValueError(f"{key} doit être une heure au format HH:MM[:SS].")
            try:
                time.fromisoformat(value)
            except ValueError as err:
                raise ValueError(f"{key} doit être une heure au format HH:MM[:SS].") from err
        elif key in SWITCH_DEFINITIONS or key.startswith("device_") or key.endswith("_enabled"):
            if not isinstance(value, bool):
                raise ValueError(f"{key} doit être un booléen.")
        elif key == "mode":
            canonical = MODE_ALIASES.get(str(value), value)
            if canonical not in MODES:
                raise ValueError(f"Mode EMS non pris en charge : {value}.")
            validated[key] = canonical
        elif key == "network_policy" and value not in NETWORK_POLICIES:
            raise ValueError(f"Politique réseau non prise en charge : {value}.")
        elif key == "price_source" and value not in PRICE_SOURCES:
            raise ValueError(f"Source de prix non prise en charge : {value}.")
        elif key == "tariff_structure" and value not in TARIFF_STRUCTURES:
            raise ValueError(f"Structure tarifaire non prise en charge : {value}.")
        elif key == "tariff_regime" and value not in TARIFF_REGIMES:
            raise ValueError(f"Régime tarifaire non pris en charge : {value}.")
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            if not math.isfinite(value):
                raise ValueError(f"{key} doit être un nombre fini.")
        elif key in DEFAULT_SETTINGS and isinstance(DEFAULT_SETTINGS[key], bool) and not isinstance(value, bool):
            raise ValueError(f"{key} doit être un booléen.")
        elif key in DEFAULT_SETTINGS and isinstance(DEFAULT_SETTINGS[key], str) and not isinstance(value, str):
            raise ValueError(f"{key} doit être du texte.")

    if "tariff_regime" in validated:
        regime = validated["tariff_regime"]
        if regime == TARIFF_DYNAMIC:
            validated["price_source"] = PRICE_SOURCE_DYNAMIC
        elif regime in {TARIFF_TOU, TARIFF_SIMPLE}:
            if validated.get("price_source") == PRICE_SOURCE_DYNAMIC:
                validated["price_source"] = PRICE_SOURCE_VARIABLE
            validated["tariff_structure"] = (
                TARIFF_STRUCTURE_TOU if regime == TARIFF_TOU else TARIFF_STRUCTURE_SIMPLE
            )
    if {"tariff_regime", "price_source", "tariff_structure"} & set(validated):
        validated["tariff_regime"] = compatibility_tariff_regime(
            {**DEFAULT_SETTINGS, **validated}
        )
    return validated


def write_settings_profile(
    directory: Path,
    name: str,
    settings: dict[str, Any],
    allowed_keys: Iterable[str] | None = None,
) -> Path:
    path = profile_path(directory, name)
    validated = validate_profile_settings(settings, allowed_keys)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps({"settings": validated}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def read_settings_profile(
    directory: Path,
    name: str,
    allowed_keys: Iterable[str] | None = None,
) -> dict[str, Any]:
    path = profile_path(directory, name)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as err:
        raise ValueError(f"Profil introuvable : {name}.") from err
    except json.JSONDecodeError as err:
        raise ValueError("Le fichier du profil JSON est invalide.") from err
    return validate_profile_settings(payload.get("settings") if isinstance(payload, dict) else None, allowed_keys)
