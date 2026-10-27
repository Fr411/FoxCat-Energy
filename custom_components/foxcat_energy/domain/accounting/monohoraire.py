"""Contrôles de cohérence pour un contrat mono-horaire (audit seulement)."""
from __future__ import annotations
from typing import Any
from ._validation import horizon_check, result

class MonohoraireAccounting:
    """Valide les compteurs mono-horaires sans modifier le ledger."""
    REGIME = "Mono-horaire"
    HORIZONS = ("today", "month", "year", "lifetime")

    def validate(self, accounting_view: dict[str, Any]) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        for horizon in self.HORIZONS:
            e, w = horizon_check(accounting_view, horizon)
            errors.extend(e); warnings.extend(w)
        warnings.append("Le ledger historique range le mono-horaire dans 'tariff.other'; aucune donnée n'est reclassée rétroactivement.")
        return result(self.REGIME, errors, warnings)
