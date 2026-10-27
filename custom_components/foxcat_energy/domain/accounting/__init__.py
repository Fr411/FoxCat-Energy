"""API publique de la comptabilité FoxCat Energy.

Le manager historique reste l'unique ledger d'écriture afin de préserver le
format persisté, les rollover et les intégrations existantes. Les modules
spécialisés effectuent des contrôles en lecture seule et n'ajoutent aucun kWh
ni montant financier.
"""
from __future__ import annotations
from typing import Any

from .manager import EnergyAccounting as _LegacyEnergyAccounting
from .bihoraire import BihoraireAccounting
from .dynamic import DynamicAccounting
from .monohoraire import MonohoraireAccounting

REGIME_MONO = "Mono-horaire"
REGIME_BI_ALIASES = {"Bi-horaire HP/HC", "Bi-horaire (HP/HC)", "Bi-horaire", "HP/HC"}
REGIME_DYNAMIC = "Dynamique"

class EnergyAccounting(_LegacyEnergyAccounting):
    """Façade compatible avec l'API existante + validation par régime.

    process(), restore(), dump() et les attributs du ledger conservent le
    comportement du manager historique. Seule la sortie view() gagne un champ
    additif `accounting_checks`.
    """
    def __init__(self) -> None:
        super().__init__()
        self._active_regime = "AUTRE"
        self._last_checks: dict[str, Any] = {
            "status": "not_checked", "regime": self._active_regime,
            "errors": [], "warnings": [],
        }
        self._mono = MonohoraireAccounting()
        self._bi = BihoraireAccounting()
        self._dynamic = DynamicAccounting()

    def restore(self, raw: Any) -> None:
        super().restore(raw)
        self._last_checks = {
            "status": "not_checked", "regime": self._active_regime,
            "errors": [], "warnings": ["Données restaurées; validation au prochain cycle de comptabilité."],
        }

    def process(self, snapshot: Any, prices: dict[str, Any], appliances: list[dict[str, Any]]) -> bool:
        # Le ledger reste maître : les validateurs n'interviennent jamais dans
        # le calcul des kWh, des coûts, du rollover ou de la persistance.
        self._active_regime = str(prices.get("regime") or "AUTRE")
        normalized_prices = dict(prices)
        # Le régime public actuel est "Bi-horaire (HP/HC)", alors que le
        # manager historique reconnaissait "Bi-horaire HP/HC" uniquement.
        # Normalisation locale avant appel : la ventilation future HP/HC est
        # corrigée sans réécrire les données déjà persistées.
        if self._active_regime in REGIME_BI_ALIASES:
            normalized_prices["regime"] = "Bi-horaire HP/HC"
        save_requested = super().process(snapshot, normalized_prices, appliances)
        ledger_view = super().view()
        if self._active_regime in REGIME_BI_ALIASES:
            self._last_checks = self._bi.validate(ledger_view)
        elif self._active_regime == REGIME_DYNAMIC:
            self._last_checks = self._dynamic.validate(ledger_view)
        elif self._active_regime in {REGIME_MONO, "Monohoraire", "Mono horaire", "Fixe / Monohoraire"}:
            self._last_checks = self._mono.validate(ledger_view)
        else:
            self._last_checks = {
                "status": "not_applicable", "regime": self._active_regime,
                "errors": [], "warnings": ["Régime non reconnu par les validateurs spécialisés; ledger historique conservé."],
            }
        return save_requested

    def view(self) -> dict[str, Any]:
        result = super().view()
        result["accounting_checks"] = dict(self._last_checks)
        return result

__all__ = ["EnergyAccounting"]
