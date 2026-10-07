from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Literal

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_AI_TASK,
    CONF_BOILER_BINARY,
    CONF_BOILER_CLIMATE,
    CONF_BOILER_POWER_SENSOR,
    CONF_BOILER_RESISTANCE_TEMP_SENSOR,
    CONF_BOILER_TEMP_SENSOR,
    CONF_DISHWASHER_CYCLE,
    CONF_DISHWASHER_SOCKET,
    CONF_DRYER_CYCLE,
    CONF_DRYER_SOCKET,
    CONF_FORECAST_12H,
    CONF_FORECAST_1H,
    CONF_FORECAST_24H,
    CONF_FORECAST_NEXT_HOUR,
    CONF_FORECAST_NOW,
    CONF_FORECAST_PEAK_TODAY,
    CONF_FORECAST_PEAK_TOMORROW,
    CONF_FORECAST_REMAINING_TODAY,
    CONF_FORECAST_THIS_HOUR,
    CONF_FORECAST_TODAY,
    CONF_FORECAST_TOMORROW,
    CONF_GRID_SIGNED_SENSOR,
    CONF_METRONOME_FALLBACK_SENSOR,
    CONF_PRICE_AVG_TODAY,
    CONF_PRICE_AVG_TOMORROW,
    CONF_PRICE_CURRENT,
    CONF_PRICE_INJECTION,
    CONF_PRICE_MAX_TODAY,
    CONF_PRICE_MAX_TOMORROW,
    CONF_PRICE_MIN_TODAY,
    CONF_PRICE_MIN_TOMORROW,
    CONF_PRICE_NEXT,
    CONF_PRICE_TOMORROW_AVAILABLE,
    CONF_PRICE_FORECAST_IMPORT,
    CONF_PRICE_FORECAST_EXPORT,
    CONF_PRI_L1,
    CONF_PRI_L2,
    CONF_PRI_L3,
    CONF_PRI_L4,
    CONF_INVERTER_POWER_SENSOR,
    CONF_PV_SENSOR,
    CONF_TARIFF_FIXED_INJECTION_PRICE_SENSOR,
    CONF_TARIFF_HC_PRICE_SENSOR,
    CONF_TARIFF_HP_PRICE_SENSOR,
    CONF_WASHER_CYCLE,
    CONF_WASHER_SOCKET,
    NUMBER_DEFINITIONS,
    SWITCH_DEFINITIONS,
    TIME_SETTING_KEYS,
    OFFICIAL_SECTION_ORDER,
)

BindingKind = Literal["native", "config", "literal"]


@dataclass(frozen=True, slots=True)
class RegistryBinding:
    role: str
    section: str
    kind: BindingKind
    key: str | None = None
    fallback_entity_id: str | None = None


# Registre canonique.  Une carte dashboard ne doit jamais dépendre directement
# de l'object_id généré par Home Assistant pour une entité FoxCat native.
BINDINGS: dict[str, RegistryBinding] = {}


def _native(role: str, section: str, key: str, fallback: str | None = None) -> None:
    BINDINGS[role] = RegistryBinding(role, section, "native", key, fallback)


def _config(role: str, section: str, key: str, fallback: str | None = None) -> None:
    BINDINGS[role] = RegistryBinding(role, section, "config", key, fallback)


def _literal(role: str, section: str, entity_id: str) -> None:
    BINDINGS[role] = RegistryBinding(role, section, "literal", None, entity_id)


# Sources énergétiques
_config("sources.grid_signed", "Sources énergétiques", CONF_GRID_SIGNED_SENSOR, "sensor.consommation_instantanee_0")
_config("sources.pv", "Sources énergétiques", CONF_PV_SENSOR, "sensor.homefoxcat_load_solaire")
_config("sources.grid_fallback", "Sources énergétiques", CONF_METRONOME_FALLBACK_SENSOR, "sensor.restitution_reseau")

# Énergie
_native("energy.pv_power", "Énergie", "production_pv", "sensor.foxcat_energy_ems_puissance_de_production_photovoltaique")
_native("energy.house_power", "Énergie", "consommation_maison", "sensor.foxcat_energy_ems_puissance_de_consommation_maison")
_native("energy.grid_power", "Énergie", "reseau_signe", "sensor.foxcat_energy_ems_puissance_nette_reseau")
_native("energy.grid_import", "Énergie", "prelevement_reseau", "sensor.foxcat_energy_ems_puissance_prelevee_au_reseau")
_native("energy.grid_export", "Énergie", "reinjection_reseau", "sensor.foxcat_energy_ems_puissance_reinjectee_au_reseau")
_native("energy.valid", "Énergie", "donnees_valides", "binary_sensor.foxcat_energy_ems_donnees_energetiques_valides")
_native("energy.today.house", "Énergie", "bilan_conso_jour")
_native("energy.today.pv", "Énergie", "bilan_pv_jour")
_native("energy.today.self_consumed", "Énergie", "bilan_autoconso_jour")
_native("energy.today.import", "Énergie", "bilan_import_jour")
_native("energy.today.export", "Énergie", "bilan_export_jour")
_native("energy.today.self_consumption_pct", "Énergie", "bilan_autoconsommation_jour")
_native("energy.today.autonomy_pct", "Énergie", "bilan_autonomie_jour")

# Onduleur / PRI interne
_native("inverter.enabled", "Onduleur", "pri_enabled", "switch.foxcat_energy_pri_solaredge_reduction_de_puissance_onduleur")
_native("inverter.level_current", "Onduleur", "pri_niveau_actuel")
_native("inverter.level_target", "Onduleur", "pri_niveau_cible")
_native("inverter.manual_level", "Onduleur", "pri_niveau_manuel")
_native("inverter.rrcr_code", "Onduleur", "pri_code_rrcr")
_native("inverter.direction", "Onduleur", "pri_direction")
_native("inverter.ack_rrcr", "Onduleur", "pri_ack_rrcr")
_native("inverter.ack_inverter", "Onduleur", "pri_ack_onduleur")
_native("inverter.ack_grid", "Onduleur", "pri_ack_reseau")
_native("inverter.reason", "Onduleur", "pri_derniere_raison", "sensor.foxcat_energy_pri_solaredge_derniere_decision_pri")
_native("inverter.score_current", "Onduleur", "pri_score_actuel")
_native("inverter.score_target", "Onduleur", "pri_score_cible")
_native("inverter.target_pv", "Onduleur", "pri_puissance_pv_cible")
_native("inverter.predicted_import", "Onduleur", "pri_import_prevu")
_native("inverter.predicted_export", "Onduleur", "pri_export_prevu")
_native("inverter.state", "Onduleur", "ems_onduleur_etat")
_native("inverter.pv_limit", "Onduleur", "ems_onduleur_plafond_pv")
_native("inverter.limit_usage", "Onduleur", "ems_onduleur_utilisation_plafond")
_native("inverter.solar_potential", "Onduleur", "ems_onduleur_potentiel")
_native("inverter.release", "Onduleur", "liberer_onduleur")
_config("inverter.power_live", "Onduleur", CONF_INVERTER_POWER_SENSOR)
_native("inverter.power_snapshot", "Onduleur", "puissance_onduleur_snapshot")
_config("inverter.rrcr_l1", "Onduleur", CONF_PRI_L1, "switch.l1_pri")
_config("inverter.rrcr_l2", "Onduleur", CONF_PRI_L2, "switch.l2_pri")
_config("inverter.rrcr_l3", "Onduleur", CONF_PRI_L3, "switch.l3_pri")
_config("inverter.rrcr_l4", "Onduleur", CONF_PRI_L4, "switch.l4_pri")

# EMS
_native("ems.mode", "EMS", "mode_ems", "select.foxcat_energy_ems_mode_ems")
_native("ems.regulation_active", "EMS", "regulation_active", "switch.foxcat_energy_ems_regulation_foxcat_active")
_native("ems.phase", "EMS", "phase", "sensor.foxcat_energy_ems_phase_de_regulation")
_native("ems.fsm_status", "EMS", "fsm_status")
_native("ems.fsm_transition_count", "EMS", "fsm_transition_count")
_native("ems.fsm_last_transition", "EMS", "fsm_last_transition")
_native("ems.fsm_last_transition_at", "EMS", "fsm_last_transition_at")
_native("ems.ack", "EMS", "ack", "sensor.foxcat_energy_ems_validation_dexecution_ems")
_native("ems.reason", "EMS", "derniere_raison")
_native("ems.pending_action", "EMS", "action_en_attente", "sensor.foxcat_energy_ems_action_en_attente")
_native("ems.last_frame", "EMS", "derniere_trame")
_native("ems.last_action", "EMS", "derniere_action")
_native("ems.load_shed", "EMS", "statut_delestage")
_native("ems.persistent_status_notification", "EMS", "persistent_status_notification_enabled")

# Appareils
_native("devices.inverter.enabled", "Appareils", "device_inverter_enabled")
_native("devices.meter.enabled", "Appareils", "device_meter_enabled")
_native("devices.boiler.enabled", "Appareils", "device_boiler_enabled")
_native("devices.machines.enabled", "Appareils", "device_machines_enabled")

# Energy Bus
_native("energy_bus.state", "Energy Bus", "energy_bus_etat")
_native("energy_bus.frame_id", "Energy Bus", "energy_bus_frame_id")
_native("energy_bus.last_frame", "Energy Bus", "energy_bus_derniere_trame")
_native("energy_bus.intent_source", "Energy Bus", "energy_bus_intention_source")
_native("energy_bus.intent_action", "Energy Bus", "energy_bus_intention_action")
_native("energy_bus.intent_delta", "Energy Bus", "energy_bus_intention_delta")
_native("energy_bus.message_id", "Energy Bus", "energy_bus_message_id")
_native("energy_bus.ack", "Energy Bus", "energy_bus_ack")
_native("energy_bus.ack_reason", "Energy Bus", "energy_bus_ack_raison")
_native("energy_bus.ack_by", "Energy Bus", "energy_bus_ack_par")
_native("energy_bus.last_event", "Energy Bus", "energy_bus_dernier_evenement")
_native("energy_bus.pending_count", "Energy Bus", "energy_bus_messages_attente")
_native("energy_bus.message_count_today", "Energy Bus", "energy_bus_messages_jour")
_native("energy_bus.message_count_previous_day", "Energy Bus", "energy_bus_messages_hier")
_native("energy_bus.last_daily_reset", "Energy Bus", "energy_bus_dernier_reset")
_native("energy_bus.last_source", "Energy Bus", "energy_bus_derniere_source")
_native("energy_bus.last_target", "Energy Bus", "energy_bus_derniere_cible")
_native("energy_bus.last_action", "Energy Bus", "energy_bus_derniere_action")
_native("energy_bus.frame_ems_status", "Energy Bus", "energy_bus_trame_ems_statut")
_native("energy_bus.frame_inverter_status", "Energy Bus", "energy_bus_trame_onduleur_statut")
_native("ems.processed_frames", "EMS", "ems_trames_traitees")
_native("inverter.processed_frames", "Onduleur", "onduleur_trames_traitees")
_native("inverter.actuator_status", "Onduleur", "onduleur_actionneur_statut")
_native("inverter.actuator_target", "Onduleur", "onduleur_actionneur_cible")

# Boiler
_config("boiler.climate", "Boiler", CONF_BOILER_CLIMATE, "climate.buanderie_boiler_chauffe_eau")
_config("boiler.temperature_source", "Boiler", CONF_BOILER_TEMP_SENSOR, "sensor.garage_boiler_sonde_temperature_temperature")
_config("boiler.resistance_temperature_source", "Boiler", CONF_BOILER_RESISTANCE_TEMP_SENSOR)
_config("boiler.power_source", "Boiler", CONF_BOILER_POWER_SENSOR, "sensor.boiler_puissance")
_config("boiler.binary_source", "Boiler", CONF_BOILER_BINARY, "binary_sensor.boiler")
_native("boiler.temperature", "Boiler", "temperature_boiler")
_native("boiler.resistance_temperature", "Boiler", "temperature_resistance_boiler")
_native("boiler.safety", "Boiler", "securite_thermique_boiler")
_native("boiler.safety_source", "Boiler", "source_securite_thermique_boiler")
_native("boiler.power", "Boiler", "puissance_boiler")
_native("boiler.volume", "Boiler", "boiler_volume")
_native("boiler.element_power", "Boiler", "boiler_puissance_resistance")
_native("boiler.cold_water_temp", "Boiler", "boiler_temperature_eau_froide")
_native("boiler.thermal_energy_missing", "Boiler", "boiler_energie_thermique_manquante")
_native("boiler.heating_duration", "Boiler", "boiler_duree_chauffe_estimee")
_native("boiler.thermal_capacity_comfort", "Boiler", "boiler_capacite_thermique_confort")
_native("boiler.physical", "Boiler", "boiler_physique")
_native("boiler.demand", "Boiler", "demande_boiler")
_native("boiler.origin", "Boiler", "origine_boiler")
_native("boiler.execution_status", "Boiler", "execution_status")
_native("boiler.execution_command", "Boiler", "execution_command")
_native("boiler.execution_failure", "Boiler", "execution_failure_reason")
_native("boiler.execution_retries", "Boiler", "execution_retries")
_native("boiler.enabled", "Boiler", "boiler_enabled")
_native("boiler.allow_hc", "Boiler", "boiler_allow_hc")
_native("boiler.user_start", "Boiler", "boiler_demarrage_utilisateur")
_native("boiler.user_stop", "Boiler", "boiler_arret_utilisateur")
_native("boiler.user_auto", "Boiler", "boiler_retour_automatique")
_native("boiler.user_override", "Boiler", "boiler_override_utilisateur")

# Machines historiques + extensibles (les extensibles sont ajoutées dynamiquement au snapshot du registre).
_config("machines.washer.switch", "Machines", CONF_WASHER_SOCKET, "switch.lave_linge_prise_1")
_config("machines.washer.cycle", "Machines", CONF_WASHER_CYCLE, "input_boolean.lave_linge_en_cours")
_config("machines.dryer.switch", "Machines", CONF_DRYER_SOCKET, "switch.seche_linge_prise_1")
_config("machines.dryer.cycle", "Machines", CONF_DRYER_CYCLE, "input_boolean.seche_linge_en_cours")
_config("machines.dishwasher.switch", "Machines", CONF_DISHWASHER_SOCKET, "switch.lave_vaisselle_prise_1")
_config("machines.dishwasher.cycle", "Machines", CONF_DISHWASHER_CYCLE, "input_boolean.lave_vaisselle_en_cours")
_native("machines.window", "Machines", "fenetre_machines")
_native("machines.protected", "Machines", "machine_protegee_active")

# Tarification
_native("pricing.regime", "Tarification", "regime_tarifaire", "select.foxcat_energy_tarification_regime_tarifaire")
_native("pricing.dynamic_structure", "Tarification", "structure_dynamique")
_native("pricing.price_source", "Tarification", "source_prix")
_native("pricing.tariff_structure", "Tarification", "structure_tarifaire")
_native("pricing.price_analyzer", "Tarification", "price_analyzer_v2")
_native("machines.flexible_planner", "Machines", "planificateur_charges_flexibles")
_native("diagnostic.engine_version", "Diagnostic", "version_moteur")
_native("diagnostic.dashboard_version", "Diagnostic", "version_dashboard_active")
_native("diagnostic.dashboard_select", "Diagnostic", "dashboard_version")
_native("pricing.network_policy", "Tarification", "politique_reseau", "select.foxcat_energy_tarification_politique_reseau")

for _setting_key in NUMBER_DEFINITIONS:
    _native(f"settings.{_setting_key}", "Technique", _setting_key)
for _setting_key in SWITCH_DEFINITIONS:
    _native(f"settings.{_setting_key}", "Technique", _setting_key)
for _setting_key in TIME_SETTING_KEYS:
    _native(f"settings.time.{_setting_key}", "Technique", f"heure_{_setting_key}")
_native("pricing.current", "Tarification", "prix_actuel")
_native("pricing.next", "Tarification", "prix_suivant")
_native("pricing.injection", "Tarification", "prix_injection")
_native("pricing.period", "Tarification", "periode_tarifaire")
_native("pricing.status", "Tarification", "statut_prix")
_native("pricing.active_buy", "Tarification", "prix_achat_actif")
_native("pricing.next_buy", "Tarification", "prix_achat_suivant")
_native("pricing.dynamic_curve_position", "Tarification", "position_courbe_dynamique")
_native("pricing.dynamic_curve_rank", "Tarification", "rang_courbe_dynamique")
_native("pricing.dynamic_curve_trend", "Tarification", "tendance_courbe_dynamique")
_native("pricing.active_label", "Tarification", "libelle_prix_actif")
_native("pricing.next_label", "Tarification", "libelle_prix_suivant")
_native("pricing.export_sign_convention", "Tarification", "convention_prix_reinjection")
_native("pricing.cost_today", "Tarification", "bilan_cout_reseau_jour")
_native("pricing.export_value_today", "Tarification", "bilan_valeur_injection_jour")
_native("pricing.export_revenue_today", "Tarification", "bilan_revenu_injection_jour")
_native("pricing.export_cost_today", "Tarification", "bilan_cout_injection_jour")
_native("pricing.net_today", "Tarification", "bilan_cout_net_jour")
_native("pricing.solar_gain_today", "Tarification", "bilan_gain_solaire_jour")
_native("pricing.economic_decision", "Tarification", "decision_economique_ems")
_native("pricing.predictive_enabled", "Tarification", "predictive_pricing_enabled", "switch.foxcat_predictive_pricing_enabled")
_native("pricing.solar_forecast_arbitrage", "Tarification", "solar_forecast_arbitrage", "switch.foxcat_solar_forecast_arbitrage")
_native("pricing.financial_status", "Tarification", "etat_financier_ems")
_native("pricing.financial_detail", "Tarification", "detail_financier_ems")
_native("pricing.economic_best_future", "Tarification", "economique_meilleur_prix_futur")
_native("pricing.economic_best_slot", "Tarification", "economique_meilleur_creneau")
_native("pricing.economic_saving", "Tarification", "economique_economie_potentielle")
# V1.6.159 — Day-Ahead Dynamic uniquement.
_native("pricing.day_ahead.threshold", "Tarification", "dynamic_favorable_position_pct")
_native("pricing.day_ahead.peak_threshold", "Tarification", "dynamic_high_position_pct")
_native("pricing.day_ahead.favorable", "Tarification", "fenetre_prix_favorable_day_ahead")
_native("pricing.day_ahead.plan", "Tarification", "day_ahead_plan")
_native("pricing.day_ahead.next_valley", "Tarification", "day_ahead_prochain_creux")
_native("pricing.day_ahead.next_peak", "Tarification", "day_ahead_prochain_pic")
_native("pricing.day_ahead.horizon", "Tarification", "day_ahead_horizon")
_native("accounting.dynamic.import_today", "Tarification", "bilan_dynamic_import_jour")
_native("accounting.dynamic.export_today", "Tarification", "bilan_dynamic_export_jour")
_native("accounting.dynamic.import_cost_today", "Tarification", "bilan_dynamic_cout_achat_jour")
_native("accounting.dynamic.export_revenue_today", "Tarification", "bilan_dynamic_revenu_injection_jour")
_native("accounting.dynamic.export_cost_today", "Tarification", "bilan_dynamic_cout_injection_jour")
_native("accounting.dynamic.net_cost_today", "Tarification", "bilan_dynamic_cout_net_jour")
_native("accounting.hphc.hp.import_today", "Tarification", "bilan_hp_import_jour")
_native("accounting.hphc.hp.export_today", "Tarification", "bilan_hp_export_jour")
_native("accounting.hphc.hc.import_today", "Tarification", "bilan_hc_import_jour")
_native("accounting.hphc.hc.export_today", "Tarification", "bilan_hc_export_jour")
_config("pricing.source.current", "Tarification", CONF_PRICE_CURRENT, "sensor.luminus_luminus_dynamic_wallonia_prix_actuel")
_config("pricing.source.next", "Tarification", CONF_PRICE_NEXT, "sensor.luminus_luminus_dynamic_wallonia_prix_heure_suivante")
_config("pricing.source.injection", "Tarification", CONF_PRICE_INJECTION, "sensor.luminus_luminus_dynamic_wallonia_prix_d_injection")
_config("pricing.source.min_today", "Tarification", CONF_PRICE_MIN_TODAY, "sensor.luminus_luminus_dynamic_wallonia_minimum_aujourd_hui")
_config("pricing.source.max_today", "Tarification", CONF_PRICE_MAX_TODAY, "sensor.luminus_luminus_dynamic_wallonia_maximum_aujourd_hui")
_config("pricing.source.avg_today", "Tarification", CONF_PRICE_AVG_TODAY, "sensor.luminus_luminus_dynamic_wallonia_moyenne_aujourd_hui")
_config("pricing.source.min_tomorrow", "Tarification", CONF_PRICE_MIN_TOMORROW, "sensor.luminus_luminus_dynamic_wallonia_minimum_demain")
_config("pricing.source.max_tomorrow", "Tarification", CONF_PRICE_MAX_TOMORROW, "sensor.luminus_luminus_dynamic_wallonia_maximum_demain")
_config("pricing.source.avg_tomorrow", "Tarification", CONF_PRICE_AVG_TOMORROW, "sensor.luminus_luminus_dynamic_wallonia_moyenne_demain")
_config("pricing.source.hp", "Tarification", CONF_TARIFF_HP_PRICE_SENSOR, "sensor.luminus_luminus_comfyflex_wallonia_prix_heures_pleines_jour")
_config("pricing.source.hc", "Tarification", CONF_TARIFF_HC_PRICE_SENSOR, "sensor.luminus_luminus_comfyflex_wallonia_prix_heures_creuses_nuit")
_config("pricing.source.fixed_injection", "Tarification", CONF_TARIFF_FIXED_INJECTION_PRICE_SENSOR, "sensor.luminus_luminus_comfyflex_wallonia_prix_d_injection")
_config("pricing.source.forecast_import", "Tarification", CONF_PRICE_FORECAST_IMPORT)
_config("pricing.source.forecast_export", "Tarification", CONF_PRICE_FORECAST_EXPORT)
_config("pricing.source.tomorrow_available", "Tarification", CONF_PRICE_TOMORROW_AVAILABLE, "binary_sensor.luminus_luminus_dynamic_wallonia_prix_de_demain_disponibles")

# Métronome
_native("metronome.status", "Métronome", "metronome_statut")
_native("metronome.source", "Métronome", "metronome_source")
_native("metronome.active_sensor", "Métronome", "metronome_capteur_actif")
_native("metronome.last_pulse", "Métronome", "metronome_dernier_battement")
_native("metronome.counter", "Métronome", "metronome_compteur")
_native("metronome.counter_date", "Métronome", "metronome_date_compteur")
_native("metronome.last_daily_reset", "Métronome", "metronome_dernier_reset")
_native("metronome.previous_day_pulses", "Métronome", "metronome_battements_hier")
_native("metronome.previous_day_frames", "Métronome", "metronome_trames_hier")
_native("metronome.previous_day_messages", "Métronome", "metronome_messages_hier")
_native("metronome.period", "Métronome", "metronome_periode")
_native("metronome.reason", "Métronome", "metronome_raison")

# Diagnostic
_native("diagnostic.registry", "Diagnostic", "registre_entites")
_native("diagnostic.button", "Diagnostic", "diagnostic")
_native("diagnostic.reset", "Diagnostic", "reinitialiser_cycle")
_native("diagnostic.dashboard_regenerate", "Diagnostic", "regenerer_dashboard")
_native("diagnostic.legacy_conflict", "Diagnostic", "conflit_legacy")
_native("diagnostic.high_load", "Diagnostic", "haute_consommation_active")

# Prévisions solaires / IA restent accessibles au registre. Les rôles
# ems.forecast.* sont conservés pour compatibilité avec les dashboards existants.
_config("ems.forecast.ai_task", "EMS", CONF_AI_TASK)
_config("ems.forecast.now", "EMS", CONF_FORECAST_NOW)
_config("ems.forecast.this_hour", "EMS", CONF_FORECAST_THIS_HOUR)
_config("ems.forecast.next_hour", "EMS", CONF_FORECAST_NEXT_HOUR)
_config("ems.forecast.today", "EMS", CONF_FORECAST_TODAY)
_config("ems.forecast.remaining_today", "EMS", CONF_FORECAST_REMAINING_TODAY)
_config("ems.forecast.1h", "EMS", CONF_FORECAST_1H)
_config("ems.forecast.12h", "EMS", CONF_FORECAST_12H)
_config("ems.forecast.24h", "EMS", CONF_FORECAST_24H)
_config("ems.forecast.peak_today", "EMS", CONF_FORECAST_PEAK_TODAY)
_config("ems.forecast.tomorrow", "EMS", CONF_FORECAST_TOMORROW)
_config("ems.forecast.peak_tomorrow", "EMS", CONF_FORECAST_PEAK_TOMORROW)


# Liaisons legacy du dashboard historique. Elles restent centralisées ici;
# aucune carte ne référence directement ces entity_id en V1.6.0.
_literal('legacy.binary_sensor_boiler_physique', 'Boiler', 'binary_sensor.boiler_physique')
_literal('legacy.binary_sensor_lave_linge', 'Machines', 'binary_sensor.lave_linge')
_literal('legacy.binary_sensor_lave_linge_en_cours', 'Machines', 'binary_sensor.lave_linge_en_cours')
_literal('legacy.binary_sensor_lave_vaisselle', 'Machines', 'binary_sensor.lave_vaisselle')
_literal('legacy.binary_sensor_lave_vaisselle_en_cours', 'Machines', 'binary_sensor.lave_vaisselle_en_cours')
_literal('legacy.binary_sensor_seche_linge', 'Machines', 'binary_sensor.seche_linge')
_literal('legacy.binary_sensor_seche_linge_en_cours', 'Machines', 'binary_sensor.seche_linge_en_cours')
_literal('legacy.climate_chambre_natheo_2', 'Machines', 'climate.chambre_natheo_2')
_literal('legacy.climate_chambre_parentale', 'Machines', 'climate.chambre_parentale')
_literal('legacy.climate_chauffage_sol_2', 'Machines', 'climate.chauffage_sol_2')
_literal('legacy.climate_poele_a_pellet', 'Machines', 'climate.poele_a_pellet')
_literal('legacy.climate_salle_de_bain_2', 'Machines', 'climate.salle_de_bain_2')
_literal('legacy.climate_salon_2', 'Machines', 'climate.salon_2')
_literal('legacy.input_boolean_emi_active', 'Diagnostic', 'input_boolean.emi_active')
_literal('legacy.input_boolean_ems_2_afficher_reglages', 'EMS', 'input_boolean.ems_2_afficher_reglages')
_literal('legacy.input_boolean_ems_boiler', 'Boiler', 'input_boolean.ems_boiler')
_literal('legacy.input_boolean_ems_head_lateral', 'EMS', 'input_boolean.ems_head_lateral')
_literal('legacy.input_boolean_ems_head_menu', 'EMS', 'input_boolean.ems_head_menu')
_literal('legacy.input_boolean_ems_lave_linge', 'Machines', 'input_boolean.ems_lave_linge')
_literal('legacy.input_boolean_ems_lave_vaisselle', 'Machines', 'input_boolean.ems_lave_vaisselle')
_literal('legacy.input_boolean_ems_prevision_solaire_disponible', 'EMS', 'input_boolean.ems_prevision_solaire_disponible')
_literal('legacy.input_boolean_ems_regulation_ack', 'EMS', 'input_boolean.ems_regulation_ack')
_literal('legacy.input_boolean_ems_seche_linge', 'Machines', 'input_boolean.ems_seche_linge')
_literal('legacy.input_boolean_repassage_en_cours', 'Machines', 'input_boolean.repassage_en_cours')
_literal('legacy.input_number_ems_ack_error', 'EMS', 'input_number.ems_ack_error')
_literal('legacy.input_number_ems_ack_tolerance', 'EMS', 'input_number.ems_ack_tolerance')
_literal('legacy.input_number_ems_action_reference_grid', 'EMS', 'input_number.ems_action_reference_grid')
_literal('legacy.input_number_ems_agressivite_score', 'EMS', 'input_number.ems_agressivite_score')
_literal('legacy.input_number_ems_boiler_cycle_min_secondes', 'Boiler', 'input_number.ems_boiler_cycle_min_secondes')
_literal('legacy.input_number_ems_boiler_temp_normal', 'Boiler', 'input_number.ems_boiler_temp_normal')
_literal('legacy.input_number_ems_couverture_solaire_min_dynamique', 'EMS', 'input_number.ems_couverture_solaire_min_dynamique')
_literal('legacy.input_number_ems_grid_expected', 'EMS', 'input_number.ems_grid_expected')
_literal('legacy.input_number_ems_grid_t0', 'EMS', 'input_number.ems_grid_t0')
_literal('legacy.input_number_ems_import_boiler_max_dynamique', 'Boiler', 'input_number.ems_import_boiler_max_dynamique')
_literal('legacy.input_number_ems_pending_delta', 'EMS', 'input_number.ems_pending_delta')
_literal('legacy.input_number_ems_prevision_solaire_confiance', 'EMS', 'input_number.ems_prevision_solaire_confiance')
_literal('legacy.input_number_ems_solaire_confiance_minimum', 'EMS', 'input_number.ems_solaire_confiance_minimum')
_literal('legacy.input_number_ems_solaire_duree_minimum', 'EMS', 'input_number.ems_solaire_duree_minimum')
_literal('legacy.input_number_ems_solaire_seuil_bon', 'EMS', 'input_number.ems_solaire_seuil_bon')
_literal('legacy.input_number_ems_solaire_seuil_fort', 'EMS', 'input_number.ems_solaire_seuil_fort')
_literal('legacy.input_number_ems_solaire_seuil_minimum', 'EMS', 'input_number.ems_solaire_seuil_minimum')
_literal('legacy.input_number_ems_solaire_seuil_possible', 'EMS', 'input_number.ems_solaire_seuil_possible')
_literal('legacy.input_number_ems_stability_tolerance', 'EMS', 'input_number.ems_stability_tolerance')
_literal('legacy.input_number_seuil_energie_prix_kwh', 'Onduleur', 'input_number.seuil_energie_prix_kwh')
_literal('legacy.input_select_ems_ack_status', 'EMS', 'input_select.ems_ack_status')
_literal('legacy.input_select_ems_boiler_demande', 'Boiler', 'input_select.ems_boiler_demande')
_literal('legacy.input_select_ems_mode', 'EMS', 'input_select.ems_mode')
_literal('legacy.input_select_ems_prevision_solaire_potentiel', 'EMS', 'input_select.ems_prevision_solaire_potentiel')
_literal('legacy.input_select_ems_regulation_phase', 'EMS', 'input_select.ems_regulation_phase')
_literal('legacy.input_text_ems_agressivite_raison', 'EMS', 'input_text.ems_agressivite_raison')
_literal('legacy.input_text_ems_boiler_origine', 'Boiler', 'input_text.ems_boiler_origine')
_literal('legacy.input_text_ems_last_reason', 'EMS', 'input_text.ems_last_reason')
_literal('legacy.input_text_ems_pending_action', 'EMS', 'input_text.ems_pending_action')
_literal('legacy.input_text_ems_prevision_solaire_debut', 'EMS', 'input_text.ems_prevision_solaire_debut')
_literal('legacy.input_text_ems_prevision_solaire_fin', 'EMS', 'input_text.ems_prevision_solaire_fin')
_literal('legacy.input_text_ems_prevision_solaire_raison', 'EMS', 'input_text.ems_prevision_solaire_raison')
_literal('legacy.input_text_ems_prevision_solaire_tendance', 'EMS', 'input_text.ems_prevision_solaire_tendance')
_literal('legacy.select_central_mode', 'Diagnostic', 'select.central_mode')
_literal('legacy.sensor_boiler_energy_daily', 'Boiler', 'sensor.boiler_energy_daily')
_literal('legacy.sensor_boiler_energy_daily_cost', 'Boiler', 'sensor.boiler_energy_daily_cost')
_literal('legacy.sensor_boiler_puissance_hc_energy', 'Boiler', 'sensor.boiler_puissance_hc_energy')
_literal('legacy.sensor_boiler_puissance_hp_energy', 'Boiler', 'sensor.boiler_puissance_hp_energy')
_literal('legacy.sensor_chambre_natheo_temperature_slope', 'Diagnostic', 'sensor.chambre_natheo_temperature_slope')
_literal('legacy.sensor_chambre_parentale_temperature_slope', 'Diagnostic', 'sensor.chambre_parentale_temperature_slope')
_literal('legacy.sensor_consommation_jour', 'Énergie', 'sensor.consommation_jour')
_literal('legacy.sensor_consommation_reelle_maison', 'Énergie', 'sensor.consommation_reelle_maison')
_literal('legacy.sensor_garage_boiler_sonde_temperature_pente_boiler', 'Boiler', 'sensor.garage_boiler_sonde_temperature_pente_boiler')
_literal('legacy.sensor_homefoxcat_load_autre', 'Diagnostic', 'sensor.homefoxcat_load_autre')
_literal('legacy.sensor_homefoxcat_total_consumption_today', 'Énergie', 'sensor.homefoxcat_total_consumption_today')
_literal('legacy.sensor_homefoxcat_total_production_today', 'Énergie', 'sensor.homefoxcat_total_production_today')
_literal('legacy.sensor_lave_linge_cout_journalier', 'Machines', 'sensor.lave_linge_cout_journalier')
_literal('legacy.sensor_lave_linge_energie_journaliere', 'Machines', 'sensor.lave_linge_energie_journaliere')
_literal('legacy.sensor_lave_linge_energy_daily', 'Machines', 'sensor.lave_linge_energy_daily')
_literal('legacy.sensor_lave_linge_energy_daily_cost', 'Machines', 'sensor.lave_linge_energy_daily_cost')
_literal('legacy.sensor_lave_linge_hc_energy', 'Machines', 'sensor.lave_linge_hc_energy')
_literal('legacy.sensor_lave_linge_hp_energy', 'Machines', 'sensor.lave_linge_hp_energy')
_literal('legacy.sensor_lave_linge_power', 'Machines', 'sensor.lave_linge_power')
_literal('legacy.sensor_lave_linge_puissance', 'Machines', 'sensor.lave_linge_puissance')
_literal('legacy.sensor_lave_linge_puissance_hc_energy', 'Machines', 'sensor.lave_linge_puissance_hc_energy')
_literal('legacy.sensor_lave_linge_puissance_hp_energy', 'Machines', 'sensor.lave_linge_puissance_hp_energy')
_literal('legacy.sensor_lave_vaisselle_cout_journalier', 'Machines', 'sensor.lave_vaisselle_cout_journalier')
_literal('legacy.sensor_lave_vaisselle_energie_journaliere', 'Machines', 'sensor.lave_vaisselle_energie_journaliere')
_literal('legacy.sensor_lave_vaisselle_energy_daily', 'Machines', 'sensor.lave_vaisselle_energy_daily')
_literal('legacy.sensor_lave_vaisselle_energy_daily_cost', 'Machines', 'sensor.lave_vaisselle_energy_daily_cost')
_literal('legacy.sensor_lave_vaisselle_hc_energy', 'Machines', 'sensor.lave_vaisselle_hc_energy')
_literal('legacy.sensor_lave_vaisselle_hp_energy', 'Machines', 'sensor.lave_vaisselle_hp_energy')
_literal('legacy.sensor_lave_vaisselle_power', 'Machines', 'sensor.lave_vaisselle_power')
_literal('legacy.sensor_lave_vaisselle_puissance', 'Machines', 'sensor.lave_vaisselle_puissance')
_literal('legacy.sensor_lave_vaisselle_puissance_hc_energy', 'Machines', 'sensor.lave_vaisselle_puissance_hc_energy')
_literal('legacy.sensor_lave_vaisselle_puissance_hp_energy', 'Machines', 'sensor.lave_vaisselle_puissance_hp_energy')
_literal('legacy.sensor_luminus_luminus', 'Tarification', 'sensor.luminus_luminus_')
_literal('legacy.sensor_nord_pool_be_current_price', 'Onduleur', 'sensor.nord_pool_be_current_price')
_literal('legacy.sensor_pourcentage_solaire_consomme', 'Énergie', 'sensor.pourcentage_solaire_consomme')
_literal('legacy.sensor_prix_electricite_actif_aiesh_tvac', 'Onduleur', 'sensor.prix_electricite_actif_aiesh_tvac')
_literal('legacy.sensor_prix_electricite_client_aiesh_tvac', 'Onduleur', 'sensor.prix_electricite_client_aiesh_tvac')
_literal('legacy.sensor_reinjection_jour', 'Énergie', 'sensor.reinjection_jour')
_literal('legacy.sensor_retourne_au_reseau', 'Énergie', 'sensor.retourne_au_reseau')
_literal('legacy.sensor_salle_de_bain_temperature_slope', 'Diagnostic', 'sensor.salle_de_bain_temperature_slope')
_literal('legacy.sensor_seche_linge_cout_journalier', 'Machines', 'sensor.seche_linge_cout_journalier')
_literal('legacy.sensor_seche_linge_energie_journaliere', 'Machines', 'sensor.seche_linge_energie_journaliere')
_literal('legacy.sensor_seche_linge_energy_daily', 'Machines', 'sensor.seche_linge_energy_daily')
_literal('legacy.sensor_seche_linge_energy_daily_cost', 'Machines', 'sensor.seche_linge_energy_daily_cost')
_literal('legacy.sensor_seche_linge_hc_energy', 'Machines', 'sensor.seche_linge_hc_energy')
_literal('legacy.sensor_seche_linge_hp_energy', 'Machines', 'sensor.seche_linge_hp_energy')
_literal('legacy.sensor_seche_linge_power', 'Machines', 'sensor.seche_linge_power')
_literal('legacy.sensor_seche_linge_puissance', 'Machines', 'sensor.seche_linge_puissance')
_literal('legacy.sensor_seche_linge_puissance_hc_energy', 'Machines', 'sensor.seche_linge_puissance_hc_energy')
_literal('legacy.sensor_seche_linge_puissance_hp_energy', 'Machines', 'sensor.seche_linge_puissance_hp_energy')
_literal('legacy.sensor_solar_production_forecast_heure_de_pointe_de_puissance_la_plus_elevee_aujourd_hui', 'EMS', 'sensor.solar_production_forecast_heure_de_pointe_de_puissance_la_plus_elevee_aujourd_hui')
_literal('legacy.sensor_solar_production_forecast_production_d_electricite_estimee_maintenant', 'EMS', 'sensor.solar_production_forecast_production_d_electricite_estimee_maintenant')
_literal('legacy.sensor_solar_production_forecast_production_d_energie_estimee_aujourd_hui', 'EMS', 'sensor.solar_production_forecast_production_d_energie_estimee_aujourd_hui')
_literal('legacy.sensor_solar_production_forecast_production_d_energie_estimee_cette_heure', 'EMS', 'sensor.solar_production_forecast_production_d_energie_estimee_cette_heure')
_literal('legacy.sensor_solar_production_forecast_production_d_energie_estimee_en_12_heures', 'EMS', 'sensor.solar_production_forecast_production_d_energie_estimee_en_12_heures')
_literal('legacy.sensor_solar_production_forecast_production_d_energie_estimee_heure_suivante', 'EMS', 'sensor.solar_production_forecast_production_d_energie_estimee_heure_suivante')
_literal('legacy.sensor_solar_production_forecast_production_d_energie_estimee_restante_aujourd_hui', 'EMS', 'sensor.solar_production_forecast_production_d_energie_estimee_restante_aujourd_hui')
_literal('legacy.sensor_t_h_sensor_with_external_probe_probe_temperature', 'Diagnostic', 'sensor.t_h_sensor_with_external_probe_probe_temperature')
_literal('legacy.sensor_temperature_boiler_2sondes_moyenne', 'Boiler', 'sensor.temperature_boiler_2sondes_moyenne')
_literal('legacy.sensor_xxx', 'Diagnostic', 'sensor.xxx')
_literal('legacy.switch_boiler_prise_1', 'Boiler', 'switch.boiler_prise_1')

_TOKEN_RE = re.compile(r"\[\[foxcat:([a-zA-Z0-9_.-]+)\]\]")


def literal_role_for(entity_id: str) -> str:
    """Return a deterministic semantic fallback role for a legacy dashboard entity."""
    safe = re.sub(r"[^a-z0-9]+", "_", entity_id.lower()).strip("_")
    return f"legacy.{safe}"


def register_legacy_literal(entity_id: str, section: str = "Diagnostic") -> str:
    role = literal_role_for(entity_id)
    if role not in BINDINGS:
        _literal(role, section, entity_id)
    return role


def _native_entities_by_key(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, str]:
    registry = er.async_get(hass)
    result: dict[str, str] = {}
    for item in er.async_entries_for_config_entry(registry, entry.entry_id):
        unique_id = str(item.unique_id or "")
        prefix = f"{entry.entry_id}_"
        if unique_id.startswith(prefix):
            result[unique_id[len(prefix):]] = item.entity_id
    return result


def resolve_registry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    config: dict[str, Any],
) -> dict[str, str]:
    """Resolve all FoxCat roles to the current HA entity_ids.

    Native FoxCat entities are resolved from Home Assistant's entity registry by
    unique_id, so user renames and automatic suffixes do not break the generated
    dashboard. Config-bound physical entities come from the ConfigEntry.
    """
    native = _native_entities_by_key(hass, entry)
    resolved: dict[str, str] = {}

    for role, binding in BINDINGS.items():
        entity_id: str | None = None
        if binding.kind == "native" and binding.key:
            entity_id = native.get(binding.key)
        elif binding.kind == "config" and binding.key:
            value = config.get(binding.key)
            if value:
                entity_id = str(value)
        elif binding.kind == "literal":
            entity_id = binding.fallback_entity_id

        if not entity_id:
            entity_id = binding.fallback_entity_id
        if entity_id:
            resolved[role] = entity_id

    # Boutons utilisateurs des machines extensibles : rôles déterministes
    # construits à partir des unique_id natifs FoxCat.
    try:
        from .machines import machine_definitions
        for machine in machine_definitions(config):
            safe_key = machine.machine_id.replace(" ", "_").lower()
            start_key = f"machine_{safe_key}_demarrage_utilisateur"
            stop_key = f"machine_{safe_key}_arret_utilisateur"
            if native.get(start_key):
                resolved[f"machines.{machine.machine_id}.user_start"] = native[start_key]
            if native.get(stop_key):
                resolved[f"machines.{machine.machine_id}.user_stop"] = native[stop_key]
            day_ahead_key = f"day_ahead_{safe_key}_plan"
            if native.get(day_ahead_key):
                resolved[f"machines.{machine.machine_id}.day_ahead_plan"] = native[day_ahead_key]

            # V1.6.154 : rôles dédiés Machine Learning, distincts des capteurs
            # opérationnels Machines. Aucun de ces rôles ne pilote l'EMS.
            ml_roles = {
                "cycles": f"apprentissage_{safe_key}_cycles",
                "collecting": f"apprentissage_{safe_key}_collecte",
                "average_energy": f"apprentissage_{safe_key}_energie_moyenne",
                "average_duration": f"apprentissage_{safe_key}_duree_moyenne",
            }
            for suffix, native_key in ml_roles.items():
                if native.get(native_key):
                    resolved[f"machine_learning.{machine.machine_id}.{suffix}"] = native[native_key]
    except Exception:
        pass

    return resolved


def render_dashboard_template(template: str, registry: dict[str, str]) -> tuple[str, list[str]]:
    unresolved: set[str] = set()

    def repl(match: re.Match[str]) -> str:
        role = match.group(1)
        entity_id = registry.get(role)
        if entity_id:
            return entity_id
        unresolved.add(role)
        # Keep a visible invalid entity reference instead of silently binding a
        # wrong source. Home Assistant will mark the card/entity unavailable.
        return f"sensor.foxcat_registry_unresolved_{re.sub(r'[^a-z0-9_]', '_', role.lower())}"

    return _TOKEN_RE.sub(repl, template), sorted(unresolved)


def registry_diagnostics(hass: HomeAssistant, entry: ConfigEntry, config: dict[str, Any]) -> dict[str, Any]:
    resolved = resolve_registry(hass, entry, config)
    sections: dict[str, dict[str, str]] = {section: {} for section in OFFICIAL_SECTION_ORDER}
    unresolved: list[str] = []
    unavailable: list[str] = []
    for role, binding in BINDINGS.items():
        entity_id = resolved.get(role)
        if entity_id:
            sections.setdefault(binding.section, {})[role] = entity_id
            if hass.states.get(entity_id) is None:
                unavailable.append(role)
        else:
            unresolved.append(role)
    return {
        "order": list(OFFICIAL_SECTION_ORDER),
        "resolved_count": len(resolved),
        "binding_count": len(BINDINGS),
        "unresolved": sorted(unresolved),
        "unavailable": sorted(unavailable),
        "sections": sections,
    }
