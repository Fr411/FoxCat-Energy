from __future__ import annotations

from datetime import datetime

from ...const import BOILER_BOOST_65, BOILER_HEAT_45, BOILER_NONE, BOILER_STOP
from ..models import BoilerIntent, EnergySnapshot
from ..tariff import is_offpeak, is_peak
from .common import coverage


def evaluate_eco(
    snapshot: EnergySnapshot,
    t0: EnergySnapshot,
    settings: dict[str, object],
    now: datetime,
    boiler_on_seconds: float,
    current_demand: str,
) -> BoilerIntent:
    """Mode Économie énergie hybride boiler + PRI.

    Le boiler absorbe d'abord un surplus réellement disponible. Le PRI est
    arbitré séparément par le coordinateur et traite l'excédent résiduel.
    Aucun achat HP n'est autorisé pour le boiler.
    """
    normal = float(settings["boiler_temp_normal_c"])
    start = float(settings["boiler_temp_start_c"])
    boost = float(settings["boiler_temp_boost_c"])
    safety = float(settings["boiler_temp_safety_c"])
    boiler_power = float(settings["boiler_power_w"])
    cycle_min = float(settings["boiler_cycle_min_s"])

    if not bool(settings["boiler_enabled"]):
        return BoilerIntent(BOILER_STOP, "Économie énergie : boiler désactivé.", "SECURITE")
    if snapshot.boiler_safety_temp_c >= safety:
        return BoilerIntent(BOILER_STOP, "Économie énergie : sécurité thermique atteinte.", "SECURITE")
    if snapshot.boiler_temp_c >= boost:
        return BoilerIntent(BOILER_STOP, "Économie énergie : stockage ECS 65 °C terminé.", "ECO")

    cov_now = coverage(snapshot.grid_net_w, boiler_power)
    cov_t0 = coverage(t0.grid_net_w, boiler_power)
    solar_full = cov_now >= 100 and cov_t0 >= 100

    # Le non-achat en HP reste prioritaire sur l'opportunisme solaire.
    if is_peak(now, settings) and snapshot.boiler_on and snapshot.import_w > 50:
        return BoilerIntent(BOILER_STOP, "Économie énergie : achat réseau HP interdit pour le boiler.", "ECO")

    # Respect du cycle physique minimum lorsqu'il n'entre pas en conflit avec
    # la règle HP ci-dessus ni avec une sécurité.
    if snapshot.boiler_on and boiler_on_seconds < cycle_min:
        if snapshot.boiler_temp_c < normal:
            return BoilerIntent(BOILER_HEAT_45, "Économie énergie : cycle minimum CHAUFFE_45 en cours.", "CYCLE_MIN")
        if current_demand == BOILER_BOOST_65 and snapshot.import_w <= 50:
            return BoilerIntent(BOILER_BOOST_65, "Économie énergie : cycle minimum BOOST_65 en cours.", "CYCLE_MIN")

    # Un boost solaire engagé reste actif tant qu'il ne provoque pas d'achat.
    if snapshot.boiler_on and current_demand == BOILER_BOOST_65 and normal <= snapshot.boiler_temp_c < boost:
        if snapshot.import_w <= 50 and snapshot.pv_w > 0:
            return BoilerIntent(BOILER_BOOST_65, "Économie énergie : stockage solaire vers 65 °C maintenu.", "ECO_SOLAR")
        return BoilerIntent(BOILER_STOP, "Économie énergie : surplus solaire disparu, fin du boost.", "ECO_SOLAR")

    # Le surplus est valorisé avant bridage PRI : 45 °C d'abord, puis stockage
    # opportuniste jusqu'à 65 °C si le boiler peut être couvert sur deux trames.
    if solar_full:
        if snapshot.boiler_temp_c < normal:
            return BoilerIntent(BOILER_HEAT_45, "Économie énergie : surplus solaire utilisé pour atteindre 45 °C.", "ECO_SOLAR")
        if snapshot.boiler_temp_c < boost:
            return BoilerIntent(BOILER_BOOST_65, "Économie énergie : surplus solaire stocké dans l'ECS avant bridage PRI.", "ECO_SOLAR")

    # Comportement historique de confort minimal en HC conservé.
    if snapshot.boiler_on and snapshot.boiler_temp_c < normal:
        if is_offpeak(now, settings) and bool(settings["boiler_allow_hc"]):
            return BoilerIntent(BOILER_HEAT_45, "Économie énergie : chauffe HC engagée jusqu'à 45 °C.", "HC_RESEAU")
        return BoilerIntent(BOILER_NONE, "Économie énergie : chauffe en cours surveillée.", "ECO")

    if is_offpeak(now, settings) and bool(settings["boiler_allow_hc"]) and not snapshot.boiler_on and snapshot.boiler_temp_c < start:
        return BoilerIntent(BOILER_HEAT_45, "Économie énergie : seuil HC atteint, chauffe à 45 °C.", "HC_RESEAU")

    if snapshot.boiler_on and snapshot.boiler_temp_c >= normal:
        return BoilerIntent(BOILER_STOP, "Économie énergie : 45 °C atteint sans surplus à stocker.", "ECO")

    return BoilerIntent(BOILER_NONE, "Économie énergie : aucune action boiler, PRI disponible pour l'excédent résiduel.", "ECO")
