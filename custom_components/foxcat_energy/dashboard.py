from __future__ import annotations

import hashlib
import json
import logging
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
    DashboardVariant,
    DASHBOARD_VARIANTS,
    available_dashboard_versions as _scan_dashboard_versions,
    dashboard_version_for_label as _scan_dashboard_version_for_label,
    dashboard_version_label as _scan_dashboard_version_label,
    recommended_dashboard_version as _scan_recommended_version,
    dashboard_template_path,
    dashboard_variant_files,
)
from .registry import render_dashboard_template, resolve_registry

_LOGGER = logging.getLogger(__name__)

DASHBOARD_FOLDER = "foxcat_energy"
DASHBOARD_FILENAME = "dashboard.yaml"
CUSTOM_DASHBOARD_OPTION = "Personnalisé"


# FONCTION : _dir — Dir
def _dir() -> Path:
    return Path(__file__).parent / "dashboard" / "versions"


# FONCTION : _target — Target
def _target(hass: HomeAssistant, variant: DashboardVariant = "tablet") -> Path:
    filename, _ = dashboard_variant_files(variant)
    return Path(hass.config.path(DASHBOARD_FOLDER, filename))


# FONCTION : _state — State
def _state(hass: HomeAssistant, variant: DashboardVariant = "tablet") -> Path:
    _, filename = dashboard_variant_files(variant)
    return Path(hass.config.path(DASHBOARD_FOLDER, filename))


# FONCTION : _user_dashboard — User dashboard
def _user_dashboard(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(DASHBOARD_FOLDER, "dashboard_user.yaml"))


# FONCTION : _user_dashboard_base — User dashboard base
def _user_dashboard_base(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(DASHBOARD_FOLDER, "dashboard_user_base.yaml"))


# FONCTION : _user_dashboard_state — User dashboard state
def _user_dashboard_state(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(DASHBOARD_FOLDER, "dashboard_user_state.json"))


# FONCTION : _read — Read
def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


# FONCTION : _write — Write
def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


# FONCTION : _write_text — Write text
def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


# FONCTION : available_dashboard_versions — Available dashboard versions
def available_dashboard_versions(variant: DashboardVariant = "tablet") -> list[str]:
    return _scan_dashboard_versions(_dir(), variant)


# FONCTION : recommended_dashboard_version — Recommended dashboard version
def recommended_dashboard_version(variant: DashboardVariant = "tablet") -> str | None:
    return _scan_recommended_version(_dir(), variant)


# FONCTION : dashboard_version_label — Dashboard version label
def dashboard_version_label(
    version: str, variant: DashboardVariant = "tablet"
) -> str:
    return _scan_dashboard_version_label(version, _dir(), variant)


# FONCTION : dashboard_version_for_label — Dashboard version for label
def dashboard_version_for_label(
    label: str, variant: DashboardVariant = "tablet"
) -> str:
    return _scan_dashboard_version_for_label(label, _dir(), variant)


# FONCTION : dashboard_select_options — Dashboard select options
def dashboard_select_options(
    hass: HomeAssistant | None = None, variant: DashboardVariant = "tablet"
) -> list[str]:
    versions = available_dashboard_versions(variant)
    if hass is not None and _dashboard_customized(hass, variant):
        versions.append(CUSTOM_DASHBOARD_OPTION)
    return versions


# FONCTION : _dashboard_customized — Dashboard customized
def _dashboard_customized(
    hass: HomeAssistant, variant: DashboardVariant = "tablet"
) -> bool:
    target = _target(hass, variant)
    if not target.exists():
        return False
    state = _read(_state(hass, variant))
    managed_hash = state.get("sha256")
    current_hash = hashlib.sha256(target.read_bytes()).hexdigest()
    return not managed_hash or managed_hash != current_hash


# FONCTION : dashboard_status — Dashboard status
def dashboard_status(
    hass: HomeAssistant, variant: DashboardVariant = "tablet"
) -> dict[str, Any]:
    state = _read(_state(hass, variant))
    target = _target(hass, variant)
    current_hash = hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
    managed_hash = state.get("sha256")
    customized = bool(target.exists() and (not managed_hash or managed_hash != current_hash))
    return {
        "engine_version": VERSION,
        "active_version": CUSTOM_DASHBOARD_OPTION if customized else state.get("active_version"),
        "previous_version": state.get("previous_version"),
        "available": available_dashboard_versions(variant),
        "sha256": current_hash,
        "customized": customized,
    }


# FONCTION : _render — Render
def _template_path(version: str, variant: DashboardVariant) -> Path:
    return dashboard_template_path(_dir(), version, variant)


def _render(
    hass: HomeAssistant,
    entry: ConfigEntry,
    config: dict[str, Any],
    version: str,
    variant: DashboardVariant = "tablet",
) -> str:
    source = _template_path(version, variant)
    if not source.is_file():
        raise ValueError(f"Version de dashboard inconnue : {version}")
    template = source.read_text(encoding="utf-8")
    return render_dashboard_template(template, resolve_registry(hass, entry, config))[0]


# FONCTION : _apply — Apply
def _apply(
    hass: HomeAssistant,
    entry: ConfigEntry,
    config: dict[str, Any],
    version: str,
    variant: DashboardVariant = "tablet",
) -> dict[str, Any]:
    if version not in available_dashboard_versions(variant):
        raise ValueError(f"Version de dashboard inconnue : {version}")

    target = _target(hass, variant)
    state_path = _state(hass, variant)
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
        rendered = _render(hass, entry, config, version, variant)
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
        return dashboard_status(hass, variant)
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


# FONCTION ASYNCHRONE : async_switch_dashboard — traitement asynchrone : switch dashboard
async def async_switch_dashboard(
    hass: HomeAssistant,
    entry: ConfigEntry,
    config: dict[str, Any],
    selection: str,
    variant: DashboardVariant = "tablet",
) -> dict[str, Any]:
    return await hass.async_add_executor_job(
        _apply, hass, entry, config, selection, variant
    )


# FONCTION ASYNCHRONE : async_ensure_dashboard — traitement asynchrone : ensure dashboard
async def async_ensure_dashboard(
    hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]
) -> tuple[bool, str]:
    """Preserve the legacy tablet result and independently attempt mobile setup."""
    tablet_error = None
    try:
        tablet_created = await _ensure_dashboard_variant(
            hass, entry, config, "tablet"
        )
    except (OSError, ValueError) as err:
        tablet_error = err
    try:
        await _ensure_dashboard_variant(hass, entry, config, "mobile")
    except (OSError, ValueError) as err:
        _LOGGER.warning("Impossible de générer le dashboard FoxCat mobile : %s", err)
    if tablet_error is not None:
        raise tablet_error
    return tablet_created, str(_target(hass))


async def _ensure_dashboard_variant(
    hass: HomeAssistant,
    entry: ConfigEntry,
    config: dict[str, Any],
    variant: DashboardVariant,
) -> bool:
    target = _target(hass, variant)
    if target.exists():
        return False
    options = dashboard_select_options(hass, variant)
    if not options:
        raise FileNotFoundError(
            f"Aucune version de dashboard {variant} n’est disponible."
        )
    recommended = recommended_dashboard_version(variant) or options[0]
    await async_switch_dashboard(hass, entry, config, recommended, variant)
    return True


async def async_ensure_dashboards(
    hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]
) -> list[str]:
    """Create each missing dashboard independently and return paths created."""
    created_paths: list[str] = []
    for variant in DASHBOARD_VARIANTS:
        try:
            if await _ensure_dashboard_variant(hass, entry, config, variant):
                created_paths.append(str(_target(hass, variant)))
        except (OSError, ValueError) as err:
            _LOGGER.warning(
                "Impossible de générer le dashboard FoxCat %s : %s",
                variant,
                err,
            )
    return created_paths


# FONCTION ASYNCHRONE : async_regenerate_dashboard — traitement asynchrone : regenerate dashboard
async def async_regenerate_dashboard(
    hass: HomeAssistant,
    entry: ConfigEntry,
    config: dict[str, Any],
    variant: DashboardVariant = "tablet",
) -> str:
    state = _read(_state(hass, variant))
    version = state.get("active_version")
    options = dashboard_select_options(hass, variant)
    if version not in options:
        version = recommended_dashboard_version(variant) or (options[0] if options else None)
    if version is None:
        raise FileNotFoundError("Aucune version de dashboard FoxCat n’est disponible.")
    await async_switch_dashboard(hass, entry, config, version, variant)
    return str(_target(hass, variant))


# FONCTION : _save_user_dashboard — Save user dashboard
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


# FONCTION : _apply_user_dashboard_to_latest — Apply user dashboard to latest
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


# FONCTION ASYNCHRONE : async_save_user_dashboard — traitement asynchrone : save user dashboard
async def async_save_user_dashboard(
    hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]
) -> str:
    return await hass.async_add_executor_job(
        _save_user_dashboard, hass, entry, config
    )


# FONCTION ASYNCHRONE : async_apply_user_dashboard_to_latest — traitement asynchrone : apply user dashboard to latest
async def async_apply_user_dashboard_to_latest(
    hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]
) -> dict[str, Any]:
    return await hass.async_add_executor_job(
        _apply_user_dashboard_to_latest, hass, entry, config
    )


# FONCTION ASYNCHRONE : async_restore_previous_dashboard — traitement asynchrone : restore previous dashboard
async def async_restore_previous_dashboard(
    hass: HomeAssistant,
    entry: ConfigEntry,
    config: dict[str, Any],
    variant: DashboardVariant = "tablet",
) -> dict[str, Any]:
    previous = _read(_state(hass, variant)).get("previous_version")
    options = dashboard_select_options(hass, variant)
    if previous not in options:
        raise ValueError("Aucune version précédente disponible à restaurer.")
    return await async_switch_dashboard(hass, entry, config, previous, variant)
