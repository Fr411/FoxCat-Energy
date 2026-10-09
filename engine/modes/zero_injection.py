from __future__ import annotations

from ...const import BOILER_NONE, MODE_ZERO
from ..models import BoilerIntent, EnergySnapshot


def evaluate_zero_injection(snapshot: EnergySnapshot, settings: dict[str, object]) -> BoilerIntent:
    return BoilerIntent(BOILER_NONE, "Zéro injection : aucune stratégie boiler automatique, PRI prioritaire.", MODE_ZERO)
