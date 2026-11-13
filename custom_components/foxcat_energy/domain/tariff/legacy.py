"""Pont entre les réglages historiques de FoxCat et le modèle de tarif.

* ``observed_tariff`` : le tarif réellement appliqué par FoxCat, valorisé avec
  les prix lus à chaque créneau (déjà finaux, compléments réseau inclus).
* ``tariff_from_settings`` : le contrat décrit par les anciens réglages
  (prix fixes HP/HC, plages, compléments), utile pour le comparer aux autres.
"""
from __future__ import annotations

from typing import Any

from ...const import (
    PRICE_SOURCE_CONTRACT,
    TARIFF_STRUCTURE_IMPACT,
    TARIFF_STRUCTURE_TOU,
)
from .models import (
    ENERGY_FIXED,
    ENERGY_OBSERVED,
    ENERGY_PERIODS,
    INJECTION_FIXED,
    INJECTION_OBSERVED,
    Period,
    Tariff,
)
from .templates import DEFAULT_HC_EUR_KWH, DEFAULT_HP_EUR_KWH, DEFAULT_SIMPLE_EUR_KWH

ACTIVE_TARIFF_ID = "active"
CONTRACT_TARIFF_ID = "contract"


def _float(value: Any, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if result == result else default


def _hhmm(value: Any, default: str) -> str:
    raw = str(value or default)
    return ":".join(raw.split(":")[:2])


def observed_tariff() -> Tariff:
    """Tarif réellement appliqué : les prix lus par FoxCat font foi."""
    return Tariff(
        id=ACTIVE_TARIFF_ID, name="Tarif actuel (prix lus)",
        energy_kind=ENERGY_OBSERVED, all_in=True,
        injection_kind=INJECTION_OBSERVED,
        note="Prix d'achat et de réinjection tels que FoxCat les a appliqués à chaque créneau.",
    )


def tariff_from_settings(settings: dict[str, Any]) -> Tariff | None:
    """Reconstruit le contrat à prix saisis, ou ``None`` si les prix viennent d'entités.

    Seule la source « contractuelle / fixe » décrit un contrat complet. Avec des
    prix lus depuis des entités, ``observed_tariff`` est la bonne représentation.
    """
    if settings.get("price_source") != PRICE_SOURCE_CONTRACT:
        return None
    injection = _float(settings.get("tariff_fixed_injection_eur_kwh"), 0.0)
    injection_kind = INJECTION_FIXED if injection else "none"
    structure = settings.get("tariff_structure")

    if structure == TARIFF_STRUCTURE_TOU:
        hp = _float(settings.get("tariff_hp_price_eur_kwh"), DEFAULT_HP_EUR_KWH)
        hc = _float(settings.get("tariff_hc_price_eur_kwh"), DEFAULT_HC_EUR_KWH)
        hp_adder = _float(settings.get("tariff_tou_hp_adder_eur_kwh"), 0.0)
        windows = (
            ("HP 1", _hhmm(settings.get("tariff_hp_start_1"), "07:00"),
             _hhmm(settings.get("tariff_hp_end_1"), "11:00")),
            ("HP 2", _hhmm(settings.get("tariff_hp_start_2"), "17:00"),
             _hhmm(settings.get("tariff_hp_end_2"), "22:00")),
        )
        return Tariff(
            id=CONTRACT_TARIFF_ID, name="Contrat saisi (HP/HC)",
            energy_kind=ENERGY_PERIODS, energy_price=hc,
            energy_periods=tuple(Period(n, s, e, hp) for n, s, e in windows),
            network_periods=tuple(Period(n, s, e, hp_adder) for n, s, e in windows),
            network_default=_float(settings.get("tariff_tou_hc_adder_eur_kwh"), 0.0),
            injection_kind=injection_kind, injection_price=injection,
        ).validate()

    price = _float(settings.get("tariff_simple_fixed_price_eur_kwh"), DEFAULT_SIMPLE_EUR_KWH)
    network: tuple[Period, ...] = ()
    if structure == TARIFF_STRUCTURE_IMPACT:
        network = (
            Period("ECO nuit", _hhmm(settings.get("impact_eco_start_1"), "01:00"),
                   _hhmm(settings.get("impact_eco_end_1"), "07:00"),
                   _float(settings.get("impact_eco_adder_eur_kwh"), 0.0)),
            Period("ECO jour", _hhmm(settings.get("impact_eco_start_2"), "11:00"),
                   _hhmm(settings.get("impact_eco_end_2"), "17:00"),
                   _float(settings.get("impact_eco_adder_eur_kwh"), 0.0)),
            Period("PIC", _hhmm(settings.get("impact_peak_start"), "17:00"),
                   _hhmm(settings.get("impact_peak_end"), "22:00"),
                   _float(settings.get("impact_peak_adder_eur_kwh"), 0.0)),
        )
    medium = _float(settings.get("impact_medium_adder_eur_kwh"), 0.0) if structure == TARIFF_STRUCTURE_IMPACT else 0.0
    return Tariff(
        id=CONTRACT_TARIFF_ID, name="Contrat saisi",
        energy_kind=ENERGY_FIXED, energy_price=price,
        network_periods=network, network_default=medium,
        injection_kind=injection_kind, injection_price=injection,
    ).validate()
