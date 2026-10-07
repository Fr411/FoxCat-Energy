from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import VERSION
from .dashboard_merge import merge_dashboard_text
from .dashboard_versions import (
    available_dashboard_versions as _scan_dashboard_versions,
    dashboard_version_for_label as _scan_dashboard_version_for_label,
    dashboard_version_label as _scan_dashboard_version_label,
    recommended_dashboard_version as _scan_recommended_version,
)
from .registry import render_dashboard_template, resolve_registry

DASHBOARD_FOLDER = "foxcat_energy"
DASHBOARD_FILENAME = "dashboard.yaml"
CUSTOM_DASHBOARD_OPTION = "Personnalisé"


def _dir() -> Path:
    return Path(__file__).parent / "dashboard" / "versions"


def _target(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(DASHBOARD_FOLDER, DASHBOARD_FILENAME))


def _state(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(DASHBOARD_FOLDER, "dashboard_state.json"))


def _user_dashboard(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(DASHBOARD_FOLDER, "dashboard_user.yaml"))


def _user_dashboard_base(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(DASHBOARD_FOLDER, "dashboard_user_base.yaml"))


def _user_dashboard_state(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(DASHBOARD_FOLDER, "dashboard_user_state.json"))


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def available_dashboard_versions() -> list[str]:
    return _scan_dashboard_versions(_dir())


def recommended_dashboard_version() -> str | None:
    return _scan_recommended_version(_dir())


def dashboard_version_label(version: str) -> str:
    return _scan_dashboard_version_label(version, _dir())


def dashboard_version_for_label(label: str) -> str:
    return _scan_dashboard_version_for_label(label, _dir())


def dashboard_select_options(hass: HomeAssistant | None = None) -> list[str]:
    versions = available_dashboard_versions()
    if hass is not None and _dashboard_customized(hass):
        versions.append(CUSTOM_DASHBOARD_OPTION)
    return versions


def _dashboard_customized(hass: HomeAssistant) -> bool:
    target = _target(hass)
    if not target.exists():
        return False
    state = _read(_state(hass))
    managed_hash = state.get("sha256")
    current_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    return not managed_hash or managed_hash != current_hash


def dashboard_status(hass: HomeAssistant) -> dict[str, Any]:
    state = _read(_state(hass))
    target = _target(hass)
    current_hash = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
    managed_hash = state.get("sha256")
    customized = bool(target.exists() and (not managed_hash or managed_hash != current_hash))
    return {
        "engine_version": VERSION,
        "active_version": CUSTOM_DASHBOARD_OPTION if customized else state.get("active_version"),
        "previous_version": state.get("previous_version"),
        "available": available_dashboard_versions(),
        "sha256": current_hash,
        "customized": customized,
    }


def _render(hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any], version: str) -> str:
    source = _dir() / f"dashboard_v{version}.yaml"
    if not source.is_file():
        raise ValueError(f"Version de dashboard inconnue : {version}")
    template = source.read_text(encoding="utf-8")
    return render_dashboard_template(template, resolve_registry(hass, entry, config))[0]


def _apply(hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any], version: str) -> dict[str, Any]:
    if version not in available_dashboard_versions():
        raise ValueError(f"Version de dashboard inconnue : {version}")

    target = _target(hass)
    state_path = _state(hass)
    state = _read(state_path)
    old_content = target.read_bytes() if target.exists() else None
    old_state = state_path.read_bytes() if state_path.exists() else None
    current_hash = hashlib.sha256(old_content).hexdigest() if old_content is not None else None
    if old_content is not None and (not state.get("sha256") or state.get("sha256") != current_hash):
        raise ValueError("Le dashboard existant est personnalisé ; il ne sera pas remplacé.")

    backup = None
    if old_content is not None:
        backup = target.with_suffix(target.suffix + ".bak")
        shutil.copy2(target, backup)

    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        rendered = _render(hass, entry, config, version)
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(target)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        _write(
            state_path,
            {
                "active_version": version,
                "previous_version": state.get("active_version"),
                "backup": str(backup) if backup else None,
                "last_change": datetime.now(timezone.utc).isoformat(),
                "sha256": digest,
            },
        )
        return dashboard_status(hass)
    except Exception:
        if temporary.exists():
            temporary.unlink()
        if old_content is not None:
            target.write_bytes(old_content)
        elif target.exists():
            target.unlink()
        if old_state is not None:
            state_path.write_bytes(old_state)
        elif state_path.exists():
            state_path.unlink()
        raise


async def async_switch_dashboard(
    hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any], selection: str
) -> dict[str, Any]:
    return await hass.async_add_executor_job(_apply, hass, entry, config, selection)


async def async_ensure_dashboard(
    hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]
) -> tuple[bool, str]:
    target = _target(hass)
    if target.exists():
        return False, str(target)
    options = dashboard_select_options(hass)
    if not options:
        raise FileNotFoundError("Aucune version de dashboard FoxCat n’est disponible.")
    recommended = recommended_dashboard_version() or options[0]
    await async_switch_dashboard(hass, entry, config, recommended)
    return True, str(target)


async def async_regenerate_dashboard(
    hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]
) -> str:
    state = _read(_state(hass))
    version = state.get("active_version")
    options = dashboard_select_options(hass)
    if version not in options:
        version = recommended_dashboard_version() or (options[0] if options else None)
    if version is None:
        raise FileNotFoundError("Aucune version de dashboard FoxCat n’est disponible.")
    await async_switch_dashboard(hass, entry, config, version)
    return str(_target(hass))


def _save_user_dashboard(
    hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]
) -> str:
    target = _target(hass)
    if not target.is_file():
        raise ValueError("Aucun dashboard FoxCat n’est disponible à sauvegarder.")

    state = _read(_state(hass))
    version = state.get("active_version")
    if version not in available_dashboard_versions():
        raise ValueError(
            "La version de base du dashboard est inconnue ; sauvegardez d’abord "
            "une version FoxCat, puis personnalisez-la."
        )
    current = target.read_text(encoding="utf-8")
    if not _dashboard_customized(hass):
        raise ValueError("Aucune personnalisation du dashboard n’a été détectée.")

    base = _render(hass, entry, config, version)
    _write_text(_user_dashboard_base(hass), base)
    _write_text(_user_dashboard(hass), current)
    _write(
        _user_dashboard_state(hass),
        {
            "base_version": version,
            "base_sha256": hashlib.sha256(base.encode("utf-8")).hexdigest(),
            "user_sha256": hashlib.sha256(current.encode("utf-8")).hexdigest(),
            "saved_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return str(_user_dashboard(hass))


def _apply_user_dashboard_to_latest(
    hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]
) -> dict[str, Any]:
    saved_state = _read(_user_dashboard_state(hass))
    user_path = _user_dashboard(hass)
    base_path = _user_dashboard_base(hass)
    if not saved_state or not user_path.is_file() or not base_path.is_file():
        raise ValueError("Enregistrez d’abord votre dashboard personnalisé.")

    user_text = user_path.read_text(encoding="utf-8")
    base_text = base_path.read_text(encoding="utf-8")
    if hashlib.sha256(user_text.encode("utf-8")).hexdigest() != saved_state.get("user_sha256"):
        raise ValueError("La sauvegarde utilisateur est invalide ; enregistrez-la à nouveau.")
    if hashlib.sha256(base_text.encode("utf-8")).hexdigest() != saved_state.get("base_sha256"):
        raise ValueError("La base de fusion est invalide ; enregistrez à nouveau votre dashboard.")

    latest_version = recommended_dashboard_version()
    if latest_version is None:
        raise FileNotFoundError("Aucune version de dashboard FoxCat n’est disponible.")
    latest_text = _render(hass, entry, config, latest_version)
    merged = merge_dashboard_text(base_text, user_text, latest_text)
    try:
        parsed = yaml.safe_load(merged)
    except yaml.YAMLError as err:
        raise ValueError(
            "La fusion produirait un YAML invalide ; aucun changement n’a été appliqué."
        ) from err
    if not isinstance(parsed, dict):
        raise ValueError(
            "La fusion ne produit pas un dashboard YAML valide ; aucun changement n’a été appliqué."
        )

    target = _target(hass)
    state_path = _state(hass)
    state = _read(state_path)
    old_content = target.read_bytes() if target.exists() else None
    old_state = state_path.read_bytes() if state_path.exists() else None
    backup = target.with_suffix(target.suffix + ".bak") if old_content is not None else None
    if backup is not None:
        shutil.copy2(target, backup)
    try:
        _write_text(target, merged)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        _write(
            state_path,
            {
                "active_version": latest_version,
                "previous_version": state.get("active_version"),
                "backup": str(backup) if backup else None,
                "last_change": datetime.now(timezone.utc).isoformat(),
                "sha256": digest,
                "user_customizations_applied": True,
            },
        )
    except Exception:
        if old_content is not None:
            target.write_bytes(old_content)
        elif target.exists():
            target.unlink()
        if old_state is not None:
            state_path.write_bytes(old_state)
        elif state_path.exists():
            state_path.unlink()
        raise
    return dashboard_status(hass)


async def async_save_user_dashboard(
    hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]
) -> str:
    return await hass.async_add_executor_job(
        _save_user_dashboard, hass, entry, config
    )


async def async_apply_user_dashboard_to_latest(
    hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]
) -> dict[str, Any]:
    return await hass.async_add_executor_job(
        _apply_user_dashboard_to_latest, hass, entry, config
    )


async def async_restore_previous_dashboard(
    hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]
) -> dict[str, Any]:
    previous = _read(_state(hass)).get("previous_version")
    options = dashboard_select_options(hass)
    if previous not in options:
        raise ValueError("Aucune version précédente disponible à restaurer.")
    return await async_switch_dashboard(hass, entry, config, previous)
