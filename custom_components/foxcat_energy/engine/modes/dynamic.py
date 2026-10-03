from __future__ import annotations

from datetime import datetime

from ...const import BOILER_BOOST_65, BOILER_HEAT_45, BOILER_NONE, BOILER_STOP, TARIFF_DYNAMIC
from ..models import BoilerIntent, EnergySnapshot, SolarForecast
from .common import coverage, thermal_deadline


def evaluate_dynamic(
    snapshot: EnergySnapshot,
    t0: EnergySnapshot,
    settings: dict[str, object],
    now: datetime,
    prices: dict[str, object],
    solar: SolarForecast,
) -> BoilerIntent:
    """Mode financier dynamique.

    Priorités : sécurité > garde cycle protégé du CORE > prix négatif réseau > solaire utile >
    optimisation min/max/tendance. Un prix d'achat strictement inférieur au
    seuil configuré autorise explicitement un chargement ECS sur le réseau
    jusqu'au niveau de stockage 65 °C.
    """
    if str(settings.get("tariff_regime")) != TARIFF_DYNAMIC:
        return BoilerIntent(
            BOILER_NONE,
            "Prix dynamique bloqué : le régime tarifaire sélectionné n'est pas Dynamique.",
            "PRIX_BLOQUE",
        )
    if not bool(settings["boiler_enabled"]):
        return BoilerIntent(BOILER_STOP, "Boiler désactivé dans FoxCat.", "SECURITE")
    if snapshot.boiler_safety_temp_c >= float(settings["boiler_temp_safety_c"]):
        return BoilerIntent(BOILER_STOP, "Sécurité thermique boiler.", "SECURITE")

    # Le mode dynamique consomme exclusivement le contexte tarifaire normalisé
    # par le coordinator : achat Luminus Dynamic all-in et valeur économique
    # signée de la réinjection. Aucune entité ComfyFlex n'entre ici.
    current = prices.get("active_buy")
    next_price = prices.get("next_buy")
    pmin = prices.get("min_today")
    pmax = prices.get("max_today")
    avg = prices.get("avg_today")
    export_value = prices.get("export_value")
    if not isinstance(current, (int, float)) or not isinstance(pmin, (int, float)) or not isinstance(pmax, (int, float)):
        return BoilerIntent(BOILER_NONE, "Prix dynamiques invalides : régulation suspendue.", "PRIX")
    current = float(current)
    pmin = float(pmin)
    pmax = float(pmax)
    next_price = float(next_price) if isinstance(next_price, (int, float)) else current
    avg = float(avg) if isinstance(avg, (int, float)) else current
    export_value = float(export_value) if isinstance(export_value, (int, float)) else 0.0

    normal = float(settings["boiler_temp_normal_c"])
    start = float(settings["boiler_temp_start_c"])
    boost = float(settings["boiler_temp_boost_c"])
    boiler_power = float(settings["boiler_power_w"])
    coverage_now = coverage(snapshot.grid_net_w, boiler_power)
    coverage_t0 = coverage(t0.grid_net_w, boiler_power)

    # NOUVEAU V1.2.0 : le prix d'achat négatif autorise une charge réseau.
    # La charge va jusqu'au stockage thermique utile (65 °C), jamais au-delà de
    # la sécurité 68 °C qui reste souveraine dans le CORE.
    negative_threshold = float(settings.get("dynamic_grid_charge_threshold_eur_kwh", 0.0))
    negative_enabled = bool(settings.get("dynamic_negative_price_charge_enabled", True))
    if negative_enabled and current < negative_threshold:
        if snapshot.boiler_temp_c < boost:
            return BoilerIntent(
                BOILER_BOOST_65,
                f"Prix dynamique négatif {current:.4f} €/kWh : charge réseau autorisée jusqu'à 65 °C.",
                "PRIX_NEGATIF_RESEAU",
            )
        if snapshot.boiler_on:
            return BoilerIntent(BOILER_STOP, "Prix négatif : stockage ECS 65 °C déjà rempli.", "PRIX_NEGATIF_RESEAU")
        return BoilerIntent(BOILER_NONE, "Prix négatif : stockage ECS déjà à 65 °C.", "PRIX_NEGATIF_RESEAU")

    amplitude = max(pmax - pmin, 0.001)
    position = (current - pmin) / amplitude
    very_low = position <= 0.20 or current <= pmin + 0.005
    low = position <= 0.45 or current < avg
    very_high = position >= 0.80 or current >= pmax - 0.005
    significant = float(settings["dynamic_price_significant_delta"])
    injection_lucrative = export_value > 0.0
    boost_solar = normal <= snapshot.boiler_temp_c < boost and coverage_t0 >= 100 and coverage_now >= 100 and not injection_lucrative
    solar_future = solar.available and solar.confidence >= float(settings["solar_confidence_min_percent"]) and solar.potential in {"Moyen", "Bon", "Fort"}
    deadline = thermal_deadline(snapshot, settings, now)

    # Le solaire reste prioritaire hors prix négatif explicite.
    if snapshot.boiler_temp_c < normal and coverage_t0 >= 100 and coverage_now >= 100:
        return BoilerIntent(BOILER_HEAT_45, "Solaire prioritaire pour le besoin ECS.", "DYNAMIC_SOLAR_45")
    if boost_solar:
        return BoilerIntent(BOILER_BOOST_65, "Stockage solaire ECS économiquement pertinent.", "DYNAMIC_BOOST_65")

    if snapshot.boiler_temp_c >= normal:
        return BoilerIntent(BOILER_STOP if snapshot.boiler_on else BOILER_NONE, "Température ECS normale atteinte.", "PRIX")
    if snapshot.boiler_temp_c < normal and deadline:
        return BoilerIntent(BOILER_HEAT_45, "Dernier départ thermique sûr atteint.", "DYNAMIC_GARANTIE")
    if snapshot.boiler_temp_c < normal and very_low:
        return BoilerIntent(BOILER_HEAT_45, "Créneau tarifaire très favorable utilisé.", "PRIX")
    if snapshot.boiler_temp_c < normal and low and next_price >= current + significant:
        return BoilerIntent(BOILER_HEAT_45, "Bon prix actuel avant hausse.", "PRIX")
    if snapshot.boiler_temp_c < start and current <= avg and not very_high:
        return BoilerIntent(BOILER_HEAT_45, "Besoin ECS et tarif sous la moyenne.", "PRIX")
    if snapshot.boiler_temp_c < normal and next_price < current - significant and not deadline:
        return BoilerIntent(BOILER_STOP, "Attente d'un meilleur prix à l'heure suivante.", "PRIX")
    if snapshot.boiler_temp_c < normal and very_high:
        return BoilerIntent(BOILER_STOP, "Prix élevé évité.", "PRIX")
    if snapshot.boiler_temp_c < normal and solar_future and not deadline and not very_low:
        return BoilerIntent(BOILER_STOP, "Attente solaire recommandée par IA.", "IA")
    return BoilerIntent(BOILER_NONE, "Surveillance dynamique : aucune action nécessaire.", "PRIX")
