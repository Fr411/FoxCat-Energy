from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

_VERSION_SUFFIX = r"(\d+(?:\.\d+)+(?:-[a-z][a-z0-9-]*)?)\.yaml$"
DashboardVariant = Literal["tablet", "mobile"]
_VARIANT_FILES: dict[DashboardVariant, tuple[str, str]] = {
    "tablet": ("dashboard.yaml", "dashboard_state.json"),
    "mobile": ("dashboardmob1.yaml", "dashboard_state_mobile.json"),
}
DASHBOARD_VARIANTS: tuple[DashboardVariant, ...] = tuple(_VARIANT_FILES)
_VARIANT_SOURCES: dict[
    DashboardVariant, tuple[str, re.Pattern[str], str]
] = {
    "tablet": ("dashboard_v", re.compile(r"^dashboard_v" + _VERSION_SUFFIX), "manifest_v"),
    "mobile": (
        "dashboard_mobile_v",
        re.compile(r"^dashboard_mobile_v" + _VERSION_SUFFIX),
        "manifest_mobile_v",
    ),
}


def _variant_source(variant: DashboardVariant) -> tuple[str, re.Pattern[str], str]:
    try:
        return _VARIANT_SOURCES[variant]
    except KeyError as err:
        raise ValueError(f"Type de dashboard inconnu : {variant}") from err


def dashboard_variant_files(variant: DashboardVariant) -> tuple[str, str]:
    try:
        return _VARIANT_FILES[variant]
    except KeyError as err:
        raise ValueError(f"Type de dashboard inconnu : {variant}") from err


def dashboard_template_path(
    directory: Path, version: str, variant: DashboardVariant = "tablet"
) -> Path:
    prefix, _, _ = _variant_source(variant)
    source = directory / f"{prefix}{version}.yaml"
    return source


def dashboard_manifest_path(
    directory: Path, version: str, variant: DashboardVariant
) -> Path:
    manifest_prefix = _variant_source(variant)[2]
    return directory / f"{manifest_prefix}{version}.json"


# FONCTION : available_dashboard_versions — Available dashboard versions
def available_dashboard_versions(
    directory: Path, variant: DashboardVariant = "tablet"
) -> list[str]:
    prefix, pattern, _ = _variant_source(variant)
    versions = []
    for path in directory.glob(f"{prefix}*.yaml"):
        match = pattern.fullmatch(path.name)
        if match:
            versions.append(match.group(1))
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
    manifest = dashboard_manifest_path(directory, version, variant)
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
    _variant_source(variant)
    versions = available_dashboard_versions(directory, variant)
    for version in versions:
        manifest = dashboard_manifest_path(directory, version, variant)
        try:
            metadata = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if metadata.get("dashboard_version") == version and metadata.get("recommended") is True:
            return version
    return versions[0] if versions else None
