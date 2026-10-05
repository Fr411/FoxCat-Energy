from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower, UnitOfTemperature, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, CONF_GRID_SIGNED_SENSOR, CONF_PV_SENSOR
from .coordinator import FoxCatEnergyCoordinator
from .entity import FoxCatEntity
from .registry import registry_diagnostics


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    c: FoxCatEnergyCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        FoxCatValueSensor(c, "modele_sources", "Modèle des sources énergétiques", "mdi:source-branch", "sources", lambda d: "2 SOURCES SIGNÉES" if c.config.get(CONF_GRID_SIGNED_SENSOR) else "COMPATIBILITÉ LEGACY"),
        FoxCatValueSensor(c, "source_reseau", "Source puissance réseau active", "mdi:transmission-tower", "sources", lambda d: (d.get("metronome", {}).get("fallback_entity") if d.get("metronome", {}).get("source") == "SECOURS" else d.get("metronome", {}).get("primary_entity")) or c.config.get(CONF_GRID_SIGNED_SENSOR) or "Legacy"),
        FoxCatValueSensor(c, "source_pv", "Source production photovoltaïque", "mdi:solar-power", "sources", lambda d: c.config.get(CONF_PV_SENSOR) or "Indisponible"),
        FoxCatValueSensor(c, "phase", "Phase de régulation", "mdi:state-machine", "ems", lambda d: d["core"]["phase"]),
        FoxCatValueSensor(c, "fsm_status", "Machine à états EMS • État", "mdi:state-machine", "ems", lambda d: d["core"].get("fsm_status", "INCONNU")),
        FoxCatNumericSensor(c, "fsm_transition_count", "Machine à états EMS • Transitions", "mdi:counter", "ems", lambda d: d["core"].get("fsm_transition_count", 0)),
        FoxCatValueSensor(c, "fsm_last_transition", "Machine à états EMS • Dernière transition", "mdi:swap-horizontal", "ems", lambda d: d["core"].get("fsm_last_transition", "AUCUNE")),
        FoxCatValueSensor(c, "fsm_last_transition_at", "Machine à états EMS • Dernière transition à", "mdi:clock-check-outline", "ems", lambda d: _iso(d["core"].get("fsm_last_transition_at"))),
        FoxCatValueSensor(c, "ack", "Validation d’exécution EMS", "mdi:check-decagram-outline", "ems", lambda d: d["core"]["ack"]),
        FoxCatValueSensor(c, "derniere_raison", "Dernière décision EMS", "mdi:information-outline", "ems", lambda d: d["core"]["last_reason"]),
        FoxCatValueSensor(c, "action_en_attente", "Action en attente", "mdi:progress-clock", "ems", lambda d: d["core"]["pending_action"]),
        FoxCatValueSensor(c, "demande_boiler", "Demande chauffe-eau", "mdi:water-boiler-auto", "boiler", lambda d: d["core"]["boiler_demand"]),
        FoxCatValueSensor(c, "origine_boiler", "Origine de la demande chauffe-eau", "mdi:source-branch", "boiler", lambda d: d["core"]["boiler_origin"]),
        FoxCatValueSensor(c, "boiler_override_utilisateur", "Boiler • Commande utilisateur", "mdi:account-cog-outline", "user_functions", lambda d: d["core"].get("boiler_user_override", "AUTO")),
        FoxCatValueSensor(c, "execution_status", "État d’exécution chauffe-eau", "mdi:progress-check", "boiler", lambda d: d["core"]["execution_status"]),
        FoxCatValueSensor(c, "execution_command", "Commande chauffe-eau vérifiée", "mdi:code-tags-check", "boiler", lambda d: d["core"]["execution_command"]),
        FoxCatValueSensor(c, "execution_failure_reason", "Raison d'échec d'exécution", "mdi:alert-circle-outline", "boiler", lambda d: d["core"]["execution_failure_reason"] or "Aucune"),
        FoxCatNumericSensor(c, "execution_retries", "Tentatives d'exécution", "mdi:counter", "boiler", lambda d: d["core"]["execution_retries"]),
        FoxCatNumericSensor(c, "erreur_ack", "Erreur ACK", "mdi:delta", "ems", lambda d: d["core"]["ack_error"], UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatNumericSensor(c, "reseau_reference_action", "Réseau avant action", "mdi:transmission-tower", "ems", lambda d: d["core"]["action_reference_grid"], UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatNumericSensor(c, "reseau_attendu", "Réseau attendu", "mdi:transmission-tower", "ems", lambda d: d["core"]["grid_expected"], UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatNumericSensor(c, "variation_attendue", "Variation attendue", "mdi:swap-vertical", "ems", lambda d: d["core"]["pending_delta"], UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatNumericSensor(c, "production_pv", "Puissance de production photovoltaïque", "mdi:solar-power", "energy", lambda d: d["snapshot"].pv_w, UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatNumericSensor(c, "consommation_maison", "Puissance de consommation maison", "mdi:home-lightning-bolt", "energy", lambda d: d["snapshot"].house_w, UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatValueSensor(c, "statut_delestage", "Statut délestage haute consommation", "mdi:home-lightning-bolt-outline", "ems", lambda d: d["load_shed"].get("reason")),
        FoxCatNumericSensor(c, "reinjection_reseau", "Puissance réinjectée au réseau", "mdi:transmission-tower-export", "energy", lambda d: d["snapshot"].export_w, UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatNumericSensor(c, "prelevement_reseau", "Puissance prélevée au réseau", "mdi:transmission-tower-import", "energy", lambda d: d["snapshot"].import_w, UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatNumericSensor(c, "reseau_signe", "Puissance réseau signée (+ prélèvement / − réinjection)", "mdi:transmission-tower", "energy", lambda d: d["snapshot"].import_w - d["snapshot"].export_w, UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatNumericSensor(c, "balance_reseau", "Flux réseau interne (export positif)", "mdi:transmission-tower", "diagnostic", lambda d: d["snapshot"].grid_net_w, UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatValueSensor(c, "metronome_statut", "Statut métronome réseau", "mdi:metronome", "metronome", lambda d: d["metronome"].get("status")),
        FoxCatValueSensor(c, "metronome_source", "Source métronome réseau", "mdi:source-branch-sync", "metronome", lambda d: d["metronome"].get("source")),
        FoxCatValueSensor(c, "metronome_capteur_actif", "Capteur actif du métronome", "mdi:access-point-network", "metronome", lambda d: d["metronome"].get("primary_entity") if d["metronome"].get("source") == "PRINCIPAL" else d["metronome"].get("fallback_entity")),
        FoxCatValueSensor(c, "metronome_dernier_battement", "Dernier battement métronome", "mdi:clock-check-outline", "metronome", lambda d: _iso(d["metronome"].get("last_pulse_at"))),
        FoxCatNumericSensor(c, "metronome_compteur", "Compteur de battements métronome", "mdi:counter", "metronome", lambda d: d["metronome"].get("pulse_count")),
        FoxCatValueSensor(c, "metronome_date_compteur", "Journée compteur métronome", "mdi:calendar-today", "metronome", lambda d: d["metronome"].get("counter_date", "—")),
        FoxCatValueSensor(c, "metronome_dernier_reset", "Dernier reset journalier", "mdi:backup-restore", "metronome", lambda d: _iso(d["metronome"].get("last_daily_reset_at"))),
        FoxCatNumericSensor(c, "metronome_battements_hier", "Battements métronome journée précédente", "mdi:counter", "metronome", lambda d: d["metronome"].get("previous_day_pulse_count", 0)),
        FoxCatNumericSensor(c, "metronome_trames_hier", "Trames réseau journée précédente", "mdi:counter", "metronome", lambda d: d["metronome"].get("previous_day_frame_count", 0)),
        FoxCatNumericSensor(c, "metronome_messages_hier", "Messages Energy Bus journée précédente", "mdi:counter", "metronome", lambda d: d["metronome"].get("previous_day_message_count", 0)),
        FoxCatNumericSensor(c, "metronome_periode", "Fenêtre Watchdog réseau", "mdi:timer-sync-outline", "metronome", lambda d: d["metronome"].get("period_s"), "s"),
        FoxCatValueSensor(c, "metronome_raison", "Diagnostic métronome réseau", "mdi:information-outline", "metronome", lambda d: d["metronome"].get("last_reason")),
        FoxCatNumericSensor(c, "temperature_boiler", "Température chauffe-eau", "mdi:thermometer-water", "boiler", lambda d: d["snapshot"].boiler_temp_c, UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
        FoxCatNumericSensor(c, "temperature_resistance_boiler", "Température résistance de sécurité", "mdi:thermometer-alert", "boiler", lambda d: d["snapshot"].raw.get("boiler_resistance_temp_c"), UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
        FoxCatValueSensor(c, "source_securite_thermique_boiler", "Source sécurité thermique", "mdi:shield-thermometer-outline", "boiler", lambda d: d["snapshot"].raw.get("boiler_safety_source", "REFERENCE")),
        FoxCatNumericSensor(c, "puissance_boiler", "Puissance chauffe-eau", "mdi:water-boiler", "boiler", lambda d: d["snapshot"].boiler_power_w, UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatNumericSensor(c, "boiler_volume", "Boiler • Volume", "mdi:water-boiler", "boiler", lambda d: d.get("boiler_thermal", {}).get("volume_l"), "L", suggested_object_id="foxcat_boiler_volume"),
        FoxCatNumericSensor(c, "boiler_puissance_resistance", "Boiler • Puissance nominale résistance", "mdi:flash", "boiler", lambda d: d.get("boiler_thermal", {}).get("element_power_w"), UnitOfPower.WATT, SensorDeviceClass.POWER, suggested_object_id="foxcat_boiler_puissance_resistance"),
        FoxCatNumericSensor(c, "boiler_temperature_eau_froide", "Boiler • Température eau froide réseau", "mdi:coolant-temperature", "boiler", lambda d: d.get("boiler_thermal", {}).get("cold_water_temp_c"), UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE, suggested_object_id="foxcat_boiler_temperature_eau_froide"),
        FoxCatNumericSensor(c, "boiler_energie_thermique_manquante", "Boiler • Énergie thermique manquante", "mdi:water-thermometer-outline", "boiler", lambda d: d.get("boiler_thermal", {}).get("energy_missing_kwh"), UnitOfEnergy.KILO_WATT_HOUR, suggested_object_id="foxcat_boiler_energie_thermique_manquante"),
        FoxCatNumericSensor(c, "boiler_duree_chauffe_estimee", "Boiler • Durée de chauffe estimée", "mdi:timer-heat-outline", "boiler", lambda d: d.get("boiler_thermal", {}).get("heating_duration_h"), "h", suggested_object_id="foxcat_boiler_duree_chauffe_estimee"),
        FoxCatNumericSensor(c, "boiler_temperature_estimee", "Boiler • Température thermique estimée", "mdi:thermometer-water", "boiler", lambda d: d.get("boiler_thermal", {}).get("estimated_temp_c"), UnitOfTemperature.CELSIUS, SensorDeviceClass.TEMPERATURE),
        FoxCatNumericSensor(c, "boiler_confiance_estimation", "Boiler • Confiance estimation", "mdi:shield-check-outline", "boiler", lambda d: d.get("boiler_thermal", {}).get("estimate_confidence_pct"), PERCENTAGE),
        FoxCatValueSensor(c, "boiler_etat_thermique", "Boiler • État thermique", "mdi:water-thermometer", "boiler", lambda d: d.get("boiler_thermal", {}).get("thermal_state", "INDISPONIBLE")),
        FoxCatNumericSensor(c, "boiler_capacite_thermique_confort", "Boiler • Capacité thermique confort", "mdi:water-boiler-auto", "boiler", lambda d: d.get("boiler_thermal", {}).get("thermal_capacity_comfort_kwh"), UnitOfEnergy.KILO_WATT_HOUR, suggested_object_id="foxcat_boiler_capacite_thermique_confort"),
        FoxCatNumericSensor(c, "puissance_onduleur_snapshot", "Puissance onduleur au dernier snapshot", "mdi:solar-power", "pri", lambda d: d["snapshot"].inverter_power_w, UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatNumericSensor(c, "pri_niveau_actuel", "Niveau de puissance PRI actuel", "mdi:solar-power-variant", "pri", lambda d: d["pri"]["current_level"], PERCENTAGE),
        FoxCatNumericSensor(c, "pri_niveau_cible", "Niveau de puissance PRI cible", "mdi:target", "pri", lambda d: d["pri"]["target_level"], PERCENTAGE),
        FoxCatValueSensor(c, "pri_code_rrcr", "Code RRCR", "mdi:code-binary", "pri", lambda d: d["pri"]["code"]),
        FoxCatValueSensor(c, "pri_direction", "Direction PRI", "mdi:arrow-up-down", "pri", lambda d: d["pri"]["direction"]),
        FoxCatValueSensor(c, "pri_ack_rrcr", "ACK RRCR", "mdi:electric-switch", "pri", lambda d: d["pri"]["ack_rrcr"]),
        FoxCatValueSensor(c, "pri_ack_onduleur", "ACK onduleur", "mdi:solar-power", "pri", lambda d: d["pri"]["ack_inverter"]),
        FoxCatValueSensor(c, "pri_ack_reseau", "ACK réseau", "mdi:transmission-tower", "pri", lambda d: d["pri"]["ack_grid"]),
        FoxCatValueSensor(c, "pri_derniere_raison", "Dernière décision PRI", "mdi:information-outline", "pri", lambda d: d["pri"]["last_reason"]),
        FoxCatNumericSensor(c, "pri_score_actuel", "Score PRI actuel", "mdi:scale-balance", "pri", lambda d: d["pri"]["score_current"]),
        FoxCatNumericSensor(c, "pri_score_cible", "Score PRI cible", "mdi:scale-balance", "pri", lambda d: d["pri"]["score_target"]),
        FoxCatNumericSensor(c, "pri_cible_maison", "Repère PRI selon consommation (diagnostic)", "mdi:home-percent-outline", "pri", lambda d: d["pri"]["house_target_level"], PERCENTAGE),
        FoxCatNumericSensor(c, "pri_charge_reseau_estimee", "Charge maison estimée par bilan réseau", "mdi:home-lightning-bolt-outline", "pri", lambda d: d["pri"].get("estimated_house_w"), UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatNumericSensor(c, "pri_puissance_pv_cible", "Puissance PV cible PRI", "mdi:solar-power", "pri", lambda d: d["pri"].get("target_pv_w"), UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatNumericSensor(c, "pri_import_prevu", "Import réseau prévu au palier cible", "mdi:transmission-tower-import", "pri", lambda d: d["pri"].get("predicted_import_w"), UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatNumericSensor(c, "pri_export_prevu", "Réinjection prévue au palier cible", "mdi:transmission-tower-export", "pri", lambda d: d["pri"].get("predicted_export_w"), UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatNumericSensor(c, "confiance_solaire", "Confiance solaire", "mdi:weather-sunny-alert", "solar", lambda d: d["solar"].confidence, PERCENTAGE),
        FoxCatValueSensor(c, "potentiel_solaire", "Potentiel solaire", "mdi:white-balance-sunny", "solar", lambda d: d["solar"].potential),
        FoxCatValueSensor(c, "tendance_solaire", "Tendance solaire", "mdi:trending-up", "solar", lambda d: d["solar"].trend),
        FoxCatValueSensor(c, "prevision_solaire_debut", "Début fenêtre solaire", "mdi:clock-start", "solar", lambda d: d["solar"].start),
        FoxCatValueSensor(c, "prevision_solaire_fin", "Fin fenêtre solaire", "mdi:clock-end", "solar", lambda d: d["solar"].end),
        FoxCatValueSensor(c, "prevision_solaire_raison", "Raison prévision solaire", "mdi:text-box-outline", "solar", lambda d: d["solar"].reason),
        FoxCatValueSensor(c, "prevision_solaire_brute", "Prévision solaire brute", "mdi:code-json", "solar", lambda d: d["solar"].raw),
        FoxCatNumericSensor(c, "prix_actuel", "Prix dynamique actuel", "mdi:cash", "pricing", lambda d: d["prices"].get("current"), "€/kWh"),
        FoxCatNumericSensor(c, "prix_suivant", "Prix dynamique heure suivante", "mdi:cash-clock", "pricing", lambda d: d["prices"].get("next"), "€/kWh"),
        FoxCatNumericSensor(c, "prix_injection", "Prix dynamique de réinjection brut", "mdi:cash-plus", "pricing", lambda d: d["prices"].get("injection"), "€/kWh"),
        FoxCatNumericSensor(c, "prix_heures_pleines", "Prix heures pleines (HP)", "mdi:cash-clock", "pricing", lambda d: d["prices"].get("hp_price"), "€/kWh"),
        FoxCatNumericSensor(c, "prix_heures_creuses", "Prix heures creuses (HC)", "mdi:cash-clock-outline", "pricing", lambda d: d["prices"].get("hc_price"), "€/kWh"),
        FoxCatNumericSensor(c, "prix_reinjection_fixe", "Prix fixe de réinjection", "mdi:transmission-tower-export", "pricing", lambda d: d["prices"].get("fixed_injection_price"), "€/kWh"),
        FoxCatValueSensor(c, "source_prix_hp", "Source prix heures pleines", "mdi:database-arrow-right-outline", "pricing", lambda d: d["prices"].get("hp_price_source")),
        FoxCatValueSensor(c, "source_prix_hc", "Source prix heures creuses", "mdi:database-arrow-right-outline", "pricing", lambda d: d["prices"].get("hc_price_source")),
        FoxCatValueSensor(c, "source_prix_reinjection_fixe", "Source prix fixe de réinjection", "mdi:database-arrow-right-outline", "pricing", lambda d: d["prices"].get("fixed_injection_price_source")),
        FoxCatNumericSensor(c, "surplus_disponible_boiler_cycle_protege", "Surplus disponible pour le chauffe-eau pendant cycle protégé", "mdi:solar-power-variant-outline", "machines", lambda d: d["machine_guard"].get("boiler_surplus_available_w"), UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatValueSensor(c, "regime_tarifaire_actif", "Contrat énergie actif", "mdi:cash-sync", "pricing", lambda d: d["prices"].get("regime")),
        FoxCatValueSensor(c, "profil_distribution_actif", "Profil distribution actif", "mdi:transmission-tower", "pricing", lambda d: d["prices"].get("distribution_profile")),
        FoxCatValueSensor(c, "periode_distribution", "Période de distribution", "mdi:clock-outline", "pricing", lambda d: d["prices"].get("distribution_period")),
        FoxCatValueSensor(c, "periode_tarifaire", "Période tarifaire", "mdi:clock-time-eight-outline", "pricing", lambda d: d["prices"].get("period")),
        FoxCatValueSensor(c, "statut_prix", "Statut du prix", "mdi:chart-line", "pricing", lambda d: d["prices"].get("status")),
        FoxCatValueSensor(c, "modele_cout", "Modèle de coût", "mdi:calculator-variant-outline", "pricing", lambda d: d["prices"].get("cost_model")),
        FoxCatValueSensor(c, "prix_negatif_actif", "Prix dynamique négatif actif", "mdi:cash-minus", "pricing", lambda d: "OUI" if d["prices"].get("negative_purchase") else "NON"),
        FoxCatNumericSensor(c, "prix_achat_actif", "Prix d'achat actif", "mdi:transmission-tower-import", "pricing", lambda d: d["prices"].get("active_buy"), "€/kWh"),
        FoxCatNumericSensor(c, "prix_achat_suivant", "Prix d'achat suivant", "mdi:clock-fast", "pricing", lambda d: d["prices"].get("next_buy"), "€/kWh"),
        FoxCatNumericSensor(c, "position_courbe_dynamique", "Position sur la courbe dynamique", "mdi:chart-bell-curve-cumulative", "pricing", lambda d: d.get("economic", {}).get("decision", {}).get("dynamic_curve_position_pct"), PERCENTAGE),
        FoxCatNumericSensor(c, "rang_courbe_dynamique", "Rang prix dynamique", "mdi:sort-numeric-ascending", "pricing", lambda d: d.get("economic", {}).get("decision", {}).get("dynamic_curve_rank")),
        FoxCatValueSensor(c, "tendance_courbe_dynamique", "Tendance courbe dynamique", "mdi:trending-up", "pricing", lambda d: d.get("economic", {}).get("decision", {}).get("dynamic_curve_trend") or "—"),
        FoxCatValueSensor(c, "libelle_prix_actif", "Libellé prix actif", "mdi:label-outline", "pricing", lambda d: d["prices"].get("active_buy_label", "—")),
        FoxCatValueSensor(c, "libelle_prix_suivant", "Libellé prix suivant", "mdi:label-multiple-outline", "pricing", lambda d: d["prices"].get("next_buy_label", "—")),
        FoxCatNumericSensor(c, "valeur_reinjection", "Valeur économique de la réinjection", "mdi:transmission-tower-export", "pricing", lambda d: d["prices"].get("export_value"), "€/kWh"),
        FoxCatValueSensor(c, "convention_prix_reinjection", "Convention prix de réinjection", "mdi:plus-minus-variant", "pricing", lambda d: d["prices"].get("export_sign_convention", "—")),
        FoxCatNumericSensor(c, "cout_prelevement_instantane", "Coût instantané du prélèvement", "mdi:cash-minus", "pricing", lambda d: d["prices"].get("import_cost_rate_eur_h"), "€/h"),
        FoxCatNumericSensor(c, "valeur_reinjection_instantanee", "Valeur instantanée de la réinjection", "mdi:cash-plus", "pricing", lambda d: d["prices"].get("export_value_rate_eur_h"), "€/h"),
        FoxCatNumericSensor(c, "solde_reseau_instantane", "Solde financier instantané réseau", "mdi:scale-balance", "pricing", lambda d: d["prices"].get("net_cost_rate_eur_h"), "€/h"),
        FoxCatEconomicDecisionSensor(c),
        FoxCatValueSensor(c, "etat_financier_ems", "État financier EMS", "mdi:finance", "pricing", lambda d: d.get("status_summary", {}).get("financial_status", "Indéterminé")),
        FoxCatValueSensor(c, "detail_financier_ems", "Détail financier EMS", "mdi:text-box-search-outline", "pricing", lambda d: d.get("status_summary", {}).get("financial_detail", "Indisponible")),
        FoxCatNumericSensor(c, "economique_meilleur_prix_futur", "Meilleur prix d'achat futur", "mdi:cash-clock", "pricing", lambda d: d.get("economic", {}).get("decision", {}).get("best_future_buy_eur_kwh"), "€/kWh"),
        FoxCatNumericSensor(c, "economique_economie_potentielle", "Économie potentielle en reportant", "mdi:piggy-bank-outline", "pricing", lambda d: d.get("economic", {}).get("decision", {}).get("saving_vs_now_eur_kwh"), "€/kWh"),
        FoxCatValueSensor(c, "economique_meilleur_creneau", "Meilleur créneau économique", "mdi:calendar-clock", "pricing", lambda d: d.get("economic", {}).get("decision", {}).get("best_future_at") or "Maintenant"),
        FoxCatDayAheadSensor(c),
        FoxCatValueSensor(c, "day_ahead_prochain_creux", "Day-Ahead • Prochain creux", "mdi:chart-timeline-variant-shimmer", "pricing", lambda d: (d.get("economic", {}).get("day_ahead", {}).get("next_valley") or {}).get("start") or "Indisponible"),
        FoxCatValueSensor(c, "day_ahead_prochain_pic", "Day-Ahead • Prochain pic", "mdi:chart-line-variant", "pricing", lambda d: (d.get("economic", {}).get("day_ahead", {}).get("next_peak") or {}).get("start") or "Indisponible"),
        FoxCatNumericSensor(c, "day_ahead_horizon", "Day-Ahead • Horizon analysé", "mdi:timeline-clock-outline", "pricing", lambda d: d.get("economic", {}).get("day_ahead", {}).get("horizon_hours"), "h"),
        FoxCatNumericSensor(c, "bilan_conso_jour", "🏠 Maison • Consommation aujourd’hui", "mdi:home-lightning-bolt", "accounting", lambda d: d["accounting"]["today"]["house_kwh"], UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        FoxCatNumericSensor(c, "bilan_pv_jour", "☀️ PV • Production aujourd’hui", "mdi:solar-power", "accounting", lambda d: d["accounting"]["today"]["pv_kwh"], UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        FoxCatNumericSensor(c, "bilan_autoconso_jour", "☀️ PV • Énergie autoconsommée aujourd’hui", "mdi:home-import-outline", "accounting", lambda d: d["accounting"]["today"]["self_consumed_kwh"], UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        FoxCatNumericSensor(c, "bilan_import_jour", "🏠 Maison • Prélèvement réseau aujourd’hui", "mdi:transmission-tower-import", "accounting", lambda d: d["accounting"]["today"]["import_kwh"], UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        FoxCatNumericSensor(c, "bilan_export_jour", "☀️ PV • Réinjection aujourd’hui", "mdi:transmission-tower-export", "accounting", lambda d: d["accounting"]["today"]["export_kwh"], UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        FoxCatNumericSensor(c, "bilan_autoconsommation_jour", "☀️ PV • Taux d’autoconsommation aujourd’hui", "mdi:percent-circle-outline", "accounting", lambda d: d["accounting"]["today"]["autoconsumption_pct"], PERCENTAGE),
        FoxCatNumericSensor(c, "bilan_autonomie_jour", "🏠 Maison • Taux d’autonomie aujourd’hui", "mdi:home-percent-outline", "accounting", lambda d: d["accounting"]["today"]["autonomy_pct"], PERCENTAGE),
        FoxCatNumericSensor(c, "bilan_cout_reseau_jour", "🏠 Maison • Coût réseau aujourd’hui", "mdi:cash-minus", "accounting", lambda d: d["accounting"]["today"]["import_cost_eur"], "€"),
        FoxCatNumericSensor(c, "bilan_valeur_injection_jour", "☀️ PV • Solde réinjection aujourd’hui", "mdi:cash-plus", "accounting", lambda d: d["accounting"]["today"]["export_value_eur"], "€"),
        FoxCatNumericSensor(c, "bilan_revenu_injection_jour", "☀️ PV • Revenu réinjection aujourd’hui", "mdi:cash-plus", "accounting", lambda d: d["accounting"]["today"]["export_revenue_eur"], "€"),
        FoxCatNumericSensor(c, "bilan_cout_injection_jour", "☀️ PV • Coût réinjection aujourd’hui", "mdi:cash-minus", "accounting", lambda d: d["accounting"]["today"]["export_cost_eur"], "€"),
        FoxCatNumericSensor(c, "bilan_cout_net_jour", "🏠 Maison • Coût net aujourd’hui", "mdi:cash-sync", "accounting", lambda d: d["accounting"]["today"]["net_grid_cost_eur"], "€"),
        FoxCatNumericSensor(c, "bilan_gain_solaire_jour", "☀️ PV • Gain solaire estimé aujourd’hui", "mdi:solar-power-variant", "accounting", lambda d: d["accounting"]["today"]["solar_gain_eur"], "€"),
        # Accounting V2 — ventilation tarifaire sans netting énergétique.
        FoxCatNumericSensor(c, "bilan_dynamic_import_jour", "Dynamic • Prélèvement réseau aujourd’hui", "mdi:transmission-tower-import", "accounting", lambda d: d["accounting"]["today"]["tariff"]["dynamic"]["import_kwh"], UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        FoxCatNumericSensor(c, "bilan_dynamic_export_jour", "Dynamic • Réinjection aujourd’hui", "mdi:transmission-tower-export", "accounting", lambda d: d["accounting"]["today"]["tariff"]["dynamic"]["export_kwh"], UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        FoxCatNumericSensor(c, "bilan_dynamic_cout_achat_jour", "Dynamic • Coût achat aujourd’hui", "mdi:cash-minus", "pricing", lambda d: d["accounting"]["today"]["tariff"]["dynamic"]["import_cost_eur"], "€"),
        FoxCatNumericSensor(c, "bilan_dynamic_revenu_injection_jour", "Dynamic • Revenu réinjection aujourd’hui", "mdi:cash-plus", "pricing", lambda d: d["accounting"]["today"]["tariff"]["dynamic"]["export_revenue_eur"], "€"),
        FoxCatNumericSensor(c, "bilan_dynamic_cout_injection_jour", "Dynamic • Coût réinjection aujourd’hui", "mdi:cash-minus", "pricing", lambda d: d["accounting"]["today"]["tariff"]["dynamic"]["export_cost_eur"], "€"),
        FoxCatNumericSensor(c, "bilan_dynamic_cout_net_jour", "Dynamic • Coût net aujourd’hui", "mdi:cash-sync", "pricing", lambda d: d["accounting"]["today"]["tariff"]["dynamic"]["net_cost_eur"], "€"),
        FoxCatNumericSensor(c, "bilan_hp_import_jour", "HP • Prélèvement réseau aujourd’hui", "mdi:weather-sunny", "accounting", lambda d: d["accounting"]["today"]["tariff"]["hphc"]["HP"]["import_kwh"], UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        FoxCatNumericSensor(c, "bilan_hp_export_jour", "HP • Réinjection aujourd’hui", "mdi:transmission-tower-export", "accounting", lambda d: d["accounting"]["today"]["tariff"]["hphc"]["HP"]["export_kwh"], UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        FoxCatNumericSensor(c, "bilan_hc_import_jour", "HC • Prélèvement réseau aujourd’hui", "mdi:weather-night", "accounting", lambda d: d["accounting"]["today"]["tariff"]["hphc"]["HC"]["import_kwh"], UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        FoxCatNumericSensor(c, "bilan_hc_export_jour", "HC • Réinjection aujourd’hui", "mdi:transmission-tower-export", "accounting", lambda d: d["accounting"]["today"]["tariff"]["hphc"]["HC"]["export_kwh"], UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        FoxCatNumericSensor(c, "bilan_conso_mois", "🏠 Maison • Consommation ce mois", "mdi:calendar-month", "accounting", lambda d: d["accounting"]["month"]["house_kwh"], UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        FoxCatNumericSensor(c, "bilan_pv_mois", "☀️ PV • Production ce mois", "mdi:calendar-month-outline", "accounting", lambda d: d["accounting"]["month"]["pv_kwh"], UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        FoxCatNumericSensor(c, "bilan_cout_net_mois", "🏠 Maison • Coût net ce mois", "mdi:cash-multiple", "accounting", lambda d: d["accounting"]["month"]["net_grid_cost_eur"], "€"),
        FoxCatNumericSensor(c, "bilan_conso_annee", "🏠 Maison • Consommation cette année", "mdi:calendar", "accounting", lambda d: d["accounting"]["year"]["house_kwh"], UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        FoxCatNumericSensor(c, "bilan_pv_annee", "☀️ PV • Production cette année", "mdi:calendar-sun", "accounting", lambda d: d["accounting"]["year"]["pv_kwh"], UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
        FoxCatNumericSensor(c, "bilan_cout_net_annee", "🏠 Maison • Coût net cette année", "mdi:cash-check", "accounting", lambda d: d["accounting"]["year"]["net_grid_cost_eur"], "€"),
        FoxCatValueSensor(c, "derniere_trame", "Dernière trame énergétique", "mdi:clock-check-outline", "ems", lambda d: _iso(d["core"].get("last_frame"))),
        FoxCatValueSensor(c, "derniere_action", "Dernière action EMS", "mdi:clock-outline", "ems", lambda d: _iso(d["core"].get("last_action"))),
    ]
    bus_view = lambda d: d.get("energy_bus", {})
    entities.extend([
        FoxCatValueSensor(c, "energy_bus_etat", "État Energy Bus", "mdi:transit-connection-variant", "energy_bus", lambda d: "ACTIF" if d.get("energy_bus") is not None else "INDISPONIBLE"),
        FoxCatNumericSensor(c, "energy_bus_frame_id", "Numéro de trame Energy Bus", "mdi:counter", "energy_bus", lambda d: bus_view(d).get("last_grid_frame_id", 0)),
        FoxCatValueSensor(c, "energy_bus_derniere_trame", "Dernière trame Energy Bus", "mdi:clock-check-outline", "energy_bus", lambda d: _iso(bus_view(d).get("last_grid_frame_at"))),
        FoxCatValueSensor(c, "energy_bus_intention_source", "Source dernière intention Energy Bus", "mdi:source-branch", "energy_bus", lambda d: (bus_view(d).get("ems_intent") or {}).get("source", "AUCUNE")),
        FoxCatValueSensor(c, "energy_bus_intention_action", "Action dernière intention Energy Bus", "mdi:message-flash-outline", "energy_bus", lambda d: (bus_view(d).get("ems_intent") or {}).get("action", "AUCUNE")),
        FoxCatNumericSensor(c, "energy_bus_intention_delta", "Delta dernière intention Energy Bus", "mdi:delta", "energy_bus", lambda d: (bus_view(d).get("ems_intent") or {}).get("delta_w", 0.0), UnitOfPower.WATT, SensorDeviceClass.POWER),
        FoxCatValueSensor(c, "energy_bus_message_id", "Energy Bus • Numéro du dernier message", "mdi:identifier", "energy_bus", lambda d: (bus_view(d).get("ems_intent") or {}).get("message_id", "AUCUN")),
        FoxCatValueSensor(c, "energy_bus_ack", "Energy Bus • ACK inter-corps", "mdi:message-check-outline", "energy_bus", lambda d: (bus_view(d).get("ems_intent") or {}).get("status", "AUCUN")),
        FoxCatValueSensor(c, "energy_bus_ack_raison", "Energy Bus • Raison ACK", "mdi:message-text-outline", "energy_bus", lambda d: (bus_view(d).get("ems_intent") or {}).get("ack_reason", "Aucune")),
        FoxCatValueSensor(c, "energy_bus_ack_par", "Energy Bus • ACK par", "mdi:source-branch-check", "energy_bus", lambda d: (bus_view(d).get("ems_intent") or {}).get("ack_by", "AUCUN")),
        FoxCatValueSensor(c, "energy_bus_dernier_evenement", "Energy Bus • Dernier échange", "mdi:transit-connection-horizontal", "energy_bus", lambda d: bus_view(d).get("last_transport_event", "Aucun")),
        FoxCatNumericSensor(c, "energy_bus_messages_jour", "Energy Bus • Messages aujourd’hui", "mdi:counter", "energy_bus", lambda d: bus_view(d).get("message_count", 0)),
        FoxCatNumericSensor(c, "energy_bus_messages_hier", "Energy Bus • Messages journée précédente", "mdi:counter", "energy_bus", lambda d: bus_view(d).get("previous_day_message_count", 0)),
        FoxCatValueSensor(c, "energy_bus_dernier_reset", "Energy Bus • Dernier reset journalier", "mdi:backup-restore", "energy_bus", lambda d: _iso(bus_view(d).get("last_daily_reset_at"))),
        FoxCatNumericSensor(c, "energy_bus_messages_attente", "Energy Bus • Messages en attente ACK", "mdi:message-badge-outline", "energy_bus", lambda d: bus_view(d).get("pending_count", 0)),
        FoxCatValueSensor(c, "energy_bus_derniere_source", "Energy Bus • Source dernier message", "mdi:source-branch", "energy_bus", lambda d: (bus_view(d).get("last_message") or {}).get("source", "AUCUNE")),
        FoxCatValueSensor(c, "energy_bus_derniere_cible", "Energy Bus • Cible dernier message", "mdi:target", "energy_bus", lambda d: (bus_view(d).get("last_message") or {}).get("target", "AUCUNE")),
        FoxCatValueSensor(c, "energy_bus_derniere_action", "Energy Bus • Action dernier message", "mdi:message-flash-outline", "energy_bus", lambda d: (bus_view(d).get("last_message") or {}).get("action", "AUCUNE")),
        FoxCatValueSensor(c, "energy_bus_trame_ems_statut", "Energy Bus • Trame • EMS Core", "mdi:state-machine", "energy_bus", lambda d: (bus_view(d).get("frame") or {}).get("ems_status", "AUCUNE")),
        FoxCatValueSensor(c, "energy_bus_trame_onduleur_statut", "Energy Bus • Trame • Onduleur Core", "mdi:solar-power-variant", "energy_bus", lambda d: (bus_view(d).get("frame") or {}).get("inverter_status", "AUCUNE")),
        FoxCatNumericSensor(c, "ems_trames_traitees", "EMS Core • Trames traitées", "mdi:counter", "ems", lambda d: d.get("core", {}).get("processed_frame_count", 0)),
        FoxCatNumericSensor(c, "onduleur_trames_traitees", "Onduleur Core • Trames traitées", "mdi:counter", "pri", lambda d: d.get("pri", {}).get("processed_frame_count", 0)),
        FoxCatValueSensor(c, "onduleur_actionneur_statut", "Onduleur • Actionneur RRCR", "mdi:electric-switch", "pri", lambda d: d.get("pri", {}).get("actuator_status", "IDLE")),
        FoxCatValueSensor(c, "onduleur_actionneur_cible", "Onduleur • Cible actionneur RRCR", "mdi:gauge", "pri", lambda d: d.get("pri", {}).get("actuator_target_level") if d.get("pri", {}).get("actuator_target_level") is not None else "AUCUNE"),
        FoxCatRegistrySensor(c),
        FoxCatValueSensor(c, "periode_tarifaire", "Période tarifaire", "mdi:clock-outline", "pricing", lambda d: d["prices"].get("period", "—")),
        FoxCatValueSensor(c, "politique_reseau_active", "Politique réseau active", "mdi:transmission-tower", "pricing", lambda d: d["settings"].get("network_policy", "Compensation")),
        FoxCatValueSensor(c, "ems_onduleur_etat", "EMS Onduleur • État", "mdi:solar-power-variant", "pri", lambda d: d["energy_bus"]["inverter"].get("status", "—")),
        FoxCatNumericSensor(c, "ems_onduleur_plafond_pv", "EMS Onduleur • Plafond PV", "mdi:solar-power", "pri", lambda d: d["energy_bus"]["inverter"].get("pv_limit_w", 0.0), "W"),
        FoxCatNumericSensor(c, "ems_onduleur_utilisation_plafond", "EMS Onduleur • Utilisation plafond", "mdi:gauge", "pri", lambda d: d["energy_bus"]["inverter"].get("pv_ratio_pct", 0.0), PERCENTAGE),
        FoxCatValueSensor(c, "ems_onduleur_potentiel", "EMS Onduleur • Potentiel solaire", "mdi:weather-sunny-alert", "pri", lambda d: "PLUS POSSIBLE" if d["energy_bus"]["inverter"].get("more_solar_possible") else ("MAX SOLAIRE ATTEINT" if d["energy_bus"]["inverter"].get("max_solar_reached") else "STABLE")),
    ])

    # Un jeu de capteurs est créé automatiquement pour chaque appareil FoxCat mesuré.
    appliance_defs = [("boiler", "Chauffe-eau")] + [(m.machine_id, m.name) for m in c.machines if m.power_sensor]
    for appliance_id, appliance_name in appliance_defs:
        safe = appliance_id.replace(" ", "_").lower()
        entities.extend([
            FoxCatNumericSensor(c, f"appareil_{safe}_energie_jour", f"🔌 {appliance_name} • Énergie aujourd’hui", "mdi:counter", "accounting", lambda d, aid=appliance_id: d["accounting"]["today"]["appliances"].get(aid,{}).get("energy_kwh",0.0), UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
            FoxCatNumericSensor(c, f"appareil_{safe}_solaire_jour", f"🔌 {appliance_name} • Part solaire aujourd’hui", "mdi:white-balance-sunny", "accounting", lambda d, aid=appliance_id: d["accounting"]["today"]["appliances"].get(aid,{}).get("solar_kwh",0.0), UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
            FoxCatNumericSensor(c, f"appareil_{safe}_reseau_jour", f"🔌 {appliance_name} • Part réseau aujourd’hui", "mdi:transmission-tower-import", "accounting", lambda d, aid=appliance_id: d["accounting"]["today"]["appliances"].get(aid,{}).get("grid_kwh",0.0), UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
            FoxCatNumericSensor(c, f"appareil_{safe}_cout_jour", f"🔌 {appliance_name} • Coût aujourd’hui", "mdi:cash", "accounting", lambda d, aid=appliance_id: d["accounting"]["today"]["appliances"].get(aid,{}).get("cost_eur",0.0), "€"),
            FoxCatNumericSensor(c, f"appareil_{safe}_hp_jour", f"🔌 {appliance_name} • Consommation HP aujourd’hui", "mdi:weather-sunny", "accounting", lambda d, aid=appliance_id: d["accounting"]["today"]["appliances"].get(aid,{}).get("hp_kwh",0.0), UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
            FoxCatNumericSensor(c, f"appareil_{safe}_hc_jour", f"🔌 {appliance_name} • Consommation HC aujourd’hui", "mdi:weather-night", "accounting", lambda d, aid=appliance_id: d["accounting"]["today"]["appliances"].get(aid,{}).get("hc_kwh",0.0), UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
            FoxCatNumericSensor(c, f"appareil_{safe}_dynamic_jour", f"🔌 {appliance_name} • Consommation Dynamic aujourd’hui", "mdi:chart-timeline-variant", "accounting", lambda d, aid=appliance_id: d["accounting"]["today"]["appliances"].get(aid,{}).get("dynamic_kwh",0.0), UnitOfEnergy.KILO_WATT_HOUR, SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
            FoxCatValueSensor(c, f"appareil_{safe}_tarif_actuel", f"🔌 {appliance_name} • Tarif actuel", "mdi:clock-check-outline", "accounting", lambda d: d["prices"].get("period","—")),
        ])
    # V1.6.152 — collecte passive des signatures machines. Les données brutes
    # restent dans le Store local; seules des synthèses légères sont exposées à HA.
    for machine in c.machines:
        mid = machine.machine_id
        safe = mid.replace(" ", "_").lower()
        name = machine.name
        entities.extend([
            FoxCatNumericSensor(c, f"apprentissage_{safe}_cycles", f"📊 {name} • Cycles collectés", "mdi:chart-timeline-variant", "machine_learning", lambda d, aid=mid: d.get("machine_learning",{}).get(aid,{}).get("total_cycles",0)),
            FoxCatValueSensor(c, f"apprentissage_{safe}_collecte", f"📊 {name} • Collecte en cours", "mdi:record-rec", "machine_learning", lambda d, aid=mid: "OUI" if (d.get("machine_learning",{}).get(aid,{}).get("current") or {}).get("active") else "NON"),
            FoxCatNumericSensor(c, f"apprentissage_{safe}_energie_moyenne", f"📊 {name} • Énergie moyenne 10 cycles", "mdi:chart-bell-curve-cumulative", "machine_learning", lambda d, aid=mid: ((d.get("machine_learning",{}).get(aid,{}).get("average_energy_wh_10") or 0.0) / 1000.0), UnitOfEnergy.KILO_WATT_HOUR),
            FoxCatNumericSensor(c, f"apprentissage_{safe}_duree_moyenne", f"📊 {name} • Durée moyenne 10 cycles", "mdi:timer-outline", "machine_learning", lambda d, aid=mid: ((d.get("machine_learning",{}).get(aid,{}).get("average_duration_s_10") or 0.0) / 60.0), "min"),
            FoxCatValueSensor(c, f"economique_{safe}_decision", f"💶 {name} • Choix économique", "mdi:cash-clock", "machines", lambda d, aid=mid: d.get("economic",{}).get("machines",{}).get(aid,{}).get("label", "Indisponible")),
            FoxCatMachineDayAheadSensor(c, mid, name),
        ])

    # V1.6.0 — classement fonctionnel officiel. Les kWh et pourcentages vont
    # dans Énergie; les coûts/valeurs monétaires vont dans Tarification.
    for entity in entities:
        key = getattr(entity, "_key", None) or getattr(entity, "_attr_unique_id", "")
        text = str(key).lower()
        if text.startswith("bilan_") or "appareil_" in text:
            monetary = any(marker in text for marker in ("cout", "valeur", "gain", "tarif"))
            device = "pricing" if monetary else "energy"
            entity._device = device
            if isinstance(entity, FoxCatNumericSensor):
                entity._foxcat_device_identifier = None
                entity._foxcat_device_name = None

    async_add_entities(entities)


class FoxCatDayAheadSensor(FoxCatEntity, SensorEntity):
    """Synthèse du planificateur Day-Ahead, strictement contrat Dynamique."""

    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "day_ahead_plan", "Planificateur Day-Ahead", "mdi:chart-timeline-variant-shimmer", "pricing")

    def _plan(self) -> dict[str, Any]:
        return self.coordinator.data.get("economic", {}).get("day_ahead", {}) or {}

    @property
    def native_value(self) -> str:
        plan = self._plan()
        if not plan.get("active"):
            return "INACTIF — HORS CONTRAT DYNAMIQUE"
        if plan.get("favorable_now"):
            return "PRIX FAVORABLE"
        return "PLANIFICATION ACTIVE"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        plan = self._plan()
        return {
            "actif": bool(plan.get("active")),
            "raison_inactive": plan.get("reason"),
            "position_pct": plan.get("current_position_pct"),
            "seuil_favorable_pct": plan.get("threshold_pct"),
            "seuil_pic_pct": plan.get("high_threshold_pct"),
            "prix_favorable": bool(plan.get("favorable_now")),
            "fin_creux_actuel": plan.get("current_favorable_end"),
            "minutes_restantes_creux": plan.get("current_favorable_remaining_minutes"),
            "temps_restant_creux": plan.get("current_favorable_remaining_label"),
            "seuil_demarrage_effectif_pct": plan.get("start_threshold_pct"),
            "periode_distribution": plan.get("distribution_period"),
            "comportement": plan.get("behavior"),
            "prix_min_eur_kwh": plan.get("curve_min_eur_kwh"),
            "prix_max_eur_kwh": plan.get("curve_max_eur_kwh"),
            "prochain_creux": plan.get("next_valley"),
            "prochain_pic": plan.get("next_peak"),
            "demain_disponible": bool(plan.get("tomorrow_available")),
            "horizon_heures": plan.get("horizon_hours"),
            "fenetre_solaire": plan.get("solar_window"),
            "machines": plan.get("machines", {}),
        }


class FoxCatMachineDayAheadSensor(FoxCatEntity, SensorEntity):
    """Fenêtre optimale d'une machine, calculée dans ses plages utilisateur."""

    def __init__(self, coordinator: FoxCatEnergyCoordinator, machine_id: str, name: str) -> None:
        safe = machine_id.replace(" ", "_").lower()
        super().__init__(coordinator, f"day_ahead_{safe}_plan", f"Day-Ahead • {name}", "mdi:calendar-clock", "machines")
        self._machine_id = machine_id

    def _plan(self) -> dict[str, Any]:
        return (self.coordinator.data.get("economic", {}).get("day_ahead", {}).get("machines", {}) or {}).get(self._machine_id, {}) or {}

    @property
    def native_value(self) -> str:
        root = self.coordinator.data.get("economic", {}).get("day_ahead", {}) or {}
        if not root.get("active"):
            return "INACTIF — HORS CONTRAT DYNAMIQUE"
        plan = self._plan()
        if plan.get("protected"):
            return "EN CYCLE — PROTÉGÉ"
        if plan.get("allow_start_now"):
            return "DÉMARRAGE AUTORISÉ"
        start = plan.get("best_start")
        return f"PLANIFIÉ {start}" if start else "ATTENTE"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return dict(self._plan())


class FoxCatEconomicDecisionSensor(FoxCatEntity, SensorEntity):
    """Décision lisible du comparateur économique FoxCat.

    Cette entité ne publie rien sur Energy Bus. Ses attributs expliquent le
    raisonnement tarifaire et les recommandations par machine.
    """

    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(
            coordinator,
            "decision_economique_ems",
            "Décision économique EMS",
            "mdi:finance",
            "pricing",
        )

    @property
    def native_value(self) -> str:
        decision = (self.coordinator.data or {}).get("economic", {}).get("decision", {})
        return str(decision.get("label") or decision.get("code") or "Indisponible")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        economic = (self.coordinator.data or {}).get("economic", {})
        decision = dict(economic.get("decision", {}) or {})
        return {
            "code": decision.get("code"),
            "raison": decision.get("reason"),
            "regime": decision.get("regime"),
            "confiance": decision.get("confidence"),
            "demarrage_charge_flexible_autorise": decision.get("flexible_start"),
            "favorise_autoconsommation": decision.get("prefer_self_consumption"),
            "favorise_reinjection": decision.get("prefer_export"),
            "prix_achat_actuel_eur_kwh": decision.get("current_buy_eur_kwh"),
            "valeur_reinjection_eur_kwh": decision.get("export_value_eur_kwh"),
            "meilleur_prix_futur_eur_kwh": decision.get("best_future_buy_eur_kwh"),
            "meilleur_creneau": decision.get("best_future_at"),
            "economie_potentielle_eur_kwh": decision.get("saving_vs_now_eur_kwh"),
            "horizon_heures": decision.get("horizon_hours"),
            "points_prix": decision.get("forecast_points"),
            "application": decision.get("application"),
            "indice_tarifaire_relatif": decision.get("dynamic_price_index"),
            "plage_tarifaire_dynamique": decision.get("dynamic_price_band"),
            "prix_min_day_ahead_eur_kwh": decision.get("dynamic_price_min_eur_kwh"),
            "prix_max_day_ahead_eur_kwh": decision.get("dynamic_price_max_eur_kwh"),
            "position_courbe_pct": decision.get("dynamic_curve_position_pct"),
            "rang_courbe": decision.get("dynamic_curve_rank"),
            "points_courbe": decision.get("dynamic_curve_points"),
            "tendance_courbe": decision.get("dynamic_curve_trend"),
            "boiler_energie_manquante_kwh": decision.get("boiler_energy_missing_kwh"),
            "boiler_duree_chauffe_h": decision.get("boiler_heating_duration_h"),
            "boiler_creneau_reserve_debut": decision.get("boiler_reserved_start"),
            "boiler_creneau_reserve_fin": decision.get("boiler_reserved_end"),
            "boiler_prix_moyen_creneau_eur_kwh": decision.get("boiler_reserved_avg_price_eur_kwh"),
            "boiler_charge_maintenant": decision.get("boiler_charge_now"),
            "priorite_confort_ecs": decision.get("boiler_comfort_priority"),
            "repli_dynamique_standard": decision.get("dynamic_fallback"),
            "prevision": economic.get("forecast", {}),
            "machines": economic.get("machines", {}),
        }


class FoxCatRegistrySensor(FoxCatEntity, SensorEntity):
    """Expose the central dashboard/entity registry as a diagnostic entity."""

    def __init__(self, coordinator: FoxCatEnergyCoordinator) -> None:
        super().__init__(coordinator, "registre_entites", "Registre des entités FoxCat", "mdi:database-search", "diagnostic")

    def _snapshot(self) -> dict[str, Any]:
        return registry_diagnostics(self.hass, self.coordinator.entry, self.coordinator.config)

    @property
    def native_value(self) -> str:
        data = self._snapshot()
        return f"{data['resolved_count']}/{data['binding_count']} résolues"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self._snapshot()
        return {
            "ordre_officiel": data["order"],
            "non_resolues": data["unresolved"],
            "indisponibles": data["unavailable"],
            "sections": data["sections"],
        }


def _iso(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else "Jamais"


class FoxCatValueSensor(FoxCatEntity, SensorEntity):
    def __init__(self, coordinator, key: str, name: str, icon: str, device: str, getter: Callable[[dict[str, Any]], Any]):
        super().__init__(coordinator, key, name, icon, device)
        self._getter = getter

    @property
    def native_value(self) -> Any:
        try:
            value = self._getter(self.coordinator.data)
            if value is None:
                return "Indisponible"
            return value
        except Exception:
            return "Indisponible"


class FoxCatNumericSensor(FoxCatEntity, SensorEntity):
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, key: str, name: str, icon: str, device: str, getter: Callable[[dict[str, Any]], Any], unit: str | None = None, device_class=None, state_class=None, device_name: str | None = None, device_identifier: str | None = None, suggested_object_id: str | None = None):
        super().__init__(coordinator, key, name, icon, device)
        if suggested_object_id:
            self._attr_suggested_object_id = suggested_object_id
        self._getter = getter
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._foxcat_device_name = device_name
        self._foxcat_device_identifier = device_identifier
        if state_class is not None:
            self._attr_state_class = state_class
        elif unit in {PERCENTAGE, "€/kWh", "€"} or unit is None:
            self._attr_state_class = None

    @property
    def native_value(self) -> float | int | None:
        try:
            value = self._getter(self.coordinator.data)
            if value is None:
                return None
            if isinstance(value, int):
                return value
            return round(float(value), 4)
        except (TypeError, ValueError, KeyError, AttributeError):
            return None

    @property
    def device_info(self):
        if self._foxcat_device_identifier:
            return {
                "identifiers": {(DOMAIN, self._foxcat_device_identifier)},
                "name": self._foxcat_device_name or self._foxcat_device_identifier,
                "manufacturer": "FoxCat Energy",
                "model": "Coûts & Bilan",
                "via_device": (DOMAIN, f"{self.coordinator.entry.entry_id}:ems"),
            }
        return super().device_info

