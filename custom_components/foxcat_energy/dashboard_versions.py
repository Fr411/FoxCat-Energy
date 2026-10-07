from __future__ import annotations

import re
import json
from pathlib import Path

_VERSION_PATTERN = re.compile(r"^dashboard_v(\d+(?:\.\d+)+)\.yaml$")


def available_dashboard_versions(directory: Path) -> list[str]:
    versions = []
    for path in directory.glob("dashboard_v*.yaml"):
        match = _VERSION_PATTERN.fullmatch(path.name)
        if match:
            versions.append(match.group(1))
    return sorted(versions, key=lambda version: tuple(int(part) for part in version.split(".")), reverse=True)


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
