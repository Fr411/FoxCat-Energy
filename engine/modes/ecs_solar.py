from __future__ import annotations

from datetime import datetime

from ...const import BOILER_BOOST_65, BOILER_HEAT_45, BOILER_NONE, BOILER_STOP
from ..models import BoilerIntent, EnergySnapshot
from ..tariff import is_offpeak_day, is_offpeak_night, is_peak, minute_of_day
from .common import coverage, ecs_last_departure


def evaluate_ecs_solar(
    snapshot: EnergySnapshot,
    t0: EnergySnapshot,
    settings: dict[str, object],
    now: datetime,
    boiler_on_seconds: float,
    current_demand: str,
) -> BoilerIntent:
    """ECS solaire V1.2.0.

    La logique métier est reprise de V1.1.0. Seule la lecture des plages HP/HC
    passe par le contexte tarifaire configurable avec les mêmes valeurs AIESH
    par défaut.
    """
    normal = float(settings["boiler_temp_normal_c"])
    boost = float(settings["boiler_temp_boost_c"])
    safety = float(settings["boiler_temp_safety_c"])
    cycle_min = float(settings["boiler_cycle_min_s"])
    boiler_power = float(settings["boiler_power_w"])

    if not bool(settings["boiler_enabled"]):
        return BoilerIntent(BOILER_STOP, "Boiler désactivé dans FoxCat.", "SECURITE")
    if snapshot.boiler_safety_temp_c >= safety:
        return BoilerIntent(BOILER_STOP, "Sécurité thermique atteinte.", "SECURITE")
    if snapshot.boiler_temp_c >= boost:
        return BoilerIntent(BOILER_STOP, "65 °C atteint : stockage thermique terminé.", "TEMPERATURE")
    if is_peak(now, settings) and snapshot.boiler_on and snapshot.import_w > 0:
        return BoilerIntent(BOILER_STOP, "HP : achat réseau détecté, arrêt demandé.", "HP")

    if snapshot.boiler_on and boiler_on_seconds < cycle_min:
        if snapshot.boiler_temp_c < normal:
            return BoilerIntent(BOILER_HEAT_45, "Cycle minimum actif : maintien CHAUFFE_45.", "CYCLE_MIN")
        if (not is_peak(now, settings)) and snapshot.boiler_temp_c < boost:
            return BoilerIntent(BOILER_BOOST_65, "45 °C atteint pendant le cycle minimum : transition BOOST_65 sans coupure.", "CYCLE_MIN")
        return BoilerIntent(BOILER_STOP, "Cycle minimum : aucune prolongation autorisée.", "CYCLE_MIN")

    coverage_now = coverage(snapshot.grid_net_w, boiler_power)
    coverage_t0 = coverage(t0.grid_net_w, boiler_power)
    last_departure = ecs_last_departure(snapshot, settings, now)

    if is_offpeak_night(now, settings):
        if not bool(settings["boiler_allow_hc"]):
            return BoilerIntent(BOILER_NONE, "Nuit HC : autorisation boiler HC désactivée.", "HC_NUIT")
        m = minute_of_day(now)
        if 1320 <= m < 1380:  # 22:00-23:00 observation
            if snapshot.boiler_temp_c < normal and last_departure:
                return BoilerIntent(BOILER_HEAT_45, "Nuit observation : failback atteint.", "ECS_HC_45")
            return BoilerIntent(BOILER_NONE, "22h00-23h00 : observation thermique.", "HC_NUIT")
        if 1380 <= m < 1400:  # 23:00-23:20
            if snapshot.boiler_temp_c < normal:
                return BoilerIntent(BOILER_HEAT_45, "23h00-23h20 : charge initiale nocturne.", "ECS_HC_45")
            return BoilerIntent(BOILER_STOP, "Charge initiale : 45 °C déjà atteint.", "HC_NUIT")
        if 1400 <= m < 1430:  # 23:20-23:50
            if snapshot.boiler_temp_c < normal and last_departure:
                return BoilerIntent(BOILER_HEAT_45, "Stabilisation : failback critique.", "ECS_HC_45")
            return BoilerIntent(BOILER_STOP, "23h20-23h50 : stabilisation de la sonde.", "HC_NUIT")
        if snapshot.boiler_on and snapshot.boiler_temp_c < normal:
            return BoilerIntent(BOILER_HEAT_45, "Failback nuit : chauffe engagée, continuité jusqu'à 45 °C.", "ECS_HC_45")
        if snapshot.boiler_temp_c < normal and last_departure:
            return BoilerIntent(BOILER_HEAT_45, "Failback nuit atteint : CHAUFFE_45.", "ECS_HC_45")
        if snapshot.boiler_temp_c >= normal:
            return BoilerIntent(BOILER_STOP, "Failback nuit : confort 45 °C assuré.", "HC_NUIT")
        return BoilerIntent(BOILER_NONE, "Nuit HC : aucune chauffe nécessaire.", "HC_NUIT")

    if is_offpeak_day(now, settings):
        if not bool(settings["boiler_allow_hc"]):
            return BoilerIntent(BOILER_NONE, "HC jour : autorisation boiler HC désactivée.", "HC_JOUR")

        aggression = bool(settings["agressivite_ecs"])
        min_cov = float(settings["coverage_solar_min_percent"])
        surplus_min = float(settings["surplus_pv_min_agressivite_w"])
        import_max = float(settings["import_boiler_max_w"])
        coverage_depart = min(min_cov, 80.0) if aggression and snapshot.pv_w > 0 and snapshot.grid_net_w >= surplus_min else 80.0
        solar_only_boost = coverage_t0 >= 100 and coverage_now >= 100
        if solar_only_boost:
            boost_depart_ok = True
        elif aggression:
            boost_depart_ok = snapshot.pv_w > 0 and snapshot.grid_net_w >= surplus_min and coverage_t0 >= min_cov and coverage_now >= min_cov
        else:
            boost_depart_ok = snapshot.pv_w > 0 and t0.grid_net_w >= 600 and snapshot.grid_net_w >= 600
        allowed_import_boost = import_max if aggression and snapshot.pv_w > 0 else (1200.0 if snapshot.pv_w > 0 else 0.0)
        boost_continuation_ok = snapshot.pv_w > 0 and snapshot.import_w <= allowed_import_boost

        if snapshot.boiler_on and snapshot.boiler_temp_c < normal:
            return BoilerIntent(BOILER_HEAT_45, "HC jour : chauffe 45 °C engagée, continuité.", "ECS_HC_45")
        if snapshot.boiler_on and current_demand == BOILER_HEAT_45 and normal <= snapshot.boiler_temp_c < boost:
            if boost_continuation_ok:
                return BoilerIntent(BOILER_BOOST_65, "45 °C atteint : transition directe vers BOOST_65.", "ECS_BOOST_65")
            return BoilerIntent(BOILER_STOP, "45 °C atteint : boost non justifié.", "HC_JOUR")
        if snapshot.boiler_on and current_demand == BOILER_BOOST_65 and snapshot.boiler_temp_c < boost:
            if boost_continuation_ok:
                return BoilerIntent(BOILER_BOOST_65, "BOOST_65 maintenu : conditions PV/import acceptables.", "ECS_BOOST_65")
            return BoilerIntent(BOILER_STOP, "BOOST_65 arrêté : PV/import hors limite.", "HC_JOUR")
        if not snapshot.boiler_on and normal <= snapshot.boiler_temp_c < boost and boost_depart_ok:
            return BoilerIntent(BOILER_BOOST_65, "HC jour : opportunité de stockage solaire confirmée.", "ECS_BOOST_65")
        if not snapshot.boiler_on and snapshot.boiler_temp_c < normal and coverage_t0 >= coverage_depart and coverage_now >= coverage_depart:
            return BoilerIntent(BOILER_HEAT_45, "HC jour : couverture solaire stable suffisante.", "ECS_HC_45")
        if snapshot.boiler_temp_c < normal and last_departure:
            return BoilerIntent(BOILER_HEAT_45, "HC jour : failback atteint.", "ECS_HC_45")
        if 960 <= minute_of_day(now) < 1020 and snapshot.boiler_temp_c < normal:
            return BoilerIntent(BOILER_HEAT_45, "16h00-17h00 : rattrapage HC vers 45 °C.", "ECS_HC_45")
        return BoilerIntent(BOILER_NONE, "HC jour : attente, aucune chauffe nécessaire.", "HC_JOUR")

    # Heures pleines
    if snapshot.boiler_on and snapshot.boiler_temp_c < normal and snapshot.import_w <= 0:
        return BoilerIntent(BOILER_HEAT_45, "HP : chauffe 45 °C maintenue sans achat réseau.", "ECS_SOLAR_45")
    if not snapshot.boiler_on and snapshot.boiler_temp_c < normal and coverage_t0 >= 100 and coverage_now >= 100:
        return BoilerIntent(BOILER_HEAT_45, "HP : CHAUFFE_45 autorisée à 100 % solaire sur deux trames.", "ECS_SOLAR_45")
    if snapshot.boiler_on and snapshot.boiler_temp_c < normal and snapshot.import_w > 0:
        return BoilerIntent(BOILER_STOP, "HP : apparition d'un achat réseau.", "HP")
    if snapshot.boiler_temp_c >= normal:
        return BoilerIntent(BOILER_STOP, "HP : 45 °C atteint, aucun boost opportuniste.", "HP")
    return BoilerIntent(BOILER_NONE, "HP : aucune opportunité solaire exploitable.", "HP")
