"""Coûts de réseau propres à l'installation (capacitaire, redevance prosumer).

Ils dépendent du gestionnaire de réseau et de la région, pas du fournisseur :
changer de contrat ne les modifie pas. Le comparateur les applique donc de la
même façon à tous les tarifs comparés, pour que l'écart reflète uniquement le
prix de l'énergie. Valeurs saisies par l'installateur, toujours modifiables.

Module pur : aucune dépendance à Home Assistant.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import CAPACITY_FLAT, CAPACITY_KINDS, CAPACITY_NONE, CAPACITY_PEAK, CapacityTerm

KEY_KIND = "grid_capacity_kind"
KEY_FLAT = "grid_capacity_eur_per_year"
KEY_PER_KW = "grid_capacity_eur_per_kw_year"
KEY_MIN_KW = "grid_capacity_min_kw"
KEY_PROSUMER = "grid_prosumer_eur_per_year"

# Valeurs moyennes du « Guide des Tarifs et Contrats d'Énergie en Belgique » (2026),
# proposées à l'installation et à remplacer par celles de la facture réelle.
REGION_GRID_COSTS: dict[str, dict[str, Any]] = {
    "flandre": {KEY_KIND: CAPACITY_PEAK, KEY_PER_KW: 55.0, KEY_MIN_KW: 2.5},
    "bruxelles": {KEY_KIND: CAPACITY_FLAT, KEY_FLAT: 47.0},
}


def _float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if result == result and result >= 0 else default


@dataclass(frozen=True, slots=True)
class GridCosts:
    """Coûts de réseau annuels de l'installation."""

    capacity: CapacityTerm = field(default_factory=CapacityTerm)
    prosumer_eur_per_year: float = 0.0

    @property
    def is_empty(self) -> bool:
        return self.capacity.kind == CAPACITY_NONE and self.prosumer_eur_per_year == 0.0

    @classmethod
    def from_settings(cls, settings: dict[str, Any]) -> "GridCosts":
        """Lecture tolérante des réglages : une valeur invalide vaut « aucun coût »."""
        kind = str(settings.get(KEY_KIND) or CAPACITY_NONE)
        if kind not in CAPACITY_KINDS:
            kind = CAPACITY_NONE
        return cls(
            capacity=CapacityTerm(
                kind=kind,
                eur_per_year=_float(settings.get(KEY_FLAT)),
                eur_per_kw_year=_float(settings.get(KEY_PER_KW)),
                min_kw=_float(settings.get(KEY_MIN_KW)),
            ),
            prosumer_eur_per_year=_float(settings.get(KEY_PROSUMER)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "capacitaire": self.capacity.to_dict(),
            "prosumer_eur_par_an": self.prosumer_eur_per_year,
        }


def region_settings(region: str | None) -> dict[str, Any]:
    """Réglages de départ d'une région (vide si la région n'a pas de capacitaire)."""
    return dict(REGION_GRID_COSTS.get(str(region or ""), {}))
