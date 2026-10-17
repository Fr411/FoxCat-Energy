from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

_VERSION_PATTERN = re.compile(r"^dashboard_v(\d+(?:\.\d+)+(?:-[a-z][a-z0-9-]*)?)\.yaml$")
_MOBILE_VERSION_PATTERN = re.compile(
    r"^dashboard_mobile_v(\d+(?:\.\d+)+(?:-[a-z][a-z0-9-]*)?)\.yaml$"
)
CURRENT_DASHBOARD_VERSION = "1.7.4"
DashboardVariant = Literal["tablet", "mobile"]
_VARIANT_FILES: dict[DashboardVariant, tuple[str, str]] = {
    "tablet": ("dashboard.yaml", "dashboard_state.json"),
    "mobile": ("dashboardmob1.yaml", "dashboard_state_mobile.json"),
}
DASHBOARD_VARIANTS = tuple(_VARIANT_FILES)
_VARIANT_SOURCES: dict[DashboardVariant, tuple[str, re.Pattern[str]]] = {
    "tablet": ("dashboard_v", _VERSION_PATTERN),
    "mobile": ("dashboard_mobile_v", _MOBILE_VERSION_PATTERN),
}


def dashboard_variant_files(variant: DashboardVariant) -> tuple[str, str]:
    try:
        return _VARIANT_FILES[variant]
    except KeyError as err:
        raise ValueError(f"Type de dashboard inconnu : {variant}") from err


def dashboard_template_path(
    directory: Path, version: str, variant: DashboardVariant = "tablet"
) -> Path:
    try:
        prefix, _ = _VARIANT_SOURCES[variant]
    except KeyError as err:
        raise ValueError(f"Type de dashboard inconnu : {variant}") from err
    source = directory / f"{prefix}{version}.yaml"
    if source.is_file():
        return source
    if variant == "tablet" and version == CURRENT_DASHBOARD_VERSION:
        return directory.parent / "dashboard.yaml"
    return source


# FONCTION : available_dashboard_versions — Available dashboard versions
def available_dashboard_versions(
    directory: Path, variant: DashboardVariant = "tablet"
) -> list[str]:
    try:
        prefix, pattern = _VARIANT_SOURCES[variant]
    except KeyError as err:
        raise ValueError(f"Type de dashboard inconnu : {variant}") from err
    versions = []
    for path in directory.glob(f"{prefix}*.yaml"):
        match = pattern.fullmatch(path.name)
        if match:
            versions.append(match.group(1))
    fallback = directory.parent / "dashboard.yaml" if variant == "tablet" else None
    if fallback is not None and fallback.is_file() and CURRENT_DASHBOARD_VERSION not in versions:
        versions.append(CURRENT_DASHBOARD_VERSION)
    return sorted(
        versions,
        key=lambda version: (
            tuple(int(part) for part in version.split("-")[0].split(".")),
            "-" not in version,
            version.partition("-")[2],
        ),
        reverse=True,
    )


# FONCTION : dashboard_version_label — Dashboard version label
def dashboard_version_label(
    version: str, directory: Path, variant: DashboardVariant = "tablet"
) -> str:
    dashboard_variant_files(variant)
    manifest_name = (
        f"manifest_mobile_v{version}.json"
        if variant == "mobile"
        else f"manifest_v{version}.json"
    )
    manifest = directory / manifest_name
    try:
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return version
    label = metadata.get("name")
    return label if isinstance(label, str) and label else version


# FONCTION : dashboard_version_for_label — Dashboard version for label
def dashboard_version_for_label(
    label: str, directory: Path, variant: DashboardVariant = "tablet"
) -> str:
    for version in available_dashboard_versions(directory, variant):
        if dashboard_version_label(version, directory, variant) == label:
            return version
    return label


# FONCTION : recommended_dashboard_version — Recommended dashboard version
def recommended_dashboard_version(
    directory: Path, variant: DashboardVariant = "tablet"
) -> str | None:
    versions = available_dashboard_versions(directory, variant)
    for version in versions:
        manifest_name = (
            f"manifest_mobile_v{version}.json"
            if variant == "mobile"
            else f"manifest_v{version}.json"
        )
        manifest = directory / manifest_name
        try:
            metadata = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if metadata.get("dashboard_version") == version and metadata.get("recommended") is True:
            return version
    return versions[0] if versions else None
