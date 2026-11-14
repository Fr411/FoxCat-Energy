"""Modèles de tarifs de départ (Belgique).

Ils remplacent les anciennes listes déroulantes : un modèle remplit un tarif,
que l'utilisateur ajuste ensuite (prix, plages, complément).

Les plages viennent du « Guide des Tarifs et Contrats d'Énergie en Belgique »
(nov. 2026) pour la Wallonie. Les prix sont les valeurs par défaut déjà
utilisées par FoxCat (simple 0,30 ; HP 0,35 ; HC 0,25 €/kWh) : ce sont des
points de départ à remplacer par les prix du contrat réel. Les montants
capacitaires sont les moyennes citées par le guide (Flandre : 51 à 60 €/kW/an,
minimum 2,5 kW ; Bruxelles : environ 47 €/an en monophasé).
"""
from __future__ import annotations

from .models import (
    CAPACITY_FLAT,
    CAPACITY_PEAK,
    ENERGY_FIXED,
    ENERGY_PERIODS,
    INJECTION_OBSERVED,
    CapacityTerm,
    Period,
    Tariff,
)

DEFAULT_SIMPLE_EUR_KWH = 0.30
DEFAULT_HP_EUR_KWH = 0.35
DEFAULT_HC_EUR_KWH = 0.25

TEMPLATE_NOTE = (
    "Modèle de départ : remplacez les prix par ceux de votre contrat. "
    "La réinjection reprend le prix réellement observé, pour comparer à armes égales."
)


def _wallonia_mono() -> Tariff:
    return Tariff(
        id="wal_mono", name="Wallonie • Mono-horaire",
        energy_kind=ENERGY_FIXED, energy_price=DEFAULT_SIMPLE_EUR_KWH,
        injection_kind=INJECTION_OBSERVED, note=TEMPLATE_NOTE,
    )


def _wallonia_bi_2026() -> Tariff:
    # HC = nuit (22h-07h) + 11h-17h, 7j/7 ; HP = 07h-11h et 17h-22h.
    return Tariff(
        id="wal_bi_2026", name="Wallonie • Bi-horaire 2026",
        energy_kind=ENERGY_PERIODS, energy_price=DEFAULT_HC_EUR_KWH,
        energy_periods=(
            Period("HP matin", "07:00", "11:00", DEFAULT_HP_EUR_KWH),
            Period("HP soir", "17:00", "22:00", DEFAULT_HP_EUR_KWH),
        ),
        injection_kind=INJECTION_OBSERVED, note=TEMPLATE_NOTE,
    )


def _wallonia_impact() -> Tariff:
    # ECO 01h-07h et 11h-17h, PIC 17h-22h, MEDIUM le reste. Compléments à renseigner.
    return Tariff(
        id="wal_impact", name="Wallonie • Impact",
        energy_kind=ENERGY_FIXED, energy_price=DEFAULT_SIMPLE_EUR_KWH,
        network_periods=(
            Period("ECO nuit", "01:00", "07:00", 0.0),
            Period("ECO jour", "11:00", "17:00", 0.0),
            Period("PIC", "17:00", "22:00", 0.0),
        ),
        injection_kind=INJECTION_OBSERVED,
        note=TEMPLATE_NOTE + " Compléments réseau ECO / MEDIUM / PIC à renseigner (MEDIUM = hors plages).",
    )


def _flanders_capacity() -> Tariff:
    return Tariff(
        id="fla_capacity", name="Flandre • Capacitaire",
        energy_kind=ENERGY_FIXED, energy_price=DEFAULT_SIMPLE_EUR_KWH,
        capacity=CapacityTerm(kind=CAPACITY_PEAK, eur_per_kw_year=55.0, min_kw=2.5),
        injection_kind=INJECTION_OBSERVED,
        note=TEMPLATE_NOTE + " Capacitaire : moyenne du guide (51 à 60 €/kW/an), minimum 2,5 kW.",
    )


def _brussels_flat() -> Tariff:
    return Tariff(
        id="bru_forfait", name="Bruxelles • Forfait capacitaire",
        energy_kind=ENERGY_FIXED, energy_price=DEFAULT_SIMPLE_EUR_KWH,
        capacity=CapacityTerm(kind=CAPACITY_FLAT, eur_per_year=47.0),
        injection_kind=INJECTION_OBSERVED,
        note=TEMPLATE_NOTE + " Forfait : environ 47 €/an en monophasé (moins de 13 kVA), le double au-delà.",
    )


_BUILDERS = (
    _wallonia_mono, _wallonia_bi_2026, _wallonia_impact,
    _flanders_capacity, _brussels_flat,
)


def template_catalog() -> dict[str, Tariff]:
    """Tous les modèles, indexés par identifiant."""
    return {t.id: t.validate() for t in (build() for build in _BUILDERS)}


def template_labels() -> dict[str, str]:
    return {tid: t.name for tid, t in template_catalog().items()}


# Modèles proposés d'office selon la région choisie à l'installation.
REGION_TEMPLATES: dict[str, tuple[str, ...]] = {
    "wallonie": ("wal_mono", "wal_bi_2026", "wal_impact"),
    "flandre": ("wal_mono", "fla_capacity"),
    "bruxelles": ("wal_mono", "bru_forfait"),
    "autre": (),
}


def templates_for_region(region: str | None) -> list[Tariff]:
    """Tarifs de comparaison préchargés pour une région (liste vide si inconnue)."""
    catalog = template_catalog()
    return [catalog[tid] for tid in REGION_TEMPLATES.get(str(region or "autre"), ())]
