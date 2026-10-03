from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .registry import render_dashboard_template, resolve_registry

DASHBOARD_FOLDER = "foxcat_energy"
DASHBOARD_FILENAME = "dashboard.yaml"


def _source_path() -> Path:
    return Path(__file__).parent / "dashboard" / DASHBOARD_FILENAME


def _target_path(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(DASHBOARD_FOLDER, DASHBOARD_FILENAME))


def _write_dashboard_content(content: str, target: Path, make_backup: bool) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)

    if make_backup and target.exists():
        backup = target.with_suffix(target.suffix + ".bak")
        shutil.copy2(target, backup)

    # Écriture atomique : on ne laisse jamais un dashboard partiellement écrit.
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(target)
    return str(target)


def _render_dashboard(
    hass: HomeAssistant,
    entry: ConfigEntry,
    config: dict[str, Any],
) -> tuple[str, list[str]]:
    source = _source_path()
    if not source.exists():
        raise FileNotFoundError(f"Dashboard FoxCat introuvable: {source}")
    template = source.read_text(encoding="utf-8")
    entity_map = resolve_registry(hass, entry, config)
    return render_dashboard_template(template, entity_map)


async def async_ensure_dashboard(
    hass: HomeAssistant,
    entry: ConfigEntry,
    config: dict[str, Any],
) -> tuple[bool, str]:
    """Create the official dashboard only when none exists.

    Existing user customisations are never overwritten at startup. The V1.6
    template itself is registry-based and is resolved only when written.
    """
    target = _target_path(hass)
    if target.exists():
        return False, str(target)

    content, _unresolved = _render_dashboard(hass, entry, config)
    path = await hass.async_add_executor_job(
        _write_dashboard_content,
        content,
        target,
        False,
    )
    return True, path


async def async_regenerate_dashboard(
    hass: HomeAssistant,
    entry: ConfigEntry,
    config: dict[str, Any],
) -> str:
    """Regenerate the dashboard from the registry-based embedded template.

    A dashboard.yaml.bak backup is made first. Native FoxCat entities are
    resolved from Home Assistant's entity registry by unique_id, not by their
    current object_id.
    """
    content, _unresolved = _render_dashboard(hass, entry, config)
    return await hass.async_add_executor_job(
        _write_dashboard_content,
        content,
        _target_path(hass),
        True,
    )
