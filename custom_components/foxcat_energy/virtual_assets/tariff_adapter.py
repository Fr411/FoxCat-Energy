"""Adaptateur tarifaire : s'appuie uniquement sur le moteur tarifaire FoxCat existant.

Aucun second moteur : le calendrier vient de ``engine.tariff`` (HP 07:00-11:00 et
17:00-22:00, HC le reste, identique tous les jours) et la conversion gros → final de
``tariff_model.final_client_price``. Un prix manquant n'est jamais inventé.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Iterable, Mapping

from ..economic_optimizer import PricePoint
from ..engine.tariff import tariff_period
from ..price_analyzer import analyze_price_curve
from ..tariff_model import final_client_price
from .models import DataQuality, VirtualAssetsError

_COMPONENT_KEYS = ("tariff_network_component_eur_kwh", "tariff_tax_component_eur_kwh",
                   "tariff_contract_component_eur_kwh")


class PriceRefused(VirtualAssetsError):
    """Prix absent, non final, ou d'un type inadapté à l'usage demandé."""


class PriceKind(str, Enum):
    FINAL_IMPORT = "final_import"
    FINAL_EXPORT = "final_export"
    WHOLESALE = "wholesale"
    UNKNOWN = "unknown"      # finalité non déclarée : refusé
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class PriceQuote:
    value: float | None
    kind: PriceKind
    at: datetime
    is_future: bool = False

    @property
    def quality(self) -> DataQuality:
        if self.value is None:
            return DataQuality.MISSING
        return DataQuality.ESTIMATED if self.is_future else DataQuality.MEASURED

    @property
    def usable(self) -> bool:
        """Utilisable pour planifier/comptabiliser : prix final connu uniquement."""
        return self.value is not None and self.kind in (PriceKind.FINAL_IMPORT,
                                                         PriceKind.FINAL_EXPORT)

    @property
    def usable_for_accounting(self) -> bool:
        """Les prix futurs servent à planifier, jamais à comptabiliser du réalisé."""
        return self.usable and not self.is_future


class TariffAdapter:
    def __init__(self, settings: Mapping[str, Any]) -> None:
        self._settings = dict(settings)

    # -- calendrier -------------------------------------------------------
    def period(self, at: datetime) -> str:
        """``HP`` ou ``HC`` selon le calendrier FoxCat (AIESH par défaut)."""
        return tariff_period(at, self._settings)

    # -- classification ---------------------------------------------------
    def classify(self, value: Any, at: datetime, now: datetime, *, direction: str = "import",
                 is_final: bool | None = None, is_wholesale: bool = False) -> PriceQuote:
        """Classe un prix. Une valeur absente ou non numérique donne un devis MISSING."""
        if direction not in ("import", "export"):
            raise VirtualAssetsError("direction doit être 'import' ou 'export'")
        future = at > now
        if value is None or isinstance(value, bool) or not isinstance(value, (int, float)) \
                or value != value or value in (float("inf"), float("-inf")):
            return PriceQuote(None, PriceKind.MISSING, at, future)
        if is_wholesale:
            return PriceQuote(float(value), PriceKind.WHOLESALE, at, future)
        if is_final is not True:
            return PriceQuote(float(value), PriceKind.UNKNOWN, at, future)
        kind = PriceKind.FINAL_IMPORT if direction == "import" else PriceKind.FINAL_EXPORT
        return PriceQuote(float(value), kind, at, future)

    def wholesale_to_final(self, quote: PriceQuote) -> PriceQuote:
        """Convertit un prix de gros via ``final_client_price`` ; refuse si composantes absentes."""
        if quote.kind is not PriceKind.WHOLESALE or quote.value is None:
            raise PriceRefused("seul un prix de gros peut être converti")
        if any(k not in self._settings for k in _COMPONENT_KEYS):
            raise PriceRefused("composantes tarifaires absentes : conversion refusée")
        settings = {**self._settings, "price_curve_is_final": False}
        return PriceQuote(final_client_price(quote.value, quote.at, settings),
                          PriceKind.FINAL_IMPORT, quote.at, quote.is_future)

    def require_final(self, quote: PriceQuote) -> float:
        if not quote.usable:
            raise PriceRefused(f"prix non final ou manquant ({quote.kind.value})")
        return float(quote.value)  # type: ignore[arg-type]

    # -- sources de prix --------------------------------------------------
    def fixed_import_quote(self, at: datetime, now: datetime,
                           prices: Mapping[str, float | None]) -> PriceQuote:
        """Prix contractuels finaux par période (``HP``/``HC``) ou ``ALL`` pour mono-horaire."""
        raw = prices.get("ALL") if "ALL" in prices else prices.get(self.period(at))
        return self.classify(raw, at, now, is_final=True)

    def curve_quote(self, at: datetime, now: datetime, points: Iterable[PricePoint], *,
                    direction: str = "import", is_final: bool | None = None,
                    is_wholesale: bool = False) -> PriceQuote:
        """Prix d'un point exact de la courbe ; aucune interpolation, aucun report."""
        match = next((p for p in points if p.at == at), None)
        quote = self.classify(None if match is None else match.price, at, now,
                              direction=direction, is_final=is_final, is_wholesale=is_wholesale)
        if quote.kind is PriceKind.WHOLESALE:
            return self.wholesale_to_final(quote)
        return quote

    def curve_summary(self, now: datetime, import_points: Iterable[PricePoint],
                      export_points: Iterable[PricePoint] = ()) -> dict[str, Any]:
        """Résumé via l'analyseur de prix existant."""
        return analyze_price_curve(now=now, import_points=import_points,
                                   export_points=export_points, settings=self._settings)


def make_slot(start: datetime, hours: float, load_kwh: float | None, pv_kwh: float | None,
              import_quote: PriceQuote, export_quote: PriceQuote | None = None, *,
              load_quality: DataQuality = DataQuality.MEASURED,
              pv_quality: DataQuality = DataQuality.MEASURED):
    """Construit un ``Slot`` : seuls les prix finaux validés sont retenus, sinon ``None``."""
    from .models import Slot

    imp = import_quote.value if import_quote.usable else None
    exp = export_quote.value if export_quote is not None and export_quote.usable else None
    quality = import_quote.quality if imp is not None else DataQuality.MISSING
    return Slot(start, hours, load_kwh, pv_kwh, imp, exp, load_quality, pv_quality, quality,
                import_quote.is_future)
