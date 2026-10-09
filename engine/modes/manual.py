from __future__ import annotations

from ...const import BOILER_NONE, MODE_MANUAL
from ..models import BoilerIntent, EnergySnapshot


def evaluate_manual(snapshot: EnergySnapshot, settings: dict[str, object]) -> BoilerIntent:
    return BoilerIntent(BOILER_NONE, "Mode Manuel : aucune stratégie automatique, sécurités thermiques actives.", MODE_MANUAL)
