from __future__ import annotations

from typing import Any

from ...const import (
    BOILER_BOOST_65,
    BOILER_HEAT_45,
    BOILER_NONE,
    BOILER_STOP,
    MODE_MANUAL,
    PRICE_SOURCE_DYNAMIC,
    TARIFF_DYNAMIC,
)
from ..load_guard import boiler_surplus_before_load_w
from ..models import BoilerIntent, EnergySnapshot


def evaluate_dynamic_boiler_v2(
    snapshot: EnergySnapshot,
    base_intent: BoilerIntent,
    settings: dict[str, object],
    economic_view: dict[str, Any],
) -> BoilerIntent:
    """Arbitrage boiler réservé à la source Day-Ahead, hors comportement Manuel.

    Cette branche ne s'applique qu'à la source Day-Ahead et ne s'exécute jamais
    en comportement Manuel. Le BOOST 65 °C reste exclusivement solaire.
    Le réseau peut assurer le confort normal jusqu'au plafond Day-Ahead
    ``dynamic_high_position_pct`` (65 % par défaut), jamais le stockage 65 °C.
    """
    if str(settings.get("mode")) == MODE_MANUAL:
        return base_intent
    if (
        str(settings.get("price_source")) != PRICE_SOURCE_DYNAMIC
        and str(settings.get("tariff_regime")) != TARIFF_DYNAMIC
    ):
        return base_intent
    if base_intent.origin in {"SECURITE", "UTILISATEUR"}:
        return base_intent

    safety = float(settings.get("boiler_temp_safety_c", 68.0))
    if snapshot.boiler_safety_temp_c >= safety:
        return BoilerIntent(
            BOILER_STOP,
            f"Dynamique : sécurité thermique {snapshot.boiler_safety_temp_c:.1f} °C >= {safety:.1f} °C.",
            "DYNAMIC_SECURITE",
        )

    normal = float(settings.get("boiler_temp_normal_c", 45.0))
    start = float(settings.get("boiler_temp_start_c", 43.0))
    boost = min(float(settings.get("boiler_temp_boost_c", 65.0)), safety)
    element_w = max(float(settings.get("boiler_power_w", 1800.0)), 1.0)
    favorable_pct = max(5.0, min(60.0, float(settings.get("dynamic_favorable_position_pct", 30.0))))
    high_pct = max(favorable_pct, min(95.0, float(settings.get("dynamic_high_position_pct", 65.0))))

    # 1) Le soleil est souverain pour le stockage thermique. On reconstitue le
    # surplus avant charge afin qu'un Boiler déjà ON ne s'arrête pas à cause de
    # sa propre consommation. Aucun prix Day-Ahead ne peut bloquer ce BOOST.
    surplus_before_boiler = boiler_surplus_before_load_w(snapshot)
    full_solar = surplus_before_boiler >= element_w
    if full_solar:
        if snapshot.boiler_temp_c < boost:
            return BoilerIntent(
                BOILER_BOOST_65,
                (
                    "Dynamique : BOOST solaire souverain, "
                    f"surplus avant Boiler {surplus_before_boiler:.0f} W >= "
                    f"résistance {element_w:.0f} W ; cible {boost:.1f} °C."
                ),
                "DYNAMIC_BOOST_SOLAIRE",
            )
        return BoilerIntent(
            BOILER_STOP if snapshot.boiler_on else BOILER_NONE,
            f"Dynamique : stockage solaire terminé à {boost:.1f} °C.",
            "DYNAMIC_BOOST_TERMINE",
        )

    decision = dict(economic_view.get("decision", {}) or {})
    position = decision.get("dynamic_curve_position_pct")
    if not isinstance(position, (int, float)):
        # Même en repli, un BOOST réseau 65 °C est interdit : le BOOST est solaire.
        if base_intent.action == BOILER_BOOST_65:
            if snapshot.boiler_temp_c < normal:
                return BoilerIntent(
                    BOILER_HEAT_45,
                    "Dynamique : position Day-Ahead indisponible ; stockage réseau 65 °C interdit, maintien confort 45 °C seulement.",
                    "DYNAMIC_REPLI_45",
                )
            return BoilerIntent(
                BOILER_STOP if snapshot.boiler_on else BOILER_NONE,
                "Dynamique : position Day-Ahead indisponible ; BOOST réseau interdit.",
                "DYNAMIC_REPLI",
            )
        return base_intent

    position = float(position)

    # 2) Au-dessus du plafond économique, aucune nouvelle chauffe réseau Boiler.
    if position > high_pct:
        return BoilerIntent(
            BOILER_STOP if snapshot.boiler_on else BOILER_NONE,
            (
                f"Dynamique : Boiler reporté, position Day-Ahead {position:.1f} % "
                f"> plafond acceptable {high_pct:.1f} %."
            ),
            "DYNAMIC_ATTENTE_PRIX",
        )

    # 3) Zone très favorable : on remet immédiatement le confort à 45 °C.
    # Le réseau ne monte jamais à la consigne BOOST ; 65 °C reste solaire.
    if position <= favorable_pct:
        if snapshot.boiler_temp_c < normal:
            return BoilerIntent(
                BOILER_HEAT_45,
                (
                    f"Dynamique : prix très favorable ({position:.1f} % <= {favorable_pct:.1f} %), "
                    f"chauffe confort jusqu'à {normal:.1f} °C."
                ),
                "DYNAMIC_PRIX_FAVORABLE",
            )
        return BoilerIntent(
            BOILER_STOP if snapshot.boiler_on else BOILER_NONE,
            f"Dynamique : confort {normal:.1f} °C déjà assuré ; attente d'un BOOST solaire.",
            "DYNAMIC_CONFORT_OK",
        )

    # 4) Zone acceptable : fallback propre au Dynamic. Pas de copie du moteur
    # Bihoraire. Il ne vise que le confort normal, jamais 65 °C.
    if snapshot.boiler_temp_c < start:
        return BoilerIntent(
            BOILER_HEAT_45,
            (
                f"Dynamique : fallback ECS, {snapshot.boiler_temp_c:.1f} °C < reprise {start:.1f} °C, "
                f"position {position:.1f} % <= {high_pct:.1f} % ; cible {normal:.1f} °C."
            ),
            "DYNAMIC_FALLBACK_ECS",
        )

    # Une réservation Day-Ahead peut terminer la chauffe normale entre reprise
    # et confort, à condition de rester sous le plafond acceptable.
    if snapshot.boiler_temp_c < normal and bool(decision.get("boiler_charge_now")):
        return BoilerIntent(
            BOILER_HEAT_45,
            (
                f"Dynamique : fenêtre Day-Ahead réservée active à {position:.1f} %, "
                f"chauffe jusqu'à {normal:.1f} °C."
            ),
            "DYNAMIC_RESERVATION",
        )

    if snapshot.boiler_temp_c >= normal:
        return BoilerIntent(
            BOILER_STOP if snapshot.boiler_on else BOILER_NONE,
            f"Dynamique : confort {normal:.1f} °C assuré ; attente solaire ou meilleur créneau.",
            "DYNAMIC_ATTENTE",
        )

    return BoilerIntent(
        BOILER_STOP if snapshot.boiler_on else BOILER_NONE,
        (
            f"Dynamique : {snapshot.boiler_temp_c:.1f} °C entre reprise et confort, "
            "aucune fenêtre réservée ; attente."
        ),
        "DYNAMIC_ATTENTE",
    )
