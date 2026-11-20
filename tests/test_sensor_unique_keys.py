"""Garde statique : une clé de capteur ne doit être déclarée qu'une fois.

Home Assistant ignore (et journalise en ERROR) un capteur dont l'unique_id existe déjà.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

SENSOR_PY = Path(__file__).parents[1] / "custom_components" / "foxcat_energy" / "sensor.py"
DECLARATION = re.compile(r'^\s*FoxCat(?:Value|Numeric)Sensor\(c, "([a-z0-9_]+)"', re.MULTILINE)


def test_sensor_keys_are_unique() -> None:
    keys = DECLARATION.findall(SENSOR_PY.read_text(encoding="utf-8"))
    assert keys, "aucune déclaration de capteur trouvée"
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)
    assert not duplicates, f"clés de capteur en double : {duplicates}"
