from __future__ import annotations

import re
import json
from pathlib import Path

_VERSION_PATTERN = re.compile(r"^dashboard_v(\d+(?:\.\d+)+(?:-[a-z][a-z0-9-]*)?)\.yaml$")


def available_dashboard_versions(directory: Path) -> list[str]:
    versions = []
    for path in directory.glob("dashboard_v*.yaml"):
        match = _VERSION_PATTERN.fullmatch(path.name)
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


def dashboard_version_label(version: str, directory: Path) -> str:
    manifest = directory / f"manifest_v{version}.json"
    try:
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return version
    label = metadata.get("name")
    return label if isinstance(label, str) and label else version


def dashboard_version_for_label(label: str, directory: Path) -> str:
    for version in available_dashboard_versions(directory):
        if dashboard_version_label(version, directory) == label:
            return version
    return label


def recommended_dashboard_version(directory: Path) -> str | None:
    versions = available_dashboard_versions(directory)
    for version in versions:
        manifest = directory / f"manifest_v{version}.json"
        try:
            metadata = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if metadata.get("dashboard_version") == version and metadata.get("recommended") is True:
            return version
    return versions[0] if versions else None
