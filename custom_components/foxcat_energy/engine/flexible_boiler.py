from __future__ import annotations

from datetime import datetime
from typing import Any

from ..const import (
    BOILER_BOOST_65, BOILER_HEAT_45, BOILER_NONE, BOILER_STOP,
    MODE_ECO, MODE_COMFORT, MODE_MANUAL, TARIFF_DYNAMIC, TARIFF_TOU,
    DISTRIBUTION_WALLONIA_IMPACT,
)
from .load_guard import boiler_surplus_before_load_w
from .models import BoilerIntent, EnergySnapshot
from .tariff import is_offpeak, distribution_period


def evaluate_flexible_boiler(
    snapshot: EnergySnapshot, settings: dict[str, Any], economic_view: dict[str, Any],
    now: datetime, thermal: dict[str, Any], user_override: str = "AUTO",
) -> BoilerIntent:
    """Boiler = charge flexible universelle FoxCat 1.7.0.

    L'ordre de décision est identique quel que soit le comptage : sécurité,
    utilisateur, surplus solaire, puis arbitrage contrat/comportement.
    """
    mode = str(settings.get("mode", MODE_ECO))
    if not bool(settings.get("boiler_enabled", True)):
        return BoilerIntent(BOILER_STOP, "Charge flexible Boiler désactivée.", "SECURITE")
    safety = float(settings.get("boiler_temp_safety_c", 68.0))
    if snapshot.boiler_safety_temp_c >= safety:
        return BoilerIntent(BOILER_STOP, "Sécurité thermique Boiler atteinte.", "SECURITE")
    if user_override == "FORCE_OFF":
        return BoilerIntent(BOILER_STOP, "Utilisateur : arrêt Boiler forcé.", "UTILISATEUR")
    if user_override == "FORCE_ON":
        return BoilerIntent(BOILER_HEAT_45, "Utilisateur : démarrage Boiler forcé.", "UTILISATEUR")
    if mode == MODE_MANUAL:
        return BoilerIntent(BOILER_NONE, "Mode Manuel : aucune décision automatique Boiler.", "MANUEL")

    normal = float(settings.get("boiler_temp_normal_c", 45.0))
    start = float(settings.get("boiler_temp_start_c", 43.0))
    boost = min(float(settings.get("boiler_temp_boost_c", 65.0)), safety)
    element_w = max(float(settings.get("boiler_power_w", 1800.0)), 1.0)
    effective = float(thermal.get("effective_temp_c", snapshot.boiler_temp_c))
    confidence = float(thermal.get("confidence_pct", 50.0))
    draw = bool(thermal.get("draw_detected", False))

    # Solaire souverain dans TOUS les contrats et profils de comptage.
    surplus_before = boiler_surplus_before_load_w(snapshot)
    if surplus_before >= element_w and effective < boost:
        return BoilerIntent(
            BOILER_BOOST_65,
            f"Charge flexible : surplus solaire {surplus_before:.0f} W >= {element_w:.0f} W, stockage thermique vers {boost:.1f} °C.",
            "FLEX_SOLAR_BOOST",
        )

    # En cas de confiance faible, ne jamais déclencher un fallback sur une seule
    # valeur de sonde douteuse. Un puisage rapide augmente au contraire la preuve.
    min_conf = float(settings.get("boiler_fallback_min_confidence_pct", 35.0))
    need = effective < start and (confidence >= min_conf or draw)
    comfort_missing = effective < normal

    regime = str(settings.get("tariff_regime", TARIFF_TOU))
    dperiod = distribution_period(now, settings)
    decision = dict(economic_view.get("decision", {}) or {})

    # La distribution est une couche indépendante du contrat. En tarif Impact,
    # le mode Éco refuse un nouveau prélèvement flexible pendant PIC, sauf
    # puisage ECS détecté. Le boost solaire a déjà été traité au-dessus.
    if dperiod == "PIC" and mode == MODE_ECO and not draw:
        return BoilerIntent(
            BOILER_STOP if snapshot.boiler_on and effective >= normal else BOILER_NONE,
            "Distribution Impact PIC : nouveau prélèvement Boiler reporté en mode Éco.",
            "FLEX_IMPACT_WAIT",
        )

    # Dynamique : 30 % = creux favorable ; plafond 65 % (Éco) avec
    # assouplissement explicite en Confort. Le boost 65 reste solaire uniquement.
    if regime == TARIFF_DYNAMIC:
        pos = decision.get("dynamic_curve_position_pct")
        if not isinstance(pos, (int, float)):
            return BoilerIntent(BOILER_NONE, "Dynamic : position Day-Ahead indisponible, attente prudente.", "FLEX_DYNAMIC_WAIT")
        pos = float(pos)
        low = float(settings.get("dynamic_favorable_position_pct", 30.0))
        # Le plafond haut est une limite économique dure du Boiler Dynamic.
        # Le mode Confort assouplit le déclenchement en dessous de ce plafond,
        # mais ne l'autorise jamais à acheter au-delà.
        high = float(settings.get("dynamic_high_position_pct", 65.0))
        if pos > high:
            return BoilerIntent(BOILER_STOP if snapshot.boiler_on else BOILER_NONE, f"Dynamic : {pos:.1f} % > plafond {high:.1f} %, achat Boiler reporté.", "FLEX_DYNAMIC_WAIT")
        if pos <= low and comfort_missing:
            return BoilerIntent(BOILER_HEAT_45, f"Dynamic : creux favorable {pos:.1f} % <= {low:.1f} %, confort vers {normal:.1f} °C.", "FLEX_DYNAMIC_LOW")
        if need:
            return BoilerIntent(BOILER_HEAT_45, f"Dynamic : fallback flexible validé ({confidence:.0f} % confiance), position {pos:.1f} % <= {high:.1f} %.", "FLEX_DYNAMIC_FALLBACK")
        if comfort_missing and bool(decision.get("boiler_charge_now")):
            return BoilerIntent(BOILER_HEAT_45, "Dynamic : créneau Day-Ahead réservé pour le Boiler.", "FLEX_DYNAMIC_RESERVED")
        return BoilerIntent(BOILER_STOP if snapshot.boiler_on and effective >= normal else BOILER_NONE, "Dynamic : attente du solaire ou d'un meilleur créneau.", "FLEX_DYNAMIC_WAIT")

    # Bihoraire : le comportement économique historique est conservé mais le
    # Boiler passe par la même abstraction de charge flexible.
    if regime == TARIFF_TOU:
        if is_offpeak(now, settings) and bool(settings.get("boiler_allow_hc", True)) and (need or (mode == MODE_COMFORT and comfort_missing)):
            return BoilerIntent(BOILER_HEAT_45, f"Bihoraire : charge flexible en HC vers {normal:.1f} °C.", "FLEX_HC")
        if snapshot.boiler_on and not is_offpeak(now, settings) and effective < normal and mode == MODE_COMFORT and dperiod != "PIC":
            return BoilerIntent(BOILER_HEAT_45, "Confort : poursuite limitée de la chauffe déjà engagée.", "FLEX_COMFORT")
        return BoilerIntent(BOILER_STOP if snapshot.boiler_on and effective >= normal else BOILER_NONE, "Bihoraire : attente HC ou solaire.", "FLEX_TOU_WAIT")

    # Contrat fixe/monohoraire : le prix n'apporte pas de fenêtre d'arbitrage.
    # Impact reste une contrainte de distribution indépendante.
    if need or (mode == MODE_COMFORT and comfort_missing):
        return BoilerIntent(BOILER_HEAT_45, f"Contrat fixe : besoin ECS validé, cible {normal:.1f} °C.", "FLEX_FIXED")
    return BoilerIntent(BOILER_STOP if snapshot.boiler_on and effective >= normal else BOILER_NONE, "Boiler flexible : aucune charge nécessaire.", "FLEX_IDLE")
