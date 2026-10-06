from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import event as event_helper
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change, async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    ACK_IDLE,
    ACK_NOK,
    ACK_OK,
    ACK_WAIT,
    VERSION,
    BOILER_BOOST_65,
    BOILER_HEAT_45,
    BOILER_NONE,
    BOILER_STOP,
    CONF_AI_TASK,
    CONF_BOILER_BINARY,
    CONF_BOILER_CLIMATE,
    CONF_BOILER_POWER_SENSOR,
    CONF_BOILER_VOLUME,
    CONF_BOILER_ELEMENT_POWER,
    CONF_BOILER_COLD_WATER_TEMP,
    CONF_BOILER_RESISTANCE_TEMP_SENSOR,
    CONF_BOILER_TEMP_SENSOR,
    CONF_DISHWASHER_CYCLE,
    CONF_DISHWASHER_SOCKET,
    CONF_DISHWASHER_ON_1,
    CONF_DISHWASHER_OFF_1,
    CONF_DISHWASHER_ON_2,
    CONF_DISHWASHER_OFF_2,
    CONF_DRYER_CYCLE,
    CONF_DRYER_SOCKET,
    CONF_DRYER_ON_1,
    CONF_DRYER_OFF_1,
    CONF_DRYER_ON_2,
    CONF_DRYER_OFF_2,
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
    CONF_GRID_EXPORT_SENSOR,
    CONF_GRID_IMPORT_SENSOR,
    CONF_GRID_LEGACY_SENSOR,
    CONF_GRID_SIGNED_SENSOR,
    CONF_GRID_SIGN_CONVENTION,
    GRID_SIGN_IMPORT_POSITIVE,
    GRID_SIGN_EXPORT_POSITIVE,
    CONF_METRONOME_SENSOR,
    CONF_METRONOME_FALLBACK_SENSOR,
    CONF_HOUSE_SENSOR,
    CONF_INSTALLATION_NAME,
    CONF_MACHINES_V13,
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
    CONF_DYNAMIC_EXPORT_SIGN_CONVENTION,
    DYNAMIC_EXPORT_NEGATIVE_IS_REVENUE,
    DYNAMIC_EXPORT_POSITIVE_IS_REVENUE,
    DYNAMIC_ARBITRAGE_HORIZON_HOURS,
    CONF_TARIFF_HP_START_1,
    CONF_TARIFF_HP_END_1,
    CONF_TARIFF_HP_START_2,
    CONF_TARIFF_HP_END_2,
    CONF_TARIFF_FIXED_INJECTION_PRICE,
    CONF_TARIFF_HP_PRICE, CONF_TARIFF_HC_PRICE, CONF_TARIFF_SIMPLE_PRICE,
    CONF_TARIFF_HP_PRICE_SENSOR,
    CONF_TARIFF_HC_PRICE_SENSOR,
    CONF_TARIFF_FIXED_INJECTION_PRICE_SENSOR,
    CONF_PRI_L1,
    CONF_PRI_L2,
    CONF_PRI_L3,
    CONF_PRI_L4,
    CONF_INVERTER_POWER_SENSOR,
    CONF_PV_SENSOR,
    CONF_WASHER_CYCLE,
    CONF_WASHER_SOCKET,
    CONF_WASHER_ON_1,
    CONF_WASHER_OFF_1,
    CONF_WASHER_ON_2,
    CONF_WASHER_OFF_2,
    DEFAULT_SETTINGS,
    DOMAIN,
    KNOWN_LEGACY_AUTOMATIONS,
    LEGACY_MODE_ENTITY,
    LEGACY_SETTING_MAP,
    LEGACY_SWITCH_MAP,
    MODE_ALIASES,
    MODE_DYNAMIC,
    MODE_ECO,
    MODE_COMFORT, MODES,
    PRICE_SOURCE_DYNAMIC, PRICE_SOURCE_VARIABLE, PRICE_SOURCE_CONTRACT,
    TARIFF_STRUCTURE_SIMPLE, TARIFF_STRUCTURE_TOU, TARIFF_STRUCTURE_IMPACT,
    NETWORK_POLICY_NOT_VALUED, NETWORK_POLICY_ZERO_INJECTION,
    MODE_ECS,
    MODE_MANUAL,
    MODE_ZERO,
    PHASE_ACQUISITION,
    PHASE_DECISION,
    PHASE_WAIT_ACK,
    RRCR_CODE_TO_LEVEL,
    RRCR_LEVEL_TO_CODE,
    TARIFF_COMPENSATION,
    NETWORK_POLICY_COMPENSATION,
    NETWORK_POLICY_BILLED_EXPORT,
    NETWORK_POLICY_LEGACY_BILLED_EXPORT,
    TARIFF_DYNAMIC,
    TARIFF_TOU,
    TIME_SETTING_KEYS,
)
from .engine import BoilerIntent, EnergySnapshot, SolarForecast, decide_dynamic, decide_zero, evaluate_mode
from .engine.load_guard import (
    boiler_surplus_before_load_w,
    protected_cycle_boiler_allowed,
    protected_cycle_boiler_allowed_stable,
)
from .engine.modes.dynamic_boiler_v2 import evaluate_dynamic_boiler_v2
from .engine.tariff import price_status, tariff_boundaries, tariff_period
from .economic_optimizer import (
    PricePoint,
    build_hphc_points,
    evaluate_market,
    extract_price_points,
    merge_price_points,
    recommend_flexible_load,
)
from .machines import MachineDefinition, machine_allowed, machine_definitions, schedule_boundaries
from .machine_cycle import MachineCycleManager
from .machine_learning import MachineLearningRecorder
from .energy_bus import EnergyBus
from .inverter_core import InverterCore
from .accounting import EnergyAccounting
from .dynamic_scheduler import build_dynamic_schedule
from .migration import (
    MIGRATION_MODEL_VERSION,
    compatibility_tariff_regime,
    migrate_settings_v173,
)
from .tariff_model import tariff_dimensions, final_client_price, apply_final_price_components
from .price_analyzer import analyze_price_curve
from .flexible_load_planner import build_flexible_load_plan
from .dashboard import dashboard_status

_LOGGER = logging.getLogger(__name__)


class FoxCatEnergyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Central sovereign EMS coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.config = dict(entry.data)
        self.config.update(entry.options)
        self._entry_options_snapshot: dict[str, Any] = {}
        self._store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.machines: list[MachineDefinition] = machine_definitions(self.config)
        # FoxCat 1.5.0 : deux cœurs, communication immédiate par EnergyBus.
        self.energy_bus = EnergyBus()
        self.inverter_core = InverterCore()
        self.machine_cycle_manager = MachineCycleManager()
        # V1.6.152 : collecte passive des signatures machines. Cette couche ne
        # participe à aucune décision EMS/PRI et n'agit sur aucun équipement.
        self.machine_learning = MachineLearningRecorder()
        self.settings: dict[str, Any] = dict(DEFAULT_SETTINGS)
        self.core_state: dict[str, Any] = {
            "phase": PHASE_ACQUISITION,
            "ack": ACK_IDLE,
            "last_reason": "FoxCat Energy initialisé.",
            "pending_action": "NONE",
            "pending_delta": 0.0,
            "action_reference_grid": 0.0,
            "grid_expected": 0.0,
            "ack_error": 0.0,
            "t0": None,
            "last_frame": None,
            "last_action": None,
            "boiler_demand": BOILER_NONE,
            "boiler_origin": "AUCUNE",
            "boiler_user_override": "AUTO",
            "execution_status": "IDLE",
            "execution_command": "NONE",
            "execution_retries": 0,
            "execution_failure_reason": "",
            "fsm_status": "OK",
            "fsm_transition_count": 0,
            "fsm_last_transition_at": None,
            "fsm_last_transition": "INITIALISATION -> ACQUISITION",
            "bus_message_id": None,
            "last_frame_id": 0,
            "last_frame_received_at": None,
            "processed_frame_count": 0,
            "last_bus_decision_id": None,
        }
        self.pri_state: dict[str, Any] = {
            "current_level": 100,
            "target_level": 100,
            "code": "0000",
            "direction": "maintien",
            "ack_rrcr": "IDLE",
            "ack_inverter": "IDLE",
            "ack_grid": "IDLE",
            "score_current": 0.0,
            "score_target": 0.0,
            "house_target_level": 100,
            "estimated_house_w": 0.0,
            "target_pv_w": 0.0,
            "predicted_import_w": 0.0,
            "predicted_export_w": 0.0,
            "last_reason": "PRI initialisé.",
            "frame_id": 0,
            "pending_frame_id": None,
            "pending_frame_serial": None,
            "pending_level": None,
            "pending_pv_before": None,
            "solar_state": "PV_UNKNOWN",
            "solar_potential_min_w": 0.0,
            "pv_limit_w": 4000.0,
            "pv_limit_error_w": 0.0,
            "guard_reason": "initialisation",
            "last_engine_run": None,
            "engine_run_count": 0,
            "decision_tick_count": 0,
            "last_decision_at": None,
            "last_frame_received_at": None,
            "processed_frame_count": 0,
            "actuator_status": "IDLE",
            "actuator_target_level": None,
            "actuator_last_error": "",
        }
        # FoxCat 1.5.5 : horloge réseau synchronisée sur un capteur physique.
        # Le capteur Smappee choisi donne la phase; un capteur de secours peut
        # prendre le relais. Le métronome ne dépend donc plus d'une variation
        # de valeur : les republications identiques restent des battements.
        primary_clock = (
            self.config.get(CONF_GRID_SIGNED_SENSOR)
            or self.config.get(CONF_METRONOME_SENSOR)
            or self.config.get(CONF_GRID_IMPORT_SENSOR)
        )
        fallback_clock = self.config.get(CONF_METRONOME_FALLBACK_SENSOR)
        if not fallback_clock and not self.config.get(CONF_GRID_SIGNED_SENSOR):
            fallback_clock = self.config.get(CONF_GRID_EXPORT_SENSOR)
        if fallback_clock == primary_clock:
            fallback_clock = None
        self.metronome_state: dict[str, Any] = {
            "status": "INITIALISATION",
            "source": "AUCUNE",
            "primary_entity": primary_clock,
            "fallback_entity": fallback_clock,
            "primary_last_report_at": None,
            "fallback_last_report_at": None,
            "last_pulse_at": None,
            "last_pulse_source": "AUCUNE",
            "pulse_count": 0,
            "primary_report_count": 0,
            "fallback_report_count": 0,
            "period_s": float(self.settings.get("metronome_period_s", 30.0)),
            "next_due_at": None,
            "last_reason": "Métronome réseau en attente de synchronisation.",
            "counter_date": dt_util.as_local(dt_util.now()).date().isoformat(),
            "last_daily_reset_at": None,
            "previous_day_pulse_count": 0,
            "previous_day_primary_report_count": 0,
            "previous_day_fallback_report_count": 0,
            "previous_day_frame_count": 0,
            "previous_day_message_count": 0,
        }
        self._metronome_lock = asyncio.Lock()
        self._metronome_pulse_lock = asyncio.Lock()
        self._frame_dispatch_lock = asyncio.Lock()
        self._metronome_last_seen_report: dict[str, datetime] = {}
        self.solar_forecast = SolarForecast()
        self._unsubs: list[Any] = []
        # V1.6.150 : les deux corps sont cadencés par la même publication réseau
        # mais ne partagent plus aucun verrou d'exécution.
        self._core_lock = asyncio.Lock()
        self._inverter_reduction_lock = asyncio.Lock()
        self._ems_action_lock = asyncio.Lock()
        self._inverter_action_lock = asyncio.Lock()
        self._pri_task: asyncio.Task | None = None
        self._pri_actuator_task: asyncio.Task | None = None
        self._pri_requested: dict[str, Any] | None = None
        self._boiler_command_task: asyncio.Task | None = None
        self._execution_task: asyncio.Task | None = None
        self._learning_save_task: asyncio.Task | None = None
        self._status_notification_task: asyncio.Task | None = None
        self._status_notification_last_signature: tuple[Any, ...] | None = None
        self._pv_below_since: datetime | None = None
        self._last_boiler_command_at: datetime | None = None
        self._high_load_since: datetime | None = None
        self._high_load_below_since: datetime | None = None
        self._frame_id = 0
        # Compteur interne monotone : ne doit jamais être remis à zéro à minuit,
        # car il protège la validation PRI N+1. _frame_id reste le numéro
        # journalier visible par l’utilisateur.
        self._frame_serial = 0
        self._high_load_high_frames = 0
        self._high_load_low_frames = 0
        self._sensor_reset_active = False
        self._valid_frames_after_reset = 0
        self.load_shed_state: dict[str, Any] = {
            "active": False,
            "reason": "Inactif",
            "triggered_at": None,
            "house_w": 0.0,
        }
        self._loaded_existing_state = False
        self.accounting = EnergyAccounting()

        super().__init__(
            hass,
            _LOGGER,
            name=f"FoxCat Energy {entry.entry_id}",
            update_interval=timedelta(seconds=30),
        )

    @property
    def installation_name(self) -> str:
        return str(self.config.get(CONF_INSTALLATION_NAME) or self.entry.title or "FoxCat Energy")


    def _financial_status_view(self, data: dict[str, Any]) -> dict[str, str]:
        """Retourne un état financier court et stable pour l'utilisateur.

        Cet indicateur résume la décision économique déjà calculée. Il ne
        commande aucun équipement et ne publie rien sur Energy Bus.
        """
        decision = dict(data.get("economic", {}).get("decision", {}) or {})
        code = str(decision.get("code") or "INCONNU")
        mapping = {
            "COMPENSATION_MAX_PV": ("COMPENSATION", "Production libre — compensation active"),
            "ABSORBER_SURPLUS": ("EXPORT DÉFAVORABLE", "Autoconsommation prioritaire"),
            "EXPORTER_ET_REPORTER": ("EXPORT FAVORABLE", "Réinjection rémunératrice"),
            "AUTOCONSOMMER": ("FAVORABLE", "Autoconsommation économiquement préférable"),
            "PRIX_ACHAT_NEGATIF": ("TRÈS FAVORABLE", "Consommation réseau avantageuse"),
            "ATTENDRE_MEILLEUR_PRIX": ("ATTENDRE", "Meilleur prix attendu"),
            "CONSOMMER_MAINTENANT": ("FAVORABLE", "Prix actuel intéressant"),
            "CONSOMMER_HC": ("FAVORABLE", "Heures creuses actives"),
            "ATTENDRE_HC": ("ATTENDRE", "Heures creuses recommandées"),
            "HP_ACCEPTABLE": ("ACCEPTABLE", "Consommation possible si nécessaire"),
            "PRIX_INDISPONIBLE": ("INDÉTERMINÉ", "Tarif indisponible"),
            "DESACTIVE": ("NON ÉVALUÉ", "Optimisation économique désactivée"),
        }
        status, detail = mapping.get(code, ("INFORMATION", str(decision.get("label") or code)))
        return {"status": status, "detail": detail, "code": code}

    def _status_notification_signature(self, data: dict[str, Any]) -> tuple[Any, ...]:
        """Empreinte des seules informations utiles à la notification persistante."""
        summary = data.get("status_summary", {})
        prices = data.get("prices", {})
        accounting = data.get("accounting", {}).get("today", {})
        return (
            summary.get("mode"),
            summary.get("network_policy"),
            summary.get("financial_status"),
            summary.get("economic_decision"),
            prices.get("regime"),
            prices.get("period"),
            round(float(prices.get("active_buy") or 0.0), 4),
            round(float(prices.get("export_value") or 0.0), 4),
            round(float(accounting.get("net_grid_cost_eur") or 0.0), 2),
        )

    async def async_refresh_persistent_status_notification(
        self, data: dict[str, Any] | None = None, *, force: bool = False
    ) -> None:
        """Crée ou remplace le résumé EMS persistant sans générer de doublons."""
        notification_id = f"foxcat_energy_status_{self.entry.entry_id}"
        if not bool(self.settings.get("persistent_status_notification_enabled", True)):
            persistent_notification.async_dismiss(self.hass, notification_id)
            self._status_notification_last_signature = None
            return

        payload = data or self.data or self._build_data()
        signature = self._status_notification_signature(payload)
        if not force and signature == self._status_notification_last_signature:
            return

        self._status_notification_last_signature = signature
        summary = payload.get("status_summary", {})
        prices = payload.get("prices", {})
        accounting = payload.get("accounting", {}).get("today", {})
        mode = str(summary.get("mode") or "Indisponible")
        policy = str(summary.get("network_policy") or "Indisponible")
        financial = str(summary.get("financial_status") or "Indéterminé")
        decision = str(summary.get("economic_decision") or "Indisponible")
        regime = str(prices.get("regime") or "Indisponible")
        period = str(prices.get("period") or "—")
        buy = prices.get("active_buy")
        export_value = prices.get("export_value")
        net_cost = float(accounting.get("net_grid_cost_eur") or 0.0)

        def euro_kwh(value: Any) -> str:
            try:
                return f"{float(value):.3f} €/kWh"
            except (TypeError, ValueError):
                return "Indisponible"

        message = (
            f"**Mode EMS :** {mode}\n\n"
            f"**Politique réseau :** {policy}\n\n"
            f"**État financier :** {financial}\n\n"
            f"**Décision économique :** {decision}\n\n"
            f"**Tarification :** {regime} — {period}\n\n"
            f"**Prix d'achat :** {euro_kwh(buy)}\n\n"
            f"**Valeur de réinjection :** {euro_kwh(export_value)}\n\n"
            f"**Coût net aujourd'hui :** {net_cost:.2f} €"
        )
        persistent_notification.async_create(
            self.hass,
            message,
            title=f"⚡ {self.installation_name} — Statut EMS",
            notification_id=notification_id,
        )

    @callback
    def async_set_updated_data(self, data: dict[str, Any]) -> None:
        """Met à jour les entités puis synchronise le résumé persistant."""
        # Ajout du résumé financier avant publication afin que le capteur, le
        # dashboard et la notification lisent exactement la même information.
        financial = self._financial_status_view(data)
        data.setdefault("status_summary", {})
        data["status_summary"].update(
            {
                "mode": data.get("settings", {}).get("mode", MODE_ECO),
                "network_policy": data.get("settings", {}).get("network_policy", NETWORK_POLICY_COMPENSATION),
                "financial_status": financial["status"],
                "financial_detail": financial["detail"],
                "financial_code": financial["code"],
                "economic_decision": data.get("economic", {}).get("decision", {}).get("label", "Indisponible"),
            }
        )
        super().async_set_updated_data(data)
        if not bool(self.settings.get("persistent_status_notification_enabled", True)):
            return
        signature = self._status_notification_signature(data)
        if signature == self._status_notification_last_signature:
            return
        if self._status_notification_task and not self._status_notification_task.done():
            self._status_notification_task.cancel()
        self._status_notification_task = self.hass.async_create_task(
            self.async_refresh_persistent_status_notification(data)
        )

    async def async_initialize(self) -> None:
        stored = await self._store.async_load()
        self._migration_notes = []
        if isinstance(stored, dict):
            raw = dict(stored.get("settings", {}) or {})
            if raw.get("configuration_model_version") != MIGRATION_MODEL_VERSION:
                raw, self._migration_notes = migrate_settings_v173(raw)
            self.settings.update(raw)
            option_settings = self._entry_option_settings()
            if stored.get("entry_option_settings") != option_settings:
                self.settings.update(option_settings)
            self._entry_options_snapshot = option_settings
            self.accounting.restore(stored.get("accounting"))
            self.machine_learning.restore(stored.get("machine_learning"))
            sf = stored.get("solar_forecast")
            if isinstance(sf, dict):
                self.solar_forecast = SolarForecast(**{k: sf.get(k, getattr(SolarForecast(), k)) for k in SolarForecast.__dataclass_fields__})
            self._loaded_existing_state = True
        else:
            self._migrate_legacy_defaults()
            self.settings.update(
                {
                    key: value
                    for key, value in self.entry.data.items()
                    if key in self.settings
                }
            )
            self.settings.update(
                {
                    key: value
                    for key, value in self.entry.options.items()
                    if key in self.settings
                }
            )
            self._entry_options_snapshot = self._entry_option_settings()

        # Les plages tarifaires sont des options de configuration. Elles sont
        # recopiées dans le contexte de stratégie à chaque chargement, sans
        # écraser les autres réglages persistants.
        for key in TIME_SETTING_KEYS:
            if key in self.config and self.config.get(key) not in (None, ""):
                self.settings[key] = str(self.config[key])
        for key in (CONF_TARIFF_FIXED_INJECTION_PRICE,):
            if key in self.config and self.config.get(key) not in (None, ""):
                try:
                    self.settings[key] = float(self.config[key])
                except (TypeError, ValueError):
                    pass

        # V1.3 : chaque machine extensible possède son propre interrupteur de gestion.
        # Les trois clés historiques restent utilisées pour les appareils migrés.
        for machine in self.machines:
            self.settings.setdefault(machine.setting_key, machine.automatic_default)

        self.settings["mode"] = MODE_ALIASES.get(str(self.settings.get("mode")), str(self.settings.get("mode")))
        self.metronome_state["period_s"] = float(self.settings.get("metronome_period_s", 30.0))
        await self._async_save()
        self._register_listeners()
        await self.async_config_entry_first_refresh()

        if bool(self.settings.get("regulation_active")):
            # Power-cut/startup fail-safe: release inverter to 100% before regulation resumes.
            await self.async_release_pri_100("Démarrage Home Assistant : fail-safe onduleur 100 %.")
            await self.async_reconcile_machines()

    async def async_shutdown(self) -> None:
        for unsub in self._unsubs:
            try:
                unsub()
            except Exception:  # pragma: no cover - defensive
                pass
        self._unsubs.clear()
        if self._pri_task and not self._pri_task.done():
            self._pri_task.cancel()
        if self._pri_actuator_task and not self._pri_actuator_task.done():
            self._pri_actuator_task.cancel()
        if self._boiler_command_task and not self._boiler_command_task.done():
            self._boiler_command_task.cancel()
        if self._execution_task and not self._execution_task.done():
            self._execution_task.cancel()
        if self._status_notification_task and not self._status_notification_task.done():
            self._status_notification_task.cancel()
        await self._async_save()

    def _migrate_legacy_defaults(self) -> None:
        for key, entity_id in LEGACY_SETTING_MAP.items():
            state = self.hass.states.get(entity_id)
            if state and state.state not in {"unknown", "unavailable", "none", ""}:
                try:
                    self.settings[key] = float(state.state)
                except (TypeError, ValueError):
                    pass
        for key, entity_id in LEGACY_SWITCH_MAP.items():
            state = self.hass.states.get(entity_id)
            if state:
                self.settings[key] = state.state == STATE_ON
        mode = self.hass.states.get(LEGACY_MODE_ENTITY)
        if mode:
            self.settings["mode"] = MODE_ALIASES.get(mode.state, mode.state)

    def _entry_option_settings(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self.entry.options.items()
            if key in self.settings
        }

    async def _async_save(self) -> None:
        await self._store.async_save(
            {
                "settings": self.settings,
                "entry_option_settings": self._entry_options_snapshot,
                "accounting": self.accounting.dump(),
                "machine_learning": self.machine_learning.dump(),
                "solar_forecast": {
                    "available": self.solar_forecast.available,
                    "start": self.solar_forecast.start,
                    "end": self.solar_forecast.end,
                    "confidence": self.solar_forecast.confidence,
                    "potential": self.solar_forecast.potential,
                    "trend": self.solar_forecast.trend,
                    "reason": self.solar_forecast.reason,
                    "raw": self.solar_forecast.raw,
                },
            }
        )

    def _register_listeners(self) -> None:
        # FoxCat 1.5.5 : métronome réseau interne.
        #
        # Le capteur choisi (Smappee consommation réseau recommandé) fournit le
        # battement physique. Sur les versions HA qui exposent state_reported,
        # une republication de la même valeur est elle aussi reconnue. Sinon le
        # watchdog se resynchronise sur State.last_reported/last_updated.
        clock_entities = list(dict.fromkeys(
            eid for eid in [
                self.metronome_state.get("primary_entity"),
                self.metronome_state.get("fallback_entity"),
            ] if eid
        ))
        if clock_entities:
            track_report = getattr(event_helper, "async_track_state_report_event", None)
            if callable(track_report):
                try:
                    self._unsubs.append(
                        track_report(self.hass, clock_entities, self._on_metronome_report)
                    )
                except (TypeError, AttributeError):
                    # Compatibilité HA : state_changed + watchdog metadata.
                    self._unsubs.append(
                        async_track_state_change_event(self.hass, clock_entities, self._on_metronome_report)
                    )
            else:
                self._unsubs.append(
                    async_track_state_change_event(self.hass, clock_entities, self._on_metronome_report)
                )

        # Le watchdog n'est pas une seconde horloge de décision : il observe
        # les timestamps de publication, active le fallback et crée un battement
        # interne uniquement lorsque le capteur physique n'a pas produit
        # d'événement exploitable mais reste frais.
        self._unsubs.append(
            async_track_time_interval(
                self.hass,
                self._on_metronome_watchdog,
                timedelta(seconds=2),
            )
        )

        # V1.6.1-101 : les compteurs visibles repartent chaque jour à zéro.
        # Le reset est purement journalier/diagnostic : les séquences techniques
        # internes utilisées pour les ACK N+1 restent monotones.
        self._unsubs.append(
            async_track_time_change(
                self.hass,
                self._on_daily_counter_reset,
                hour=0,
                minute=0,
                second=0,
            )
        )

        # Les changements import/export restent de la télémétrie immédiate.
        # Quand le métronome est actif, ils ne créent jamais une seconde marche PRI.
        grid_entities = list(dict.fromkeys(
            eid for eid in [
                self.config.get(CONF_GRID_SIGNED_SENSOR),
                self.config.get(CONF_GRID_EXPORT_SENSOR),
                self.config.get(CONF_GRID_IMPORT_SENSOR),
                self.config.get(CONF_GRID_LEGACY_SENSOR),
            ] if eid
        ))
        if grid_entities:
            self._unsubs.append(
                async_track_state_change_event(self.hass, grid_entities, self._on_grid_event)
            )

        machine_cycle_entities = [m.cycle_entity for m in self.machines if m.cycle_entity]
        safety_entities = [x for x in [
            self.config.get(CONF_BOILER_TEMP_SENSOR),
            self.config.get(CONF_BOILER_RESISTANCE_TEMP_SENSOR),
            self.config.get(CONF_BOILER_BINARY),
            self.config.get(CONF_BOILER_POWER_SENSOR),
            *machine_cycle_entities,
        ] if x]
        if safety_entities:
            self._unsubs.append(async_track_state_change_event(self.hass, safety_entities, self._on_safety_event))

        # V1.6.152 : télémétrie passive des prises machines. Les événements
        # alimentent uniquement l'historique d'apprentissage et ne cadencent
        # ni EMS Core ni Onduleur Core.
        machine_telemetry_entities = list(dict.fromkeys(
            entity_id
            for machine in self.machines
            for entity_id in (
                machine.switch_entity, machine.power_sensor,
                machine.current_sensor, machine.voltage_sensor,
            )
            if entity_id
        ))
        if machine_telemetry_entities:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, machine_telemetry_entities, self._on_machine_telemetry_event
                )
            )

        pv = self.config.get(CONF_PV_SENSOR)
        if pv:
            self._unsubs.append(async_track_state_change_event(self.hass, [pv], self._on_pv_event))

        price_entities = [
            eid
            for eid in [
                self.config.get(CONF_PRICE_CURRENT),
                self.config.get(CONF_PRICE_NEXT),
                self.config.get(CONF_PRICE_INJECTION),
                self.config.get(CONF_PRICE_MIN_TODAY),
                self.config.get(CONF_PRICE_MAX_TODAY),
                self.config.get(CONF_PRICE_AVG_TODAY),
                self.config.get(CONF_TARIFF_HP_PRICE_SENSOR),
                self.config.get(CONF_TARIFF_HC_PRICE_SENSOR),
                self.config.get(CONF_TARIFF_FIXED_INJECTION_PRICE_SENSOR),
            ]
            if eid
        ]
        if price_entities:
            self._unsubs.append(async_track_state_change_event(self.hass, price_entities, self._on_price_event))

        # V1.6.153 : les séries de prix futurs alimentent uniquement le
        # comparateur économique. Elles ne créent aucune trame EMS/PRI et ne
        # publient rien sur Energy Bus.
        economic_price_entities = [
            eid for eid in [
                self.config.get(CONF_PRICE_FORECAST_IMPORT),
                self.config.get(CONF_PRICE_FORECAST_EXPORT),
                self.config.get(CONF_PRICE_TOMORROW_AVAILABLE),
            ] if eid and eid not in price_entities
        ]
        if economic_price_entities:
            self._unsubs.append(
                async_track_state_change_event(
                    self.hass, economic_price_entities, self._on_economic_price_event
                )
            )

        # Les bornes HP/HC sont configurables. Chaque transition force une
        # nouvelle acquisition pour éviter une décision sur l'ancien tarif.
        for hour, minute in sorted(tariff_boundaries(self.settings)):
            self._unsubs.append(async_track_time_change(self.hass, self._on_tariff_boundary, hour=hour, minute=minute, second=0))

        # Machine socket schedule reconciliation aux bornes configurées.
        # Les doublons sont fusionnés afin de ne créer qu'un listener par heure.
        for hour, minute in sorted(self._machine_schedule_boundaries()):
            self._unsubs.append(async_track_time_change(self.hass, self._on_machine_schedule, hour=hour, minute=minute, second=0))

        # IA prédictive schedule.
        for hour, minute, label in (
            (7, 0, "STRATÉGIE JOUR - TRANSITION HP 07:00"),
            (10, 30, "CONFIRMATION SOLAIRE 10:30"),
            (11, 0, "RÉÉVALUATION - TRANSITION HC 11:00"),
            (15, 0, "FAILSAFE THERMIQUE - 15:00 AVANT FIN HC"),
            (17, 0, "RÉÉVALUATION - TRANSITION HP 17:00"),
            (22, 0, "RÉÉVALUATION - TRANSITION HC NUIT 22:00"),
        ):
            self._unsubs.append(async_track_time_change(self.hass, lambda now, lbl=label: self.hass.async_create_task(self.async_analyze_solar(lbl)), hour=hour, minute=minute, second=0))

    @callback
    def _on_house_event(self, event: Event) -> None:
        """Compatibilité interne : une variation maison ne cadence plus le CORE."""
        self.async_set_updated_data(self._build_data())

    @staticmethod
    def _state_report_at(state: Any) -> datetime | None:
        """Retourne le dernier instant de publication réel connu d'une entité."""
        if state is None:
            return None
        reported = getattr(state, "last_reported", None)
        if isinstance(reported, datetime):
            return reported
        updated = getattr(state, "last_updated", None)
        return updated if isinstance(updated, datetime) else None

    def _metronome_entity_fresh(self, entity_id: str | None, now: datetime, timeout_s: float) -> bool:
        if not entity_id:
            return False
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable", "none", ""}:
            return False
        reported_at = self._state_report_at(state)
        if not isinstance(reported_at, datetime):
            return False
        return (now - reported_at).total_seconds() <= timeout_s

    @callback
    def _on_daily_counter_reset(self, now: datetime) -> None:
        """Déclenche le reset journalier des compteurs visibles à minuit."""
        self.hass.async_create_task(self._async_daily_counter_reset(now))

    async def _async_daily_counter_reset(self, now: datetime) -> None:
        """Réinitialise les séquences journalières sans casser les ACK internes."""
        local_now = dt_util.as_local(now)
        today = local_now.date().isoformat()
        previous_date = str(self.metronome_state.get("counter_date") or "")
        if previous_date == today:
            return

        previous_pulses = int(self.metronome_state.get("pulse_count", 0))
        previous_primary = int(self.metronome_state.get("primary_report_count", 0))
        previous_fallback = int(self.metronome_state.get("fallback_report_count", 0))
        previous_frames = int(self._frame_id)
        bus_summary = self.energy_bus.reset_daily_counters(local_now)

        self.metronome_state.update({
            "counter_date": today,
            "last_daily_reset_at": local_now,
            "previous_day_pulse_count": previous_pulses,
            "previous_day_primary_report_count": previous_primary,
            "previous_day_fallback_report_count": previous_fallback,
            "previous_day_frame_count": previous_frames,
            "previous_day_message_count": int(bus_summary.get("previous_day_message_count", 0)),
            "pulse_count": 0,
            "primary_report_count": 0,
            "fallback_report_count": 0,
            "last_reason": (
                "Métronome : reset journalier à minuit — "
                f"{previous_pulses} battement(s), {previous_frames} trame(s), "
                f"{int(bus_summary.get('previous_day_message_count', 0))} message(s) archivés."
            ),
        })
        self._frame_id = 0
        self.pri_state["frame_id"] = 0
        self.core_state["bus_message_id"] = None
        self.async_set_updated_data(self._build_data())
        await self._async_save()

    @callback
    def _on_metronome_report(self, event: Event) -> None:
        """Capture un heartbeat du capteur principal ou de secours."""
        entity_id = str(event.data.get("entity_id", ""))
        if not entity_id:
            return
        state = event.data.get("new_state") or self.hass.states.get(entity_id)
        reported_at = self._state_report_at(state) or dt_util.now()
        self.hass.async_create_task(
            self._async_metronome_report(entity_id, reported_at, "event")
        )

    @callback
    def _on_metronome_watchdog(self, now: datetime) -> None:
        self.hass.async_create_task(self._async_metronome_watchdog(now))

    async def _async_metronome_watchdog(self, now: datetime) -> None:
        """Surveille la fraîcheur, détecte les republications et gère le fallback."""
        local_today = dt_util.as_local(now).date().isoformat()
        if str(self.metronome_state.get("counter_date") or "") != local_today:
            await self._async_daily_counter_reset(now)

        expired_frames = self.energy_bus.expire_frames(now=now, timeout_s=10.0)
        if expired_frames:
            self.metronome_state["last_reason"] = (
                "Watchdog : trame(s) non clôturée(s) détectée(s) et marquée(s) TIMEOUT : "
                + ", ".join(f"{fid}/{core}" for fid, core in expired_frames)
            )

        primary = str(self.metronome_state.get("primary_entity") or "")
        fallback = str(self.metronome_state.get("fallback_entity") or "")

        # last_reported évolue même quand la valeur numérique ne change pas sur
        # les versions HA récentes. Cela ferme précisément le cas 100 -> 90 puis
        # blocage sur une réinjection stable.
        for entity_id in (primary, fallback):
            if not entity_id:
                continue
            state = self.hass.states.get(entity_id)
            reported_at = self._state_report_at(state)
            if not isinstance(reported_at, datetime):
                continue
            previous = self._metronome_last_seen_report.get(entity_id)
            if previous is None or reported_at > previous:
                await self._async_metronome_report(entity_id, reported_at, "watchdog")

        period = max(float(self.settings.get("metronome_period_s", 30.0)), 10.0)
        primary_timeout = max(float(self.settings.get("metronome_primary_timeout_s", 45.0)), period)
        fallback_timeout = max(float(self.settings.get("metronome_fallback_timeout_s", 90.0)), primary_timeout)
        primary_fresh = self._metronome_entity_fresh(primary, now, primary_timeout)
        fallback_fresh = self._metronome_entity_fresh(fallback, now, fallback_timeout)

        if not primary_fresh and fallback_fresh:
            self.metronome_state["status"] = "FALLBACK"
            self.metronome_state["source"] = "SECOURS"
            self.metronome_state["last_reason"] = (
                "Capteur principal muet : fallback armé. Seule une publication réelle "
                "du capteur de secours déclenche une nouvelle trame."
            )
            return

        if primary_fresh:
            self.metronome_state["status"] = "SYNCHRONISE"
            self.metronome_state["source"] = "PRINCIPAL"
            self.metronome_state["last_reason"] = (
                "Source principale fraîche : Watchdog actif, aucune trame synthétique."
            )
            return

        # Aucun capteur frais : on gèle les décisions plutôt que d'utiliser
        # aveuglément des données réseau anciennes.
        self.metronome_state["status"] = "PERDU"
        self.metronome_state["source"] = "AUCUNE"
        self.metronome_state["last_reason"] = "Principal et secours périmés : aucune publication réseau, EMS/PRI gelés par sécurité."
        self.pri_state["guard_reason"] = "metronome_perdu"
        self.async_set_updated_data(self._build_data())

    async def _async_metronome_report(self, entity_id: str, reported_at: datetime, origin: str) -> None:
        """Traite chaque publication physique comme une trame réseau souveraine.

        V1.6.150 : aucune temporisation de 30 s n'est appliquée aux publications
        réelles. Le métronome est un Watchdog de fraîcheur, pas une horloge de
        décision. Une publication acceptée cadence simultanément EMS Core et
        Onduleur Core sur le même snapshot.
        """
        async with self._metronome_lock:
            previous = self._metronome_last_seen_report.get(entity_id)
            if previous is not None and reported_at <= previous:
                return
            self._metronome_last_seen_report[entity_id] = reported_at

            primary = str(self.metronome_state.get("primary_entity") or "")
            fallback = str(self.metronome_state.get("fallback_entity") or "")
            now = dt_util.now()
            period = max(float(self.settings.get("metronome_period_s", 30.0)), 10.0)
            primary_timeout = max(float(self.settings.get("metronome_primary_timeout_s", 45.0)), period)
            fallback_timeout = max(float(self.settings.get("metronome_fallback_timeout_s", 90.0)), primary_timeout)

            if entity_id == primary:
                self.metronome_state["primary_last_report_at"] = reported_at
                self.metronome_state["primary_report_count"] = int(self.metronome_state.get("primary_report_count", 0)) + 1
                source = "principal"
            elif entity_id == fallback:
                self.metronome_state["fallback_last_report_at"] = reported_at
                self.metronome_state["fallback_report_count"] = int(self.metronome_state.get("fallback_report_count", 0)) + 1
                source = "secours"
            else:
                return

            report_age = max((now - reported_at).total_seconds(), 0.0)
            if source == "principal" and report_age > primary_timeout:
                self.metronome_state["last_reason"] = "Publication principale trop ancienne : attente du fallback."
                return
            if source == "secours" and report_age > fallback_timeout:
                self.metronome_state["last_reason"] = "Publication fallback trop ancienne : trame rejetée."
                return

            primary_fresh = self._metronome_entity_fresh(primary, now, primary_timeout)
            if source == "secours" and primary_fresh:
                self.metronome_state["last_reason"] = "Publication fallback reçue; principal toujours souverain."
                self.async_set_updated_data(self._build_data())
                return

        # Le verrou métronome est libéré AVANT les deux corps. Le dispatch crée
        # une seule photographie puis lance les deux moteurs indépendamment.
        await self._async_metronome_pulse(entity_id, f"{source}_{origin}", now)

    async def _async_metronome_pulse(self, entity_id: str, source: str, pulse_at: datetime) -> None:
        """Transforme une publication réseau en UNE trame partagée par les deux corps."""
        async with self._frame_dispatch_lock:
            self.metronome_state.update({
                "status": "FALLBACK" if "fallback" in source or "secours" in source else "SYNCHRONISE",
                "source": "SECOURS" if "fallback" in source or "secours" in source else "PRINCIPAL",
                "last_pulse_at": pulse_at,
                "last_pulse_source": source,
                "pulse_count": int(self.metronome_state.get("pulse_count", 0)) + 1,
                "period_s": float(self.settings.get("metronome_period_s", 30.0)),
                "next_due_at": None,
                "last_reason": f"Publication réseau {entity_id} ({source}) : trame immédiate.",
            })

            # Une seule séquence de trame et un seul snapshot pour EMS + Onduleur.
            self._frame_id += 1
            self._frame_serial += 1
            frame_id = self._frame_id
            frame_serial = self._frame_serial
            snapshot = self.snapshot()
            # La collecte machine est alimentée par la même photographie réseau,
            # mais reste strictement observatrice.
            self._record_machine_learning(snapshot=snapshot, now=pulse_at, source="GRID_FRAME")
            machine_context = self._machine_bus_context(pulse_at)
            self.energy_bus.on_grid_frame(
                frame_id, pulse_at, source=entity_id, frame_serial=frame_serial,
                grid_net_w=snapshot.grid_net_w, pv_w=snapshot.pv_w, house_w=snapshot.house_w,
                import_w=snapshot.import_w, export_w=snapshot.export_w, valid=snapshot.valid,
                boiler_power_w=snapshot.boiler_power_w, boiler_temp_c=snapshot.boiler_temp_c,
                boiler_on=snapshot.boiler_on, machine_active=snapshot.machine_active,
                machine_context=machine_context,
                mode=str(self.settings.get("mode")),
                network_policy=str(self.settings.get("network_policy")),
            )

        # Les deux tasks partent du même snapshot mais n'attendent jamais l'autre.
        self.hass.async_create_task(
            self._run_dispatched_core(
                "ONDULEUR", frame_id,
                self.async_handle_inverter_grid_frame(
                    f"{entity_id}:{source}", snapshot=snapshot, frame_id=frame_id,
                    frame_serial=frame_serial, frame_at=pulse_at,
                ),
            )
        )
        self.hass.async_create_task(
            self._run_dispatched_core(
                "EMS", frame_id,
                self.async_handle_house_frame(
                    snapshot=snapshot, frame_id=frame_id, frame_serial=frame_serial,
                    frame_at=pulse_at, source_entity=f"{entity_id}:{source}",
                ),
            )
        )

    async def _run_dispatched_core(self, core: str, frame_id: int, task: Any) -> None:
        """Garantit qu'une exception de moteur ne laisse jamais une trame PENDING."""
        try:
            await task
        except asyncio.CancelledError:
            self.energy_bus.mark_frame_core(
                frame_id, core, "CANCELLED", now=dt_util.now(), reason="Task annulée."
            )
            raise
        except Exception as err:  # pragma: no cover - garde runtime HA
            _LOGGER.exception("FoxCat %s Core frame %s error: %s", core, frame_id, err)
            self.energy_bus.mark_frame_core(
                frame_id, core, "ERROR", now=dt_util.now(), reason=str(err)
            )
            if core == "EMS":
                self.core_state["last_reason"] = f"EMS Core : erreur trame {frame_id} : {err}"
            else:
                self.pri_state["last_reason"] = f"Onduleur Core : erreur trame {frame_id} : {err}"
            self.async_set_updated_data(self._build_data())

    @callback
    def _on_grid_event(self, event: Event) -> None:
        entity_id = str(event.data.get("entity_id", ""))
        signed_id = str(self.config.get(CONF_GRID_SIGNED_SENSOR) or "")
        export_id = str(self.config.get(CONF_GRID_EXPORT_SENSOR) or "")
        legacy_id = str(self.config.get(CONF_GRID_LEGACY_SENSOR) or "")
        inverter_clock = signed_id or export_id or legacy_id

        # Le métronome synchronisé reste l'unique horloge PRI. Les événements
        # réseau mettent immédiatement les données à jour sans créer un second
        # battement. La voie historique n'est utilisée que sans métronome.
        metronome_clock = str(self.metronome_state.get("primary_entity") or "")
        if not metronome_clock and entity_id and entity_id == inverter_clock:
            # Compatibilité legacy : même sans métronome configuré, une
            # publication réseau cadence désormais LES DEUX corps.
            self.hass.async_create_task(
                self._async_metronome_pulse(entity_id, "legacy_event", dt_util.now())
            )
        else:
            self.hass.async_create_task(self.async_handle_grid_change())

    @callback
    def _on_safety_event(self, event: Event) -> None:
        self.hass.async_create_task(self.async_handle_safety_change())

    @callback
    def _on_machine_telemetry_event(self, event: Event) -> None:
        """Collecte passive : aucun appel de décision ni commande physique."""
        now = dt_util.now()
        snapshot = self.snapshot()
        self._record_machine_learning(snapshot=snapshot, now=now, source="TELEMETRY_EVENT")
        self.async_set_updated_data(self._build_data(snapshot))

    @callback
    def _on_pv_event(self, event: Event) -> None:
        self.hass.async_create_task(self.async_handle_pv_change())

    @callback
    def _on_price_event(self, event: Event) -> None:
        self.hass.async_create_task(self.async_handle_price_change())

    @callback
    def _on_economic_price_event(self, event: Event) -> None:
        """Rafraîchit le Day-Ahead; en Dynamique, réévalue les nouveaux départs machines."""
        self.async_set_updated_data(self._build_data())
        if (
            bool(self.settings.get("regulation_active"))
            and str(self.settings.get("mode")) == MODE_DYNAMIC
            and str(self.settings.get("tariff_regime")) == TARIFF_DYNAMIC
        ):
            self.hass.async_create_task(self.async_reconcile_machines())

    @callback
    def _on_tariff_boundary(self, now: datetime) -> None:
        self.reset_core("Transition tarifaire : nouvelle acquisition demandée.")
        self.async_set_updated_data(self._build_data())

    @callback
    def _on_machine_schedule(self, now: datetime) -> None:
        self.hass.async_create_task(self.async_reconcile_machines())

    async def _async_update_data(self) -> dict[str, Any]:
        await self._watchdog()
        await self._check_end_solar()
        if bool(self.settings.get("regulation_active")):
            await self._evaluate_high_load(self.snapshot())
        return self._build_data()

    def _float_state(self, entity_id: str | None, default: float = 0.0) -> float:
        if not entity_id:
            return default
        state = self.hass.states.get(entity_id)
        if not state or state.state in {"unknown", "unavailable", "none", ""}:
            return default
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return default

    def _optional_float_state(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if not state or state.state in {"unknown", "unavailable", "none", ""}:
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    def _is_on(self, entity_id: str | None) -> bool:
        state = self.hass.states.get(entity_id) if entity_id else None
        return bool(state and state.state == STATE_ON)

    def _numeric_valid(self, entity_id: str | None) -> bool:
        return self._optional_float_state(entity_id) is not None

    def snapshot(self) -> EnergySnapshot:
        """Build the sovereign FoxCat energy snapshot.

        V1.6.0 uses two mandatory physical measurements:
        - signed grid power;
        - photovoltaic production.

        Import, export and house consumption are derived by FoxCat.  Existing
        pre-1.6 installations without ``grid_signed_sensor`` keep the legacy
        four-sensor path until the Sources énergétiques page is saved.
        """
        pv_id = self.config.get(CONF_PV_SENSOR)
        pv = max(self._float_state(pv_id), 0.0)

        primary_grid_id = self.config.get(CONF_GRID_SIGNED_SENSOR)
        fallback_grid_id = self.config.get(CONF_METRONOME_FALLBACK_SENSOR)
        signed_grid_id = primary_grid_id
        now = dt_util.now()
        primary_fresh = self._metronome_entity_fresh(
            primary_grid_id,
            now,
            float(self.settings.get("metronome_primary_timeout_s", 45.0)),
        ) if primary_grid_id else False
        fallback_fresh = self._metronome_entity_fresh(
            fallback_grid_id,
            now,
            float(self.settings.get("metronome_fallback_timeout_s", 90.0)),
        ) if fallback_grid_id else False

        # Le fallback V1.6 est lui aussi une puissance réseau signée. Quand le
        # principal n'est plus frais, valeur + cadence basculent ensemble.
        if fallback_grid_id and fallback_fresh and (
            self.metronome_state.get("source") == "SECOURS" or not primary_fresh
        ):
            signed_grid_id = fallback_grid_id

        if signed_grid_id:
            raw_grid = self._float_state(signed_grid_id)
            convention = str(self.config.get(CONF_GRID_SIGN_CONVENTION, GRID_SIGN_IMPORT_POSITIVE))
            if convention == GRID_SIGN_EXPORT_POSITIVE:
                export = max(raw_grid, 0.0)
                imp = max(-raw_grid, 0.0)
            else:
                imp = max(raw_grid, 0.0)
                export = max(-raw_grid, 0.0)
            # Conservation of power at the point of common coupling.
            house = max(pv + imp - export, 0.0)
            active_fresh = fallback_fresh if signed_grid_id == fallback_grid_id else primary_fresh
            valid = (
                self._numeric_valid(pv_id)
                and self._numeric_valid(signed_grid_id)
                and active_fresh
            )
        else:
            # Migration fallback for installations created before 1.6.0.
            house_id = self.config.get(CONF_HOUSE_SENSOR)
            export_id = self.config.get(CONF_GRID_EXPORT_SENSOR)
            import_id = self.config.get(CONF_GRID_IMPORT_SENSOR)
            house = max(self._float_state(house_id), 0.0)
            export = max(self._float_state(export_id), 0.0)
            imp = max(self._float_state(import_id), 0.0)
            valid = all(self._numeric_valid(eid) for eid in [pv_id, house_id, export_id, import_id])

        boiler_power = max(self._float_state(self.config.get(CONF_BOILER_POWER_SENSOR)), 0.0)
        boiler_binary = self._is_on(self.config.get(CONF_BOILER_BINARY))
        boiler_on = boiler_binary or boiler_power > 200
        boiler_temp = self._float_state(self.config.get(CONF_BOILER_TEMP_SENSOR))

        # V1.6.154 : la sonde placée sur la résistance est la référence de
        # sécurité thermique lorsqu'elle est configurée et valide. La sonde
        # boiler historique reste la référence de régulation ECS et le secours
        # de sécurité pour garantir la compatibilité des installations existantes.
        resistance_id = self.config.get(CONF_BOILER_RESISTANCE_TEMP_SENSOR)
        resistance_temp = self._optional_float_state(resistance_id) if resistance_id else None
        boiler_safety_temp = resistance_temp if resistance_temp is not None else boiler_temp
        boiler_safety_source = "RESISTANCE" if resistance_temp is not None else "REFERENCE"

        # La puissance physique onduleur est lue au moment du snapshot mais ne
        # cadence jamais EMS Core ni Onduleur Core. Le rôle de registre direct
        # reste disponible au dashboard pour un affichage réellement live.
        inverter_power = max(self._float_state(self.config.get(CONF_INVERTER_POWER_SENSOR)), 0.0)

        climate = self.hass.states.get(self.config.get(CONF_BOILER_CLIMATE)) if self.config.get(CONF_BOILER_CLIMATE) else None
        try:
            setpoint = float(climate.attributes.get("temperature", self.settings["boiler_temp_normal_c"])) if climate else float(self.settings["boiler_temp_normal_c"])
        except (TypeError, ValueError):
            setpoint = float(self.settings["boiler_temp_normal_c"])
        machine_active = any(
            self._is_on(machine.cycle_entity)
            for machine in self.machines
            if machine.cycle_entity
        )
        return EnergySnapshot(
            timestamp=dt_util.now(),
            pv_w=pv,
            house_w=house,
            export_w=export,
            import_w=imp,
            # Internal historical FoxCat convention: + export / - import.
            grid_net_w=export - imp,
            boiler_temp_c=boiler_temp,
            boiler_safety_temp_c=boiler_safety_temp,
            boiler_power_w=boiler_power,
            inverter_power_w=inverter_power,
            boiler_on=boiler_on,
            boiler_setpoint_c=setpoint,
            machine_active=machine_active,
            valid=valid,
            raw={
                "boiler_resistance_temp_c": resistance_temp,
                "boiler_safety_source": boiler_safety_source,
                "inverter_power_w": inverter_power,
            },
        )

    def _boiler_thermal_view(self, snapshot: EnergySnapshot | None = None) -> dict[str, Any]:
        """Modèle thermique physique du Boiler, destiné à l'arbitrage DYNAMIQUE.

        Ce calcul est purement descriptif hors régime dynamique : il n'altère
        ni HP/HC, ni les sécurités, ni la comptabilité. La constante 1.163
        représente l'énergie en Wh nécessaire pour élever 1 litre d'eau de 1 °C.
        """
        snap = snapshot or self.snapshot()
        try:
            volume_l = max(float(self.config.get(CONF_BOILER_VOLUME, 250.0)), 0.0)
        except (TypeError, ValueError):
            volume_l = 250.0
        try:
            element_power_w = max(
                float(self.config.get(CONF_BOILER_ELEMENT_POWER, self.settings.get("boiler_power_w", 2000.0))),
                0.0,
            )
        except (TypeError, ValueError):
            element_power_w = max(float(self.settings.get("boiler_power_w", 2000.0)), 0.0)
        try:
            cold_water_c = float(self.config.get(CONF_BOILER_COLD_WATER_TEMP, 15.0))
        except (TypeError, ValueError):
            cold_water_c = 15.0

        target_c = max(float(self.settings.get("boiler_temp_normal_c", 45.0)), 0.0)
        measured_c = float(snap.boiler_temp_c)
        delta_c = max(target_c - measured_c, 0.0)
        energy_missing_kwh = max(volume_l * 1.163 * delta_c / 1000.0, 0.0)
        heating_duration_h = (energy_missing_kwh / (element_power_w / 1000.0)) if element_power_w > 0 else None
        capacity_comfort_kwh = max(volume_l * 1.163 * max(target_c - cold_water_c, 0.0) / 1000.0, 0.0)

        return {
            "volume_l": round(volume_l, 3),
            "element_power_w": round(element_power_w, 3),
            "cold_water_temp_c": round(cold_water_c, 3),
            "measured_temp_c": round(measured_c, 3),
            "target_temp_c": round(target_c, 3),
            "comfort_min_c": float(self.settings.get("boiler_temp_start_c", 43.0)),
            "energy_missing_kwh": round(energy_missing_kwh, 5),
            "heating_duration_h": round(heating_duration_h, 5) if heating_duration_h is not None else None,
            "thermal_capacity_comfort_kwh": round(capacity_comfort_kwh, 5),
        }

    def _boiler_on_seconds(self) -> float:
        """Return trusted physical ON duration for the boiler.

        The binary sensor is the sovereign cycle clock.  If power is already
        present but the binary sensor is not ON, the elapsed time is unknown:
        return 0 s rather than inventing a duration from the power sensor.
        """
        entity_id = self.config.get(CONF_BOILER_BINARY)
        state = self.hass.states.get(entity_id) if entity_id else None
        if state and state.state == STATE_ON:
            return max((dt_util.utcnow() - state.last_changed).total_seconds(), 0.0)
        power_id = self.config.get(CONF_BOILER_POWER_SENSOR)
        if self._float_state(power_id) > 200:
            return 0.0
        return 999999.0

    def prices(self) -> dict[str, Any]:
        now=dt_util.now(); dims=tariff_dimensions(self.settings); regime=compatibility_tariff_regime(self.settings)
        cur=self._optional_float_state(self.config.get(CONF_PRICE_CURRENT)); nxt=self._optional_float_state(self.config.get(CONF_PRICE_NEXT)); inj=self._optional_float_state(self.config.get(CONF_PRICE_INJECTION))
        hp=self._optional_float_state(self.config.get(CONF_TARIFF_HP_PRICE_SENSOR)); hc=self._optional_float_state(self.config.get(CONF_TARIFF_HC_PRICE_SENSOR))
        hp=float(self.settings.get(CONF_TARIFF_HP_PRICE,.35)) if dims.price_source==PRICE_SOURCE_CONTRACT else hp
        hc=float(self.settings.get(CONF_TARIFF_HC_PRICE,.25)) if dims.price_source==PRICE_SOURCE_CONTRACT else hc
        hp=final_client_price(hp,now,self.settings) if hp is not None else None; hc=final_client_price(hc,now,self.settings) if hc is not None else None
        cur=final_client_price(cur,now,self.settings) if cur is not None else None; nxt=final_client_price(nxt,now+timedelta(hours=1),self.settings) if nxt is not None else None
        period=tariff_period(now,self.settings) if dims.structure==TARIFF_STRUCTURE_TOU else ('IMPACT' if dims.structure==TARIFF_STRUCTURE_IMPACT else 'SIMPLE')
        if dims.dynamic: active=cur; next_buy=nxt; label='DYNAMIQUE'; nlabel='SUIVANT'
        elif dims.structure==TARIFF_STRUCTURE_TOU: active=hp if period=='HP' else hc; next_buy=hc if period=='HP' else hp; label=period; nlabel='HC' if period=='HP' else 'HP'
        else: active=final_client_price(float(self.settings.get(CONF_TARIFF_SIMPLE_PRICE,.30)),now,self.settings) if dims.price_source==PRICE_SOURCE_CONTRACT else cur; next_buy=nxt or active; label='SIMPLE'; nlabel='SUIVANT'
        if dims.network_policy in {NETWORK_POLICY_NOT_VALUED,NETWORK_POLICY_ZERO_INJECTION}: export_value=0.0
        elif dims.network_policy==NETWORK_POLICY_BILLED_EXPORT: export_value=inj if dims.dynamic else float(self.settings.get(CONF_TARIFF_FIXED_INJECTION_PRICE,0))
        else: export_value=inj if dims.dynamic else float(self.settings.get(CONF_TARIFF_FIXED_INJECTION_PRICE,0))
        return {'current':cur,'next':nxt,'injection':inj,'hp_price':hp,'hc_price':hc,'fixed_injection_price':float(self.settings.get(CONF_TARIFF_FIXED_INJECTION_PRICE,0)),'min_today':self._optional_float_state(self.config.get(CONF_PRICE_MIN_TODAY)),'max_today':self._optional_float_state(self.config.get(CONF_PRICE_MAX_TODAY)),'avg_today':self._optional_float_state(self.config.get(CONF_PRICE_AVG_TODAY)),'min_tomorrow':self._optional_float_state(self.config.get(CONF_PRICE_MIN_TOMORROW)),'max_tomorrow':self._optional_float_state(self.config.get(CONF_PRICE_MAX_TOMORROW)),'avg_tomorrow':self._optional_float_state(self.config.get(CONF_PRICE_AVG_TOMORROW)),'price_source':dims.price_source,'tariff_structure':dims.structure,'network_policy':dims.network_policy,'regime':regime,'period':period,'active_buy':active,'next_buy':next_buy,'active_buy_label':label,'next_buy_label':nlabel,'export_value':export_value,'dynamic_compatible':dims.dynamic,'negative_purchase':bool(active is not None and active<0)}

    def _economic_import_points(
        self, prices: dict[str, Any], now: datetime
    ) -> list[PricePoint]:
        regime = str(prices.get("regime", TARIFF_TOU))
        horizon = (
            DYNAMIC_ARBITRAGE_HORIZON_HOURS
            if regime == TARIFF_DYNAMIC
            else int(float(self.settings.get("economic_horizon_hours", 24.0)))
        )
        if not tariff_dimensions(self.settings).dynamic and regime != TARIFF_TOU:
            if tariff_dimensions(self.settings).price_source == PRICE_SOURCE_CONTRACT:
                base = self.settings.get(CONF_TARIFF_SIMPLE_PRICE, 0.30)
            else:
                base = self._optional_float_state(self.config.get(CONF_PRICE_CURRENT))
            if not isinstance(base, (int, float)):
                base = prices.get("active_buy")
            if not isinstance(base, (int, float)):
                return []
            return [
                PricePoint(
                    now + timedelta(hours=hour),
                    final_client_price(float(base), now + timedelta(hours=hour), self.settings),
                    "NON_DYNAMIC_FIXED",
                )
                for hour in range(horizon + 1)
            ]
        if regime == TARIFF_TOU:
            return build_hphc_points(
                now,
                self.settings,
                prices.get("hp_price") if isinstance(prices.get("hp_price"), (int, float)) else None,
                prices.get("hc_price") if isinstance(prices.get("hc_price"), (int, float)) else None,
                horizon_hours=horizon,
            )

        source_entity = self.config.get(CONF_PRICE_FORECAST_IMPORT) or self.config.get(CONF_PRICE_CURRENT)
        series = self._economic_series_from_entity(
            source_entity, source="DYNAMIC_IMPORT", now=now, horizon_hours=horizon,
            preferred_price_keys=("all_in",),
        )
        current = prices.get("active_buy")
        nxt = prices.get("next_buy")
        manual: list[PricePoint] = []
        slot = now.replace(minute=0, second=0, microsecond=0)
        if isinstance(current, (int, float)):
            manual.append(PricePoint(slot, float(current), "DYNAMIC_CURRENT"))
        if isinstance(nxt, (int, float)):
            manual.append(PricePoint(slot + timedelta(hours=1), float(nxt), "DYNAMIC_NEXT"))
        return merge_price_points(series, manual)

    def _economic_series_from_entity(
        self,
        entity_id: str | None,
        *,
        source: str,
        now: datetime,
        horizon_hours: int,
        preferred_price_keys: tuple[str, ...] = (),
    ) -> list[PricePoint]:
        """Extract a provider price curve without treating missing data as prices."""
        if not entity_id:
            return []
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable", "none", ""}:
            return []
        raw = dict(state.attributes)
        if state.attributes:
            raw.setdefault("state", state.state)
        else:
            raw = state.state
        points = extract_price_points(
            raw,
            now,
            source=source,
            horizon_hours=horizon_hours,
            preferred_price_keys=preferred_price_keys,
        )
        for key in preferred_price_keys:
            curve = state.attributes.get(key)
            if isinstance(curve, (dict, list, tuple)):
                points.extend(
                    extract_price_points(
                        curve,
                        now,
                        source=source,
                        horizon_hours=horizon_hours,
                        preferred_price_keys=preferred_price_keys,
                    )
                )
        points = merge_price_points(points)
        if source == "DYNAMIC_IMPORT":
            return apply_final_price_components(points, self.settings)
        return points

    def _economic_export_points(
        self, prices: dict[str, Any], now: datetime
    ) -> list[PricePoint]:
        """Retourne la VALEUR économique de l'export, positive = recette."""
        regime = str(prices.get("regime", TARIFF_TOU))
        horizon = (
            DYNAMIC_ARBITRAGE_HORIZON_HOURS
            if regime == TARIFF_DYNAMIC
            else int(float(self.settings.get("economic_horizon_hours", 24.0)))
        )
        if not tariff_dimensions(self.settings).dynamic:
            value = prices.get("export_value")
            if not isinstance(value, (int, float)):
                return []
            return [
                PricePoint(now + timedelta(hours=hour), float(value), "NON_DYNAMIC_EXPORT")
                for hour in range(horizon + 1)
            ]
        if regime == TARIFF_TOU:
            value = prices.get("export_value")
            if not isinstance(value, (int, float)):
                return []
            return [
                PricePoint(now + timedelta(hours=hour), float(value), "HP_HC_EXPORT")
                for hour in range(horizon + 1)
            ]

        source_entity = self.config.get(CONF_PRICE_FORECAST_EXPORT) or self.config.get(CONF_PRICE_INJECTION)
        raw = self._economic_series_from_entity(
            source_entity, source="DYNAMIC_EXPORT_RAW", now=now, horizon_hours=horizon,
            preferred_price_keys=("injection",),
        )
        # Même convention effective que prices(), avec détection Luminus Dynamic.
        source_name = str(source_entity or "").lower()
        if "luminus_luminus_dynamic" in source_name:
            export_sign = DYNAMIC_EXPORT_POSITIVE_IS_REVENUE
        else:
            export_sign = str(self.config.get(CONF_DYNAMIC_EXPORT_SIGN_CONVENTION, DYNAMIC_EXPORT_POSITIVE_IS_REVENUE))
        factor = 1.0 if export_sign == DYNAMIC_EXPORT_POSITIVE_IS_REVENUE else -1.0
        normalised = [PricePoint(p.at, factor * float(p.price), "DYNAMIC_EXPORT") for p in raw]
        current = prices.get("export_value")
        if isinstance(current, (int, float)):
            normalised.append(
                PricePoint(now.replace(minute=0, second=0, microsecond=0), float(current), "DYNAMIC_EXPORT_CURRENT")
            )
        return merge_price_points(normalised)

    def _economic_view(
        self,
        snapshot: EnergySnapshot | None = None,
        *,
        prices: dict[str, Any] | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Construit la décision économique hors Energy Bus.

        Cette couche peut autoriser/report­er le NOUVEAU démarrage automatique
        d'une charge flexible. Elle ne modifie ni PRI, ni Onduleur Core, ni
        machine à états des cycles et ne publie aucun message inter-cœurs.
        """
        now = now or dt_util.now()
        snap = snapshot or self.snapshot()
        tariff = prices or self.prices()
        import_points = self._economic_import_points(tariff, now)
        export_points = self._economic_export_points(tariff, now)
        boiler_thermal = self._boiler_thermal_view(snap)
        decision = evaluate_market(
            now=now,
            snapshot=snap,
            prices=tariff,
            settings=self.settings,
            import_points=import_points,
            export_points=export_points,
            boiler_thermal=boiler_thermal,
        ).as_dict()

        learning = self.machine_learning.view()
        cycles = self.machine_cycle_manager.snapshot(now)
        recommendations: dict[str, Any] = {}
        for machine in self.machines:
            profile = learning.get(machine.machine_id, {})
            duration_s = profile.get("average_duration_s_10")
            energy_wh = profile.get("average_energy_wh_10")
            cycle = cycles.get(machine.machine_id, {})
            recommendations[machine.machine_id] = recommend_flexible_load(
                now=now,
                snapshot=snap,
                prices=tariff,
                settings=self.settings,
                import_points=import_points,
                duration_hours=(float(duration_s) / 3600.0) if isinstance(duration_s, (int, float)) and duration_s > 0 else None,
                energy_kwh=(float(energy_wh) / 1000.0) if isinstance(energy_wh, (int, float)) and energy_wh > 0 else None,
                active=bool(cycle.get("protected", False)),
                market_decision=decision,
            )
            recommendations[machine.machine_id]["name"] = machine.name
            recommendations[machine.machine_id]["profile_cycles"] = int(profile.get("total_cycles", 0) or 0)

        tomorrow_entity = self.config.get(CONF_PRICE_TOMORROW_AVAILABLE)
        tomorrow_available = self._is_on(tomorrow_entity) if tomorrow_entity else any(
            point.at.date() > now.date() for point in import_points
        )
        scheduler_active = bool(
            tariff_dimensions(self.settings).dynamic
            and str(self.settings.get("mode")) != MODE_MANUAL
            and bool(self.settings.get("economic_optimizer_enabled", True))
            and bool(self.settings.get("predictive_pricing_enabled", True))
        )
        day_ahead = build_dynamic_schedule(
            now=now,
            snapshot=snap,
            settings=self.settings,
            mode_dynamic_active=scheduler_active,
            import_points=import_points,
            export_points=export_points,
            machines=self.machines,
            learning=learning,
            cycles=cycles,
            market_decision=decision,
            solar_forecast=self.solar_forecast,
            tomorrow_available=tomorrow_available,
        )
        # En mode Dynamique uniquement, le planner devient la source de vérité
        # pour l'autorisation de NOUVEAU départ. Les métriques économiques déjà
        # calculées restent exposées et sont enrichies, jamais supprimées.
        if day_ahead.get("active"):
            for machine_id, plan in (day_ahead.get("machines") or {}).items():
                rec = recommendations.setdefault(machine_id, {})
                rec["allow_start"] = bool(plan.get("allow_start_now", False))
                rec["scheduler_decision"] = plan.get("decision")
                rec["scheduler_reason"] = plan.get("reason")
                rec["best_user_window_start"] = plan.get("best_start")
                rec["best_user_window_end"] = plan.get("best_end")
                rec["user_window_now"] = plan.get("user_window_now")
                rec["day_ahead_threshold_pct"] = day_ahead.get("threshold_pct")

        price_analysis = analyze_price_curve(now=now, import_points=import_points, export_points=export_points, settings=self.settings, tomorrow_available=tomorrow_available, current_buy=tariff.get("active_buy")) if tariff_dimensions(self.settings).dynamic else {"active":False,"mode":"INACTIF","state":"HORS_DYNAMIQUE","valid":True,"series":[]}
        planner = build_flexible_load_plan(now=now,snapshot=snap,settings=self.settings,import_points=import_points,export_points=export_points,machines=self.machines,learning=learning,cycles=cycles,price_analysis=price_analysis,solar_forecast=self.solar_forecast,boiler_thermal=boiler_thermal,boiler_user_override=str(self.core_state.get("boiler_user_override","AUTO")))
        for mid,plan in (planner.get("machines") or {}).items():
            recommendations.setdefault(mid,{})["allow_start"]=bool(plan.get("allow_start_now")); recommendations[mid]["scheduler_decision"]=plan.get("decision"); recommendations[mid]["scheduler_reason"]=plan.get("reason")
        best_export = max(export_points, key=lambda p: p.price) if export_points else None
        worst_export = min(export_points, key=lambda p: p.price) if export_points else None
        return {
            "decision": decision,
            "boiler_thermal": boiler_thermal,
            "machines": recommendations,
            "day_ahead": day_ahead,
            "price_analyzer": price_analysis,
            "planner": planner,
            "forecast": {
                "import_points": len(import_points),
                "export_points": len(export_points),
                "best_export_value_eur_kwh": best_export.price if best_export else None,
                "best_export_at": best_export.at.isoformat() if best_export else None,
                "worst_export_value_eur_kwh": worst_export.price if worst_export else None,
                "worst_export_at": worst_export.at.isoformat() if worst_export else None,
                "horizon_hours": int(float(self.settings.get("economic_horizon_hours", 24.0))),
                "source_import": self.config.get(CONF_PRICE_FORECAST_IMPORT) or ("HP/HC calculé" if str(tariff.get("regime")) == TARIFF_TOU else self.config.get(CONF_PRICE_CURRENT)),
                "source_export": self.config.get(CONF_PRICE_FORECAST_EXPORT) or ("Prix fixe" if str(tariff.get("regime")) == TARIFF_TOU else self.config.get(CONF_PRICE_INJECTION)),
            },
        }


    def _apply_dynamic_boiler_arbitrage(
        self, snapshot: EnergySnapshot, intent: BoilerIntent, economic_view: dict[str, Any]
    ) -> BoilerIntent:
        """Applique l'arbitrage Day-Ahead au Boiler, uniquement en mode DYNAMIQUE.

        Les sécurités CORE et les overrides utilisateur sont traités avant cet
        appel. Lorsque le kill-switch prédictif est coupé ou que le moteur est en
        repli standard, l'intention historique est restituée sans modification.
        """
        if str(self.settings.get("mode")) != MODE_DYNAMIC:
            return intent
        if str(self.settings.get("tariff_regime")) != TARIFF_DYNAMIC:
            return intent
        if not bool(self.settings.get("predictive_pricing_enabled", True)):
            return intent
        decision = dict(economic_view.get("decision", {}) or {})
        if bool(decision.get("dynamic_fallback")) or not decision.get("dynamic_price_band"):
            return intent
        if intent.origin in {"SECURITE", "UTILISATEUR"}:
            return intent

        normal = float(self.settings.get("boiler_temp_normal_c", 45.0))
        minimum = float(self.settings.get("boiler_temp_start_c", 43.0))
        element_w = float((economic_view.get("boiler_thermal") or {}).get("element_power_w") or self.settings.get("boiler_power_w", 1800.0))
        band = str(decision.get("dynamic_price_band"))
        index = decision.get("dynamic_price_index")
        position_pct = decision.get("dynamic_curve_position_pct")
        favorable_threshold_pct = max(5.0, min(60.0, float(self.settings.get("dynamic_favorable_position_pct", 30.0))))
        favorable_now = bool(isinstance(position_pct, (int, float)) and float(position_pct) <= favorable_threshold_pct)
        current_buy = decision.get("current_buy_eur_kwh")
        negative_threshold = float(self.settings.get("dynamic_grid_charge_threshold_eur_kwh", 0.0))
        negative_enabled = bool(self.settings.get("dynamic_negative_price_charge_enabled", True))
        negative_price = isinstance(current_buy, (int, float)) and float(current_buy) < negative_threshold

        # V1.6.158 — coût marginal Boiler : la part solaire consommée localement
        # vaut son coût d'opportunité de réinjection, la part réseau vaut le prix
        # d'achat. On compare ce mélange au créneau Boiler futur réservé.
        export_value = decision.get("export_value_eur_kwh")
        reserved_avg = decision.get("boiler_reserved_avg_price_eur_kwh")
        export_value = float(export_value) if isinstance(export_value, (int, float)) else 0.0
        current_buy_f = float(current_buy) if isinstance(current_buy, (int, float)) else None
        solar_fraction = min(max(float(snapshot.export_w), 0.0), max(element_w, 1.0)) / max(element_w, 1.0)
        effective_boiler_cost = None
        if current_buy_f is not None:
            effective_boiler_cost = solar_fraction * export_value + (1.0 - solar_fraction) * current_buy_f
        future_reference = float(reserved_avg) if isinstance(reserved_avg, (int, float)) else None
        marginal_margin = float(self.settings.get("economic_min_saving_eur_kwh", 0.02))
        solar_mix_favorable = bool(
            solar_fraction > 0.0
            and effective_boiler_cost is not None
            and (future_reference is None or effective_boiler_cost <= future_reference + marginal_margin)
        )

        # Confort ECS minimum : priorité absolue, même en haut de courbe.
        if snapshot.boiler_temp_c < minimum:
            return BoilerIntent(
                BOILER_HEAT_45,
                f"Dynamique Day-Ahead : confort ECS prioritaire ({snapshot.boiler_temp_c:.1f} °C < {minimum:.1f} °C), indice={index}.",
                "DYNAMIC_ECS_PRIORITE",
            )

        # Compatibilité V1.6.156 : le réglage historique « charge réseau si
        # prix dynamique négatif » reste souverain dans le régime dynamique.
        # S'il est autorisé, on conserve l'intention historique (y compris le
        # stockage 65 °C). S'il est interdit, un prix négatif ne peut pas, à lui
        # seul, provoquer une charge réseau via la nouvelle réservation Day-Ahead.
        if negative_price and negative_enabled and intent.origin == "PRIX_NEGATIF_RESEAU":
            return intent

        if negative_price and not negative_enabled:
            if snapshot.export_w >= max(element_w, 1.0):
                return BoilerIntent(
                    BOILER_HEAT_45,
                    f"Prix dynamique sous le seuil mais charge réseau négative désactivée : surplus local {snapshot.export_w:.0f} W suffisant pour la résistance {element_w:.0f} W.",
                    "DYNAMIC_SURPLUS_STRICT",
                )
            return BoilerIntent(
                BOILER_STOP if snapshot.boiler_on else BOILER_NONE,
                "Prix dynamique sous le seuil mais charge réseau négative désactivée : attente sans prélèvement réseau.",
                "DYNAMIC_NEGATIVE_DISABLED",
            )

        boost_target = float(self.settings.get("boiler_temp_boost_c", 65.0))
        self_consumption_advantage = decision.get("self_consumption_advantage_eur_kwh")
        solar_boost = bool(
            snapshot.export_w >= max(element_w, 1.0)
            and (
                not isinstance(self_consumption_advantage, (int, float))
                or float(self_consumption_advantage) >= -float(self.settings.get("economic_export_margin_eur_kwh", 0.01))
            )
        )
        # V1.6.159 : stockage thermique uniquement en mode Dynamique. Un gros
        # surplus solaire ou une position sous le seuil utilisateur peut charger
        # jusqu'à la consigne BOOST, sans jamais contourner la sécurité 68 °C.
        if snapshot.boiler_temp_c < boost_target and solar_boost:
            return BoilerIntent(
                BOILER_BOOST_65,
                f"Dynamique : boost autoconsommation, surplus {snapshot.export_w:.0f} W couvre la résistance {element_w:.0f} W.",
                "DYNAMIC_BOOST_SOLAIRE",
            )
        if snapshot.boiler_temp_c < boost_target and favorable_now:
            return BoilerIntent(
                BOILER_BOOST_65,
                f"Dynamique : boost Day-Ahead, position {float(position_pct):.1f} % <= seuil {favorable_threshold_pct:.1f} %.",
                "DYNAMIC_BOOST_PRIX",
            )

        if snapshot.boiler_temp_c >= normal:
            return BoilerIntent(
                BOILER_STOP if snapshot.boiler_on else BOILER_NONE,
                "Dynamique Day-Ahead : température de confort atteinte hors fenêtre de boost.",
                "DYNAMIC_DAY_AHEAD",
            )

        if bool(decision.get("boiler_charge_now")):
            return BoilerIntent(
                BOILER_HEAT_45,
                f"Dynamique Day-Ahead : créneau Boiler réservé actif (indice={index}, plage={band}).",
                "DYNAMIC_RESERVATION",
            )

        if band == "MEDIAN":
            if snapshot.export_w >= max(element_w, 1.0):
                return BoilerIntent(
                    BOILER_HEAT_45,
                    f"Dynamique médiane : surplus local {snapshot.export_w:.0f} W couvre la résistance {element_w:.0f} W.",
                    "DYNAMIC_SURPLUS_STRICT",
                )
            if solar_mix_favorable:
                return BoilerIntent(
                    BOILER_HEAT_45,
                    f"Dynamique médiane : mélange solaire/réseau financièrement pertinent ({effective_boiler_cost:.3f} €/kWh effectif, référence future {future_reference if future_reference is not None else float('nan'):.3f} €/kWh).",
                    "DYNAMIC_COUT_MARGINAL",
                )
            return BoilerIntent(
                BOILER_STOP if snapshot.boiler_on else BOILER_NONE,
                "Dynamique médiane : coût marginal actuel moins favorable que le créneau futur, attente.",
                "DYNAMIC_COUT_MARGINAL",
            )

        if band == "HAUT":
            if solar_mix_favorable:
                return BoilerIntent(
                    BOILER_HEAT_45,
                    f"Dynamique haut de courbe : le solaire réduit suffisamment le coût marginal ({effective_boiler_cost:.3f} €/kWh) pour chauffer sans attendre.",
                    "DYNAMIC_COUT_MARGINAL",
                )
            return BoilerIntent(
                BOILER_STOP if snapshot.boiler_on else BOILER_NONE,
                f"Dynamique Day-Ahead : haut de courbe (indice={index}), charge réseau Boiler reportée hors confort minimum.",
                "DYNAMIC_PRIX_HAUT",
            )

        # Bas de courbe mais hors bloc réservé : le solaire peut rendre le coût
        # marginal meilleur que le bloc théorique futur.
        if band == "BAS":
            if solar_mix_favorable:
                return BoilerIntent(
                    BOILER_HEAT_45,
                    f"Dynamique bas de courbe : coût marginal solaire/réseau {effective_boiler_cost:.3f} €/kWh favorable, chauffe avancée.",
                    "DYNAMIC_COUT_MARGINAL",
                )
            return BoilerIntent(
                BOILER_STOP if snapshot.boiler_on else BOILER_NONE,
                "Dynamique Day-Ahead : bas de courbe mais hors créneau optimal, attente du meilleur coût marginal.",
                "DYNAMIC_RESERVATION",
            )
        return intent

    def _set_core_phase(self, phase: str, reason: str = "") -> None:
        valid = {PHASE_ACQUISITION, PHASE_DECISION, PHASE_WAIT_ACK}
        previous = str(self.core_state.get("phase", PHASE_ACQUISITION))
        if phase not in valid:
            self.core_state["fsm_status"] = "ERREUR_PHASE"
            phase = PHASE_ACQUISITION
        if previous != phase:
            self.core_state["fsm_transition_count"] = int(self.core_state.get("fsm_transition_count", 0)) + 1
            self.core_state["fsm_last_transition_at"] = dt_util.now()
            self.core_state["fsm_last_transition"] = f"{previous} -> {phase}"
        self.core_state["phase"] = phase
        self.core_state["fsm_status"] = "OK"
        if reason:
            self.core_state["last_reason"] = reason

    def reset_core(self, reason: str) -> None:
        self._set_core_phase(PHASE_ACQUISITION, reason)
        self.core_state.update(
            {
                "ack": ACK_IDLE,
                "pending_action": "NONE",
                "pending_delta": 0.0,
                "ack_error": 0.0,
            }
        )

    async def async_set_setting(self, key: str, value: Any) -> None:
        if key == "mode":
            await self.async_set_mode(str(value))
            return

        if key == "regulation_active" and bool(value) and not bool(
            self.settings.get("device_meter_enabled", True)
        ):
            value = False
            self.core_state["last_reason"] = (
                "Activation refusée : le compteur réseau est désactivé."
            )
        if key == "pri_enabled" and bool(value) and not bool(
            self.settings.get("device_inverter_enabled", True)
        ):
            value = False

        if key == "tariff_regime":
            if value == TARIFF_DYNAMIC:
                self.settings["price_source"] = PRICE_SOURCE_DYNAMIC
            elif value in {TARIFF_TOU, TARIFF_SIMPLE}:
                if tariff_dimensions(self.settings).dynamic:
                    self.settings["price_source"] = PRICE_SOURCE_VARIABLE
                self.settings["tariff_structure"] = (
                    TARIFF_STRUCTURE_TOU if value == TARIFF_TOU else TARIFF_STRUCTURE_SIMPLE
                )

        self.settings[key] = value

        if key == "regulation_active":
            if value:
                self.reset_core("Régulation FoxCat activée : acquisition requise.")
                await self.async_release_pri_100("Activation de la régulation : point de départ sûr à 100 %.")
                if str(self.settings.get("mode")) != MODE_MANUAL:
                    await self.async_reconcile_machines()
            else:
                self.reset_core("Régulation FoxCat désactivée.")
                if self._pri_task and not self._pri_task.done():
                    self._pri_task.cancel()
                await self.async_release_pri_100("Régulation désactivée : onduleur libéré à 100 %.")

        if key == "high_load_shed_enabled" and not value:
            self._high_load_since = None
            self._high_load_below_since = None
            if self.load_shed_state.get("active"):
                self.load_shed_state.update({"active": False, "reason": "Délestage désactivé", "triggered_at": None})
                if str(self.settings.get("mode")) != MODE_MANUAL:
                    await self.async_reconcile_machines()

        if key == "pri_enabled" and not value:
            if self._pri_task and not self._pri_task.done():
                self._pri_task.cancel()
            await self.async_release_pri_100("PRI désactivé par l'utilisateur.")

        if key in {"washer_enabled", "dryer_enabled", "dishwasher_enabled"}:
            await self.async_reconcile_machines()

        if key == "tariff_regime":
            self.reset_core(f"Régime tarifaire modifié vers {value} : nouvelle acquisition demandée.")
            if str(self.settings.get("mode")) == MODE_DYNAMIC:
                if str(value) == TARIFF_DYNAMIC:
                    self.settings["pri_enabled"] = True
                else:
                    self.settings["pri_enabled"] = False
                    if self._pri_task and not self._pri_task.done():
                        self._pri_task.cancel()
                    if bool(self.settings.get("regulation_active")):
                        await self.async_release_pri_100("Prix dynamique incompatible avec le régime tarifaire : onduleur libéré à 100 %.")
                        if self.snapshot().boiler_on:
                            await self.async_command_boiler(
                                BOILER_STOP,
                                "Régime tarifaire quitté : arrêt de la charge financière dynamique en cours.",
                                "PRIX_BLOQUE",
                            )

        if key in {"predictive_pricing_enabled", "solar_forecast_arbitrage", "dynamic_favorable_position_pct", "dynamic_high_position_pct"}:
            # Réglages Day-Ahead dédiés au mode Dynamique : aucun effet sur HP/HC.
            if (
                str(self.settings.get("mode")) == MODE_DYNAMIC
                and str(self.settings.get("tariff_regime")) == TARIFF_DYNAMIC
            ):
                self.reset_core(f"Option dynamique {key}={bool(value)} : nouvelle acquisition demandée.")
                if str(self.settings.get("mode")) != MODE_MANUAL:
                    await self.async_reconcile_machines()

        if key == "persistent_status_notification_enabled" and not bool(value):
            persistent_notification.async_dismiss(
                self.hass, f"foxcat_energy_status_{self.entry.entry_id}"
            )
            self._status_notification_last_signature = None

        await self._async_save()

        # HP/HC prices are configuration-backed since V1.2.2.  Keep the
        # editable number entities for backwards compatibility, but mirror any
        # change they make into ConfigEntry options so the dedicated tariff
        # page and the entities always survive restarts with the same value.
        if key in {*TIME_SETTING_KEYS, CONF_TARIFF_FIXED_INJECTION_PRICE}:
            options = dict(self.entry.options)
            if options.get(key) != value:
                options[key] = value
                self.config[key] = value
                self.hass.config_entries.async_update_entry(self.entry, options=options)

        self.async_set_updated_data(self._build_data())

    async def async_apply_settings_profile(self, values: dict[str, Any]) -> None:
        was_regulating = bool(self.settings.get("regulation_active"))
        was_pri_enabled = bool(self.settings.get("pri_enabled"))
        was_boiler_on = self.snapshot().boiler_on
        self.settings.update(values)
        if not bool(self.settings.get("device_meter_enabled", True)):
            self.settings["regulation_active"] = False
        if not bool(self.settings.get("device_inverter_enabled", True)):
            self.settings["pri_enabled"] = False

        regulation_active = bool(self.settings.get("regulation_active"))
        pri_enabled = bool(self.settings.get("pri_enabled"))
        boiler_enabled = bool(self.settings.get("boiler_enabled")) and bool(
            self.settings.get("device_boiler_enabled", True)
        )

        self.reset_core("Profil de réglages appliqué : acquisition de sécurité requise.")
        if (was_regulating and not regulation_active) or (was_pri_enabled and not pri_enabled):
            if self._pri_task and not self._pri_task.done():
                self._pri_task.cancel()
            await self.async_release_pri_100("Profil appliqué : onduleur libéré à 100 %.")
        elif not was_regulating and regulation_active:
            await self.async_release_pri_100("Profil appliqué : démarrage depuis un point sûr à 100 %.")

        if was_boiler_on and not boiler_enabled:
            await self.async_command_boiler(
                BOILER_STOP,
                "Profil appliqué : fonction Boiler désactivée.",
                "UTILISATEUR",
            )
        if str(self.settings.get("mode")) != MODE_MANUAL:
            await self.async_reconcile_machines()
        await self._async_save()
        self.async_set_updated_data(self._build_data())

    async def async_set_mode(self, mode: str) -> None:
        canonical=MODE_ALIASES.get(mode,mode)
        if canonical not in MODES: canonical=MODE_ECO
        self.settings["mode"]=canonical
        self.reset_core(f"Comportement EMS modifié vers {canonical}.")
        if canonical==MODE_MANUAL: self.core_state["last_reason"]="Manuel : actions économiques automatiques suspendues ; mesures, comptabilité et sécurités conservées."
        else:
            self.core_state["last_reason"]=f"Comportement {canonical} actif."
            if self.settings.get("regulation_active"): await self.async_reconcile_machines()
        await self._async_save(); self.async_set_updated_data(self._build_data())

    async def async_set_pri_manual_level(self, level: int) -> None:
        """Force un niveau RRCR uniquement lorsque le mode Manuel est actif."""
        if str(self.settings.get("mode")) != MODE_MANUAL:
            self.core_state["last_reason"] = "Commande PRI manuelle refusée : le mode EMS n'est pas Manuel."
            self.async_set_updated_data(self._build_data())
            return
        level = int(level)
        if level not in RRCR_LEVEL_TO_CODE:
            self.core_state["last_reason"] = f"Commande PRI manuelle invalide : {level} %."
            self.async_set_updated_data(self._build_data())
            return
        ok = await self._apply_rrcr_level(level)
        expected = RRCR_LEVEL_TO_CODE[level]
        confirmed = ok and await self._wait_rrcr_code(expected, timeout=5.0)
        code = self._rrcr_code()
        if confirmed and code == expected:
            self.pri_state.update({
                "current_level": level,
                "target_level": level,
                "code": code,
                "direction": "manuel",
                "ack_rrcr": "OK",
                "last_reason": f"Mode Manuel : niveau PRI forcé à {level} %.",
            })
            self.core_state["last_reason"] = f"Mode Manuel : onduleur PRI réglé à {level} %."
        else:
            self.pri_state["ack_rrcr"] = "FAILED"
            self.pri_state["last_reason"] = f"Échec commande manuelle PRI {level} % : code lu {code}, attendu {expected}."
        self.async_set_updated_data(self._build_data())

    async def async_handle_inverter_grid_frame(
        self,
        source_entity: str = "",
        *,
        snapshot: EnergySnapshot | None = None,
        frame_id: int | None = None,
        frame_serial: int | None = None,
        frame_at: datetime | None = None,
    ) -> None:
        """Onduleur Core : une décision immédiate pour chaque publication réseau.

        La décision ne contient plus d'attente de commande physique : le moteur
        RRCR possède son propre worker et converge vers la dernière consigne.
        Ainsi aucune trame réseau ne reste derrière une commutation de relais.
        """
        if snapshot is None:
            snapshot = self.snapshot()
        now = frame_at or dt_util.now()
        if frame_id is None or frame_serial is None:
            # Voie legacy sans métronome : crée une trame autonome.
            async with self._frame_dispatch_lock:
                self._frame_id += 1
                self._frame_serial += 1
                frame_id = self._frame_id
                frame_serial = self._frame_serial
                self.energy_bus.on_grid_frame(
                    frame_id, now, source=source_entity or "legacy", frame_serial=frame_serial,
                    grid_net_w=snapshot.grid_net_w, pv_w=snapshot.pv_w, house_w=snapshot.house_w,
                    import_w=snapshot.import_w, export_w=snapshot.export_w, valid=snapshot.valid,
                    boiler_power_w=snapshot.boiler_power_w, boiler_temp_c=snapshot.boiler_temp_c,
                    boiler_on=snapshot.boiler_on, machine_active=snapshot.machine_active,
                    mode=str(self.settings.get("mode")),
                    network_policy=str(self.settings.get("network_policy")),
                )

        async with self._inverter_reduction_lock:
            # Le numéro de série courant suit la trame réellement traitée pour ACK N+1.
            self.pri_state["last_30s_tick"] = now
            self.pri_state["frame_id"] = int(frame_id)
            self.pri_state["decision_tick_count"] = int(self.pri_state.get("decision_tick_count", 0)) + 1
            self.pri_state["frame_source"] = source_entity or "réseau"
            self.pri_state["last_grid_frame_at"] = now
            self.pri_state["last_frame_received_at"] = dt_util.now()
            self.pri_state["processed_frame_count"] = int(self.pri_state.get("processed_frame_count", 0)) + 1

            pending_bus_ids: list[int] = []
            while (pending_bus := self.energy_bus.pending_for("ONDULEUR")) is not None:
                pending_bus_ids.append(pending_bus.message_id)
                self.energy_bus.acknowledge_pending(
                    target="ONDULEUR", now=dt_util.now(), processed=False,
                    reason=f"Message reçu sur trame {frame_id}.",
                )

            if not snapshot.valid:
                self.pri_state["guard_reason"] = "snapshot_invalide"
                self.pri_state["last_reason"] = "Onduleur Core : trame reçue, snapshot énergétique invalide."
                for pending_bus_id in pending_bus_ids:
                    self.energy_bus.mark_nok(
                        pending_bus_id, by="ONDULEUR", now=dt_util.now(),
                        reason="Snapshot énergétique invalide.", busy=True,
                    )
                self.energy_bus.publish_inverter_state(
                    status="SNAPSHOT_INVALIDE", frame_id=frame_id, frame_at=now
                )
                self.energy_bus.mark_frame_core(
                    frame_id, "ONDULEUR", "NOK", now=dt_util.now(),
                    reason=self.pri_state["last_reason"],
                )
                self.async_set_updated_data(self._build_data(snapshot))
                return

            # Validation N+1 puis nouvelle décision, toujours sur le snapshot de CETTE trame.
            await self._validate_pending_pri_on_frame(snapshot, frame_serial=int(frame_serial))
            pri_result = await self._run_pri_frame(
                snapshot, frame_id=int(frame_id), frame_serial=int(frame_serial)
            )

            for pending_bus_id in pending_bus_ids:
                if pri_result == "PROCESSED":
                    self.energy_bus.mark_processed(
                        pending_bus_id, by="ONDULEUR", now=dt_util.now(),
                        reason=f"Message traité sur trame {frame_id}; décision PRI calculée.",
                    )
                else:
                    self.energy_bus.mark_nok(
                        pending_bus_id, by="ONDULEUR", now=dt_util.now(),
                        reason=f"Message reçu mais non traitable : {pri_result}.", busy=True,
                    )

            # Le corps Onduleur annonce sa décision au corps EMS via Energy Bus.
            self.energy_bus.publish_message(
                source="ONDULEUR", target="EMS", action=f"PRI_{pri_result}", delta_w=0.0,
                now=dt_util.now(), frame_id=int(frame_id),
                current_level=self.pri_state.get("current_level"),
                target_level=self.pri_state.get("target_level"),
                direction=self.pri_state.get("direction"),
                reason=self.pri_state.get("last_reason", ""),
            )
            self.energy_bus.mark_frame_core(
                int(frame_id), "ONDULEUR", pri_result, now=dt_util.now(),
                reason=str(self.pri_state.get("last_reason", "")),
            )
            self.pri_state["last_decision_at"] = dt_util.now()
            self.async_set_updated_data(self._build_data(snapshot))


    async def async_handle_house_frame(
        self,
        *,
        snapshot: EnergySnapshot | None = None,
        frame_id: int | None = None,
        frame_serial: int | None = None,
        frame_at: datetime | None = None,
        source_entity: str = "",
    ) -> None:
        """EMS Core : traite la même trame/snapshot que le corps Onduleur.

        Les resets périodiques Smappee peuvent rendre brièvement les capteurs
        unknown/unavailable. Ces événements ne sont pas des trames EMS :
        - aucun frame_id n'est consommé ;
        - aucun ACK PRI N+1 n'est validé/échoué ;
        - l'intégrale PI est conservée ;
        - le niveau PRI est conservé ;
        - l'état du délestage est conservé ;
        - les cycles protégés et le boiler ne sont pas modifiés par optimisation.
        Après le retour des mesures, une trame complète de stabilisation est
        exigée avant de reprendre les décisions énergétiques.
        """
        async with self._core_lock:
            if snapshot is None:
                snapshot = self.snapshot()
            now = frame_at or dt_util.now()
            effective_frame_id = int(frame_id or self._frame_id)
            self.core_state["last_frame_id"] = effective_frame_id
            self.core_state["last_frame_received_at"] = dt_util.now()
            self.core_state["processed_frame_count"] = int(self.core_state.get("processed_frame_count", 0)) + 1

            pending_bus_ids: list[int] = []
            while (pending_bus := self.energy_bus.pending_for("EMS")) is not None:
                pending_bus_ids.append(pending_bus.message_id)
                self.energy_bus.acknowledge_pending(
                    target="EMS", now=dt_util.now(), processed=False,
                    reason=f"Message reçu sur trame {effective_frame_id}.",
                )

            if not snapshot.valid:
                self._sensor_reset_active = True
                self._valid_frames_after_reset = 0
                self.core_state["last_reason"] = (
                    "Reset/indisponibilité capteurs : décisions EMS gelées, "
                    "PRI/ACK/délestage conservés."
                )
                self.pri_state["last_reason"] = (
                    "Mesures transitoirement invalides : PRI conservé, "
                    "état PRI conservé, attente d'une trame complète."
                )
                for pending_bus_id in pending_bus_ids:
                    self.energy_bus.mark_nok(
                        pending_bus_id, by="EMS", now=dt_util.now(),
                        reason="Snapshot énergétique invalide.", busy=True,
                    )
                self.energy_bus.mark_frame_core(
                    effective_frame_id, "EMS", "NOK", now=dt_util.now(),
                    reason=self.core_state["last_reason"],
                )
                self.async_set_updated_data(self._build_data(snapshot))
                return

            if self._sensor_reset_active:
                self._valid_frames_after_reset += 1
                if self._valid_frames_after_reset < 2:
                    # Première trame valide après reset = stabilisation seulement.
                    self.core_state["last_reason"] = (
                        "Capteurs revenus : première trame valide de stabilisation, "
                        "aucune décision énergétique."
                    )
                    self.pri_state["last_reason"] = (
                        "Reprise capteurs : stabilisation N0, PRI inchangé."
                    )
                    for pending_bus_id in pending_bus_ids:
                        self.energy_bus.mark_processed(
                            pending_bus_id, by="EMS", now=dt_util.now(),
                            reason=f"Trame {effective_frame_id} utilisée comme stabilisation.",
                        )
                    self.energy_bus.publish_message(
                        source="EMS", target="ONDULEUR", action="CORE_STABILISATION", delta_w=0.0,
                        now=dt_util.now(), frame_id=effective_frame_id,
                        reason=self.core_state["last_reason"],
                    )
                    self.energy_bus.mark_frame_core(
                        effective_frame_id, "EMS", "STABILISATION", now=dt_util.now(),
                        reason=self.core_state["last_reason"],
                    )
                    self.async_set_updated_data(self._build_data(snapshot))
                    return
                self._sensor_reset_active = False
                self._valid_frames_after_reset = 0
                self.reset_core("Capteurs stabilisés après reset : reprise du CORE.")

            # Le frame_id de réduction onduleur est géré par sa boucle dédiée.
            self.core_state["last_frame"] = snapshot.timestamp

            # Comptabilité énergétique : observe la trame, sans influencer le CORE.
            accounting_appliances = self.machine_states()
            accounting_appliances.append({
                "id": "boiler",
                "name": "Chauffe-eau",
                "power_w": snapshot.boiler_power_w,
            })
            if self.accounting.process(snapshot, self.prices(), accounting_appliances):
                self.hass.async_create_task(self._async_save())

            if bool(self.settings.get("regulation_active")):
                # CORE EMS uniquement. Le corps Onduleur traite le même snapshot
                # dans une task indépendante déclenchée par la même publication.
                await self._evaluate_high_load(snapshot)
                await self._core_process_frame(snapshot)
            else:
                self.core_state["last_reason"] = "Régulation inactive : télémétrie seulement."
                self.pri_state["guard_reason"] = "regulation_inactive"

            # Le corps EMS accuse le message reçu puis publie sa propre décision.
            for pending_bus_id in pending_bus_ids:
                self.energy_bus.mark_processed(
                    pending_bus_id, by="EMS", now=dt_util.now(),
                    reason=f"Décision EMS traitée sur trame {effective_frame_id}.",
                )
            decision_id = self.energy_bus.publish_message(
                source="EMS", target="ONDULEUR", action="CORE_DECISION", delta_w=0.0,
                now=dt_util.now(), frame_id=effective_frame_id,
                phase=self.core_state.get("phase"),
                pending_action=self.core_state.get("pending_action"),
                ack=self.core_state.get("ack"),
                reason=self.core_state.get("last_reason", ""),
            )
            self.core_state["last_bus_decision_id"] = decision_id
            self.energy_bus.mark_frame_core(
                effective_frame_id, "EMS", "PROCESSED", now=dt_util.now(),
                reason=str(self.core_state.get("last_reason", "")),
            )
            self.async_set_updated_data(self._build_data(snapshot))

    async def async_handle_grid_change(self) -> None:
        """Télémétrie secondaire; la publication réseau souveraine déclenche les deux corps."""
        self.async_set_updated_data(self._build_data())

    async def _core_process_frame(self, snapshot: EnergySnapshot) -> None:
        if not snapshot.valid:
            self.reset_core("Mesures énergétiques invalides : aucune décision autorisée.")
            return

        # Le délestage haute consommation est prioritaire sur les stratégies
        # énergétiques normales, mais reste inactif en mode Manuel.
        if self.load_shed_state.get("active") and str(self.settings.get("mode")) != MODE_MANUAL:
            if snapshot.boiler_on:
                await self.async_command_boiler(
                    BOILER_STOP,
                    "Délestage haute consommation : arrêt temporaire du chauffe-eau.",
                    "DELESTAGE",
                )
            else:
                self.reset_core("Délestage haute consommation actif : charges variables suspendues.")
            return

        # Immediate thermal safety remains active in every mode.
        if snapshot.boiler_on and snapshot.boiler_safety_temp_c >= float(self.settings["boiler_temp_safety_c"]):
            await self.async_command_boiler(BOILER_STOP, "SÉCURITÉ CORE : température boiler maximale atteinte.", "SECURITE")
            return

        # Un cycle machine protégé conserve la priorité, mais il ne condamne
        # plus le boiler par principe. Le boiler peut continuer si le surplus
        # réellement disponible après la machine couvre sa puissance.
        if (
            str(self.settings.get("mode")) != MODE_MANUAL
            and snapshot.boiler_on
            and snapshot.machine_active
            and not protected_cycle_boiler_allowed(snapshot, self.settings)
        ):
            await self.async_command_boiler(
                BOILER_STOP,
                "Cycle machine protégé : surplus solaire insuffisant pour alimenter simultanément le boiler.",
                "MACHINE",
            )
            return

        phase = self.core_state["phase"]
        if phase == PHASE_ACQUISITION:
            self.core_state["t0"] = snapshot
            self._set_core_phase(PHASE_DECISION)
            self.core_state["ack"] = ACK_IDLE
            self.core_state["last_reason"] = (
                f"ACQUISITION : réseau={snapshot.grid_net_w:.0f} W "
                f"[export={snapshot.export_w:.0f} / import={snapshot.import_w:.0f}], "
                f"PV={snapshot.pv_w:.0f} W, maison={snapshot.house_w:.0f} W."
            )
            return

        if phase == PHASE_WAIT_ACK:
            if str(self.core_state.get("execution_status")) in {"QUEUED", "EXECUTION"}:
                self.core_state["last_reason"] = (
                    "WAIT_ACK : commande physique en cours hors trame; nouvelle trame enregistrée sans blocage."
                )
                return
            self._validate_core_ack(snapshot)
            self.core_state["t0"] = snapshot
            self._set_core_phase(PHASE_ACQUISITION)
            self.core_state["pending_action"] = "NONE"
            self.core_state["pending_delta"] = 0.0
            return

        if phase != PHASE_DECISION:
            self.reset_core("Phase CORE inconnue : retour ACQUISITION.")
            return

        t0: EnergySnapshot | None = self.core_state.get("t0")
        if not isinstance(t0, EnergySnapshot):
            self.reset_core("T0 absent : nouvelle acquisition requise.")
            return

        if abs(snapshot.grid_net_w - t0.grid_net_w) > float(self.settings["stability_tolerance_w"]):
            self.reset_core(
                f"Décision suspendue : variation réseau {abs(snapshot.grid_net_w - t0.grid_net_w):.0f} W > tolérance."
            )
            return

        mode = str(self.settings.get("mode"))
        user_override = str(self.core_state.get("boiler_user_override", "AUTO"))
        if user_override == "FORCE_ON":
            if snapshot.boiler_safety_temp_c >= float(self.settings["boiler_temp_safety_c"]):
                intent = BoilerIntent(BOILER_STOP, "Utilisateur : démarrage Boiler bloqué par sécurité température.", "UTILISATEUR")
            else:
                intent = BoilerIntent(BOILER_HEAT_45, "Utilisateur : démarrage Boiler forcé.", "UTILISATEUR")
        elif user_override == "FORCE_OFF":
            intent = BoilerIntent(BOILER_STOP, "Utilisateur : arrêt Boiler forcé.", "UTILISATEUR")
        else:
            if mode == MODE_MANUAL:
                self.reset_core("Mode Manuel : stratégies automatiques en sommeil, sécurités actives.")
                return
            tariff_context = self.prices()
            solar_for_mode = self.solar_forecast
            if (
                tariff_dimensions(self.settings).dynamic
                and not bool(self.settings.get("solar_forecast_arbitrage", True))
            ):
                # Le kill-switch neutralise uniquement l'influence de la prévision
                # solaire sur l'arbitrage DYNAMIQUE; la télémétrie IA reste intacte.
                solar_for_mode = SolarForecast()
            intent = evaluate_mode(
                mode,
                snapshot,
                t0,
                self.settings,
                dt_util.now(),
                self._boiler_on_seconds(),
                str(self.core_state.get("boiler_demand", BOILER_NONE)),
                tariff_context,
                solar_for_mode,
            )
            if (
                mode != MODE_MANUAL
                and tariff_dimensions(self.settings).dynamic
            ):
                # V1.6.160 : branche Boiler dédiée au Dynamique. L'ancienne
                # stratégie ne dépend plus du comportement EMS : le Planner et
                # le prix Day-Ahead déterminent l'arbitrage, jamais le mode Manuel.
                intent = evaluate_dynamic_boiler_v2(
                    snapshot, intent, self.settings, self._economic_view(snapshot, prices=tariff_context)
                )

        if (
            intent.origin != "UTILISATEUR"
            and intent.action in {BOILER_HEAT_45, BOILER_BOOST_65}
            and str(self.settings.get("network_policy", NETWORK_POLICY_COMPENSATION)) != NETWORK_POLICY_COMPENSATION
            and snapshot.machine_active
            and not protected_cycle_boiler_allowed_stable(snapshot, t0, self.settings)
        ):
            available = max(snapshot.grid_net_w + (snapshot.boiler_power_w if snapshot.boiler_on else 0.0), 0.0)
            required = float(self.settings["boiler_power_w"])
            self.reset_core(
                f"Cycle machine protégé : boiler en attente, surplus disponible {available:.0f} W < {required:.0f} W requis."
            )
            return

        # Politique Compensation : le réseau est tampon. Les sécurités et
        # fallback thermiques restent inchangés, mais une contrainte purement
        # énergétique HP/import ne force pas l'arrêt du boiler.
        if (
            str(self.settings.get("network_policy", NETWORK_POLICY_COMPENSATION)) == NETWORK_POLICY_COMPENSATION
            and intent.action == BOILER_STOP
            and snapshot.boiler_on
            and ("achat réseau" in intent.reason.lower() or "hp" in intent.reason.lower())
        ):
            intent = type(intent)(
                BOILER_NONE,
                "Compensation : contrainte énergétique ignorée, boiler conservé; sécurités/fallback inchangés.",
                "COMPENSATION",
            )

        self.core_state["boiler_demand"] = intent.action
        self.core_state["boiler_origin"] = intent.origin
        self.core_state["last_reason"] = intent.reason

        if intent.action == BOILER_NONE:
            self.reset_core(intent.reason)
            return
        if intent.action == BOILER_STOP and not snapshot.boiler_on:
            self.reset_core(f"{intent.reason} Boiler déjà arrêté.")
            return
        if intent.action in {BOILER_HEAT_45, BOILER_BOOST_65} and snapshot.boiler_on:
            desired = float(self.settings["boiler_temp_normal_c"] if intent.action == BOILER_HEAT_45 else self.settings["boiler_temp_boost_c"])
            if abs(snapshot.boiler_setpoint_c - desired) < 0.6:
                self.reset_core(f"{intent.reason} Consigne déjà appliquée.")
                return
        await self.async_command_boiler(intent.action, intent.reason, intent.origin)

    def _validate_core_ack(self, snapshot: EnergySnapshot) -> None:
        reference = float(self.core_state.get("action_reference_grid", 0.0))
        expected = float(self.core_state.get("grid_expected", reference))
        delta = float(self.core_state.get("pending_delta", 0.0))
        action = str(self.core_state.get("pending_action", "NONE"))
        error = abs(snapshot.grid_net_w - expected)
        tolerance = float(self.settings["ack_tolerance_w"])
        direction_ok = False
        if action.startswith("BOILER_OFF") or action == "ECS_MODULE_OFF":
            direction_ok = snapshot.grid_net_w >= reference + delta * 0.50
        elif action in {"ECS_MODULE_ON_45", "ECS_MODULE_ON_65", "BOILER_ON_45", "BOILER_ON_45_GARANTIE", "BOILER_ON_45_PRICE"}:
            direction_ok = snapshot.grid_net_w <= reference - delta * 0.50
        elif action == "ECS_MODULE_UPGRADE_65":
            direction_ok = snapshot.boiler_on and snapshot.boiler_setpoint_c >= float(self.settings["boiler_temp_boost_c"]) - 1
        ok = error <= tolerance or direction_ok
        self.core_state["ack_error"] = error
        self.core_state["ack"] = ACK_OK if ok else ACK_NOK
        self.core_state["last_reason"] = (
            f"ACK {'OK' if ok else 'NOK'} : {action}. Référence={reference:.0f} W, "
            f"attendu={expected:.0f} W, réel={snapshot.grid_net_w:.0f} W, erreur={error:.0f} W."
        )

    async def _async_ems_service_call(
        self, domain: str, service: str, data: dict[str, Any], *, timeout: float = 3.0
    ) -> bool:
        """Appel Home Assistant borné : EMS Core ne peut jamais rester bloqué indéfiniment."""
        try:
            await asyncio.wait_for(
                self.hass.services.async_call(domain, service, data, blocking=True),
                timeout=max(float(timeout), 0.5),
            )
            return True
        except asyncio.TimeoutError:
            self.core_state["execution_status"] = "TIMEOUT"
            self.core_state["execution_failure_reason"] = f"Timeout {domain}.{service} après {timeout:.1f} s."
            return False
        except Exception as err:  # pragma: no cover
            self.core_state["execution_status"] = "FAILED"
            self.core_state["execution_failure_reason"] = f"{domain}.{service}: {err}"
            return False

    async def async_command_boiler(self, action: str, reason: str, origin: str) -> None:
        if not bool(self.settings.get("regulation_active")) and origin not in {"UTILISATEUR", "SECURITE"}:
            return
        climate = self.config.get(CONF_BOILER_CLIMATE)
        if not climate:
            self.core_state["execution_status"] = "FAILED"
            self.core_state["execution_failure_reason"] = "Climate boiler non configuré."
            return

        snap = self.snapshot()
        power = max(snap.boiler_power_w, float(self.settings["boiler_power_w"]))
        reference = snap.grid_net_w

        # Communication immédiate vers EMS Onduleur. Le second cœur n'exécute
        # sa réponse physique qu'à la prochaine trame réseau.
        delta_bus = -power if action == BOILER_STOP else float(self.settings["boiler_power_w"])
        bus_message_id = self.energy_bus.publish_ems_intent(
            source="boiler",
            target="ONDULEUR",
            action=action,
            delta_w=delta_bus,
            now=dt_util.now(),
            frame_id=self._frame_id,
            origin=origin,
            reason=reason,
        )
        self.core_state["bus_message_id"] = bus_message_id
        if action == BOILER_STOP:
            expected = reference + power
            pending = "BOILER_OFF_STRATEGY"
            delta = power
        elif action == BOILER_HEAT_45:
            expected = reference - float(self.settings["boiler_power_w"])
            pending = "ECS_MODULE_ON_45" if str(self.settings.get("mode")) == MODE_ECS else ("BOILER_ON_45_PRICE" if str(self.settings.get("mode")) == MODE_DYNAMIC else "BOILER_ON_45")
            delta = float(self.settings["boiler_power_w"])
        elif action == BOILER_BOOST_65:
            if snap.boiler_on:
                expected = reference
                pending = "ECS_MODULE_UPGRADE_65"
                delta = 0.0
            else:
                expected = reference - float(self.settings["boiler_power_w"])
                pending = "ECS_MODULE_ON_65"
                delta = float(self.settings["boiler_power_w"])
        else:
            return

        self.core_state.update(
            {
                "action_reference_grid": reference,
                "grid_expected": expected,
                "pending_delta": delta,
                "pending_action": pending,
                "ack": ACK_WAIT,
                "phase": PHASE_WAIT_ACK,
                "last_action": dt_util.now(),
                "boiler_origin": origin,
                "last_reason": reason,
                "execution_command": pending,
                "execution_status": "QUEUED",
                "execution_retries": 0,
                "execution_failure_reason": "",
            }
        )

        # La commande physique ne vit jamais dans la task de trame EMS.
        # Une sécurité plus récente peut préempter une ancienne commande.
        if self._boiler_command_task and not self._boiler_command_task.done():
            self._boiler_command_task.cancel()
        self._boiler_command_task = self.hass.async_create_task(
            self._execute_boiler_command(action, pending, climate)
        )

    async def _execute_boiler_command(self, action: str, pending: str, climate: str) -> None:
        """Worker physique Boiler indépendant du cadenceur EMS."""
        try:
            self.core_state["execution_status"] = "EXECUTION"
            async with self._ems_action_lock:
                if action == BOILER_STOP:
                    ok = await self._async_ems_service_call(
                        "climate", "set_hvac_mode", {"entity_id": climate, "hvac_mode": "off"}
                    )
                else:
                    target = float(self.settings["boiler_temp_normal_c"] if action == BOILER_HEAT_45 else self.settings["boiler_temp_boost_c"])
                    ok = await self._async_ems_service_call(
                        "climate", "set_temperature", {"entity_id": climate, "temperature": target}
                    )
                    if ok:
                        ok = await self._async_ems_service_call(
                            "climate", "set_hvac_mode", {"entity_id": climate, "hvac_mode": "heat"}
                        )
            if not ok:
                self.energy_bus.publish_message(
                    source="EMS", target="ONDULEUR", action="BOILER_COMMAND_TIMEOUT", delta_w=0.0,
                    now=dt_util.now(), frame_id=self._frame_id,
                    reason=self.core_state.get("execution_failure_reason", "Commande boiler non exécutée."),
                )
                self.async_set_updated_data(self._build_data())
                return

            self._last_boiler_command_at = dt_util.now()
            self.core_state["execution_status"] = "SENT"
            if self._execution_task and not self._execution_task.done():
                self._execution_task.cancel()
            self._execution_task = self.hass.async_create_task(self._verify_boiler_execution(pending))
            self.async_set_updated_data(self._build_data())
        except asyncio.CancelledError:
            self.core_state["execution_status"] = "CANCELLED"
            raise

    async def _verify_boiler_execution(self, command: str) -> None:
        try:
            for attempt in range(4):
                await asyncio.sleep(8 if attempt == 0 else 5)
                snap = self.snapshot()
                climate = self.hass.states.get(self.config.get(CONF_BOILER_CLIMATE)) if self.config.get(CONF_BOILER_CLIMATE) else None
                climate_state = climate.state if climate else "unavailable"
                setpoint = float(climate.attributes.get("temperature", 0)) if climate else 0.0
                command_off = command.startswith("BOILER_OFF") or command == "ECS_MODULE_OFF"
                command_boost = command in {"ECS_MODULE_ON_65", "ECS_MODULE_UPGRADE_65", "ECS_MODULE_SET_65"}
                logical_ok = climate_state == "off" if command_off else climate_state == "heat"
                if command_boost and not command_off:
                    logical_ok = logical_ok and setpoint >= float(self.settings["boiler_temp_boost_c"]) - 1
                physical_ok = (not snap.boiler_on) if command_off else snap.boiler_on
                if logical_ok and physical_ok:
                    self.core_state["execution_status"] = "OK"
                    self.core_state["execution_failure_reason"] = ""
                    self.core_state["execution_retries"] = attempt
                    self.async_set_updated_data(self._build_data())
                    return
                if attempt >= 3:
                    self.core_state["execution_status"] = "FAILED"
                    self.core_state["execution_retries"] = 3
                    self.core_state["execution_failure_reason"] = (
                        f"Commande {command} non exécutée après 3 tentatives. Climate={climate_state}, "
                        f"boiler={snap.boiler_power_w:.0f} W."
                    )
                    self.async_set_updated_data(self._build_data())
                    return
                if self._execution_blocked(command, snap):
                    self.core_state["execution_status"] = "BLOCKED"
                    self.core_state["execution_failure_reason"] = "Retry bloqué par sécurité, priorité machine, mode ou autorisation."
                    self.async_set_updated_data(self._build_data())
                    return
                self.core_state["execution_status"] = "RETRY"
                self.core_state["execution_retries"] = attempt + 1
                await self._retry_boiler_command(command)
        except asyncio.CancelledError:
            return
        except Exception as err:  # pragma: no cover - HA runtime defensive path
            _LOGGER.exception("FoxCat boiler verifier error: %s", err)
            self.core_state["execution_status"] = "FAILED"
            self.core_state["execution_failure_reason"] = str(err)

    def _execution_blocked(self, command: str, snap: EnergySnapshot) -> bool:
        command_on = not (command.startswith("BOILER_OFF") or command == "ECS_MODULE_OFF")
        if not command_on:
            return False
        if (
            not bool(self.settings["boiler_enabled"])
            or not bool(self.settings.get("device_boiler_enabled", True))
            or snap.boiler_safety_temp_c >= float(self.settings["boiler_temp_safety_c"])
        ):
            return True
        # Un démarrage utilisateur garde la priorité sur les stratégies EMS et
        # les cycles machines. La sécurité thermique reste souveraine.
        if str(self.core_state.get("boiler_user_override", "AUTO")) == "FORCE_ON":
            return False
        if snap.machine_active and not protected_cycle_boiler_allowed(snap, self.settings):
            return True
        if str(self.settings.get("mode")) == MODE_MANUAL:
            return True
        return False

    async def _retry_boiler_command(self, command: str) -> None:
        if (
            not bool(self.settings.get("regulation_active"))
            and str(self.core_state.get("boiler_user_override", "AUTO")) != "FORCE_ON"
        ):
            return
        climate = self.config.get(CONF_BOILER_CLIMATE)
        if not climate:
            return
        async with self._ems_action_lock:
            if command.startswith("BOILER_OFF") or command == "ECS_MODULE_OFF":
                await self._async_ems_service_call(
                    "climate", "set_hvac_mode", {"entity_id": climate, "hvac_mode": "off"}
                )
            else:
                boost = command in {"ECS_MODULE_ON_65", "ECS_MODULE_UPGRADE_65", "ECS_MODULE_SET_65"}
                temp = float(self.settings["boiler_temp_boost_c"] if boost else self.settings["boiler_temp_normal_c"])
                if await self._async_ems_service_call(
                    "climate", "set_temperature", {"entity_id": climate, "temperature": temp}
                ):
                    await self._async_ems_service_call(
                        "climate", "set_hvac_mode", {"entity_id": climate, "hvac_mode": "heat"}
                    )

    async def async_handle_safety_change(self) -> None:
        snap = self.snapshot()
        # Sécurité thermique toujours souveraine, y compris régulation désactivée
        # et override utilisateur actif.
        if snap.boiler_on and snap.boiler_safety_temp_c >= float(self.settings["boiler_temp_safety_c"]):
            await self.async_command_boiler(BOILER_STOP, "SÉCURITÉ : température boiler maximale atteinte.", "SECURITE")
        elif bool(self.settings.get("regulation_active")):
            mode = str(self.settings.get("mode"))
            user_override = str(self.core_state.get("boiler_user_override", "AUTO"))
            if (
                user_override == "AUTO"
                and mode != MODE_MANUAL
                and snap.boiler_on
                and snap.machine_active
                and not protected_cycle_boiler_allowed(snap, self.settings)
            ):
                await self.async_command_boiler(
                    BOILER_STOP,
                    "Cycle machine protégé : surplus solaire insuffisant pour maintenir le boiler.",
                    "MACHINE",
                )
            if mode != MODE_MANUAL:
                await self.async_reconcile_machines()
        self.async_set_updated_data(self._build_data(snap))

    @staticmethod
    def _time_minutes(value: Any, default: str) -> int:
        raw = str(value or default)
        try:
            parts = raw.split(":")
            return (int(parts[0]) % 24) * 60 + (int(parts[1]) % 60)
        except (ValueError, IndexError, TypeError):
            h, m = default.split(":")[:2]
            return int(h) * 60 + int(m)

    @staticmethod
    def _within_time_window(now_minute: int, start_minute: int, stop_minute: int) -> bool:
        if start_minute == stop_minute:
            return False
        if start_minute < stop_minute:
            return start_minute <= now_minute < stop_minute
        return now_minute >= start_minute or now_minute < stop_minute

    def _machine_allowed(self, machine_id: str, now: datetime) -> bool:
        machine = next((item for item in self.machines if item.machine_id == machine_id), None)
        return machine_allowed(machine, now) if machine else False

    def _machine_schedule_boundaries(self) -> set[tuple[int, int]]:
        return schedule_boundaries(self.machines)

    def _tariff_start_favorable(self, machine: MachineDefinition | None = None, economic_view: dict[str, Any] | None = None) -> bool:
        """Décide si une NOUVELLE charge flexible peut démarrer.

        V1.6.153 : le comparateur économique est consulté directement, sans
        passer par Energy Bus. Les cycles déjà actifs/protégés restent gérés
        par la règle souveraine de ``async_reconcile_machines``. Si
        l'optimiseur est désactivé, le comportement historique est conservé.
        """
        prices = self.prices()
        regime = str(self.settings.get("tariff_regime", TARIFF_TOU))
        if not bool(self.settings.get("economic_optimizer_enabled", True)):
            if regime == TARIFF_DYNAMIC:
                current = prices.get("current")
                nxt = prices.get("next")
                avg = prices.get("avg_today")
                if not isinstance(current, (int, float)):
                    return False
                if isinstance(nxt, (int, float)) and current > nxt:
                    return False
                if isinstance(avg, (int, float)) and current > avg:
                    return False
                return True
            return str(prices.get("period")) == "HC"

        view = economic_view or self._economic_view(self.snapshot(), prices=prices)
        if machine is not None:
            if regime == TARIFF_DYNAMIC and str(self.settings.get("mode")) == MODE_DYNAMIC:
                plan = (view.get("day_ahead", {}).get("machines", {}) or {}).get(machine.machine_id)
                if isinstance(plan, dict):
                    return bool(plan.get("allow_start_now", False))
            rec = view.get("machines", {}).get(machine.machine_id)
            if isinstance(rec, dict):
                return bool(rec.get("allow_start", False))
        return bool(view.get("decision", {}).get("flexible_start", False))

    def _schedule_learning_save(self) -> None:
        if self._learning_save_task is None or self._learning_save_task.done():
            self._learning_save_task = self.hass.async_create_task(self._async_save())

    def _record_machine_learning(
        self, *, snapshot: EnergySnapshot, now: datetime, source: str
    ) -> None:
        """Observe les machines sans modifier leur machine à états."""
        if not self.machines:
            return
        prices = self.prices()
        cycle_snapshot = self.machine_cycle_manager.snapshot(now)
        context = {
            "grid_w": snapshot.grid_net_w,
            "pv_w": snapshot.pv_w,
            "house_w": snapshot.house_w,
            "price": prices.get("active_buy"),
            "tariff": prices.get("period") if prices.get("regime") != TARIFF_DYNAMIC else "DYNAMIQUE",
        }
        save_requested = False
        for machine in self.machines:
            cycle = cycle_snapshot.get(machine.machine_id, {})
            save_requested = self.machine_learning.observe(
                machine_id=machine.machine_id,
                name=machine.name,
                now=now,
                power_w=self._optional_float_state(machine.power_sensor),
                current_a=self._optional_float_state(machine.current_sensor),
                voltage_v=self._optional_float_state(machine.voltage_sensor),
                switch_on=self._is_on(machine.switch_entity),
                cycle_state=str(cycle.get("state", "IDLE")),
                cycle_origin=str(cycle.get("origin", "NONE")),
                cycle_protected=bool(cycle.get("protected", False)),
                start_w=machine.cycle_start_w,
                end_w=machine.cycle_end_w,
                end_confirm_s=machine.cycle_end_confirm_minutes * 60.0,
                context=context,
                source=source,
            ) or save_requested
        if save_requested:
            self._schedule_learning_save()

    def _machine_bus_context(self, now: datetime) -> list[dict[str, Any]]:
        """Contexte machine transporté dans la trame, sans effet décisionnel."""
        cycles = self.machine_cycle_manager.snapshot(now)
        learning = self.machine_learning.view()
        result: list[dict[str, Any]] = []
        for machine in self.machines:
            cycle = cycles.get(machine.machine_id, {})
            profile = learning.get(machine.machine_id, {})
            result.append({
                "id": machine.machine_id,
                "name": machine.name,
                "switch_on": self._is_on(machine.switch_entity),
                "power_w": self._optional_float_state(machine.power_sensor),
                "current_a": self._optional_float_state(machine.current_sensor),
                "voltage_v": self._optional_float_state(machine.voltage_sensor),
                "cycle_state": cycle.get("state", "IDLE"),
                "cycle_protected": bool(cycle.get("protected", False)),
                "cycle_origin": cycle.get("origin", "NONE"),
                "learning_cycle_active": bool((profile.get("current") or {}).get("active", False)),
                "learning_cycles_collected": int(profile.get("total_cycles", 0)),
            })
        return result

    def _refresh_machine_cycles(self) -> None:
        now = dt_util.now()
        for machine in self.machines:
            power = self._optional_float_state(machine.power_sensor) or 0.0
            external = bool(machine.cycle_entity and self._is_on(machine.cycle_entity))
            self.machine_cycle_manager.update(
                machine.machine_id, power, now,
                start_w=machine.cycle_start_w,
                start_confirm_s=machine.cycle_start_confirm_s,
                duration_minutes=machine.cycle_duration_minutes,
                margin_minutes=machine.cycle_margin_minutes,
                end_w=machine.cycle_end_w,
                end_confirm_minutes=machine.cycle_end_confirm_minutes,
                external_cycle_on=external,
            )

    def machine_states(self, economic_view: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self._refresh_machine_cycles()
        now = dt_util.now()
        if economic_view is None and self.machines:
            economic_view = self._economic_view(self.snapshot(), prices=self.prices(), now=now)
        result: list[dict[str, Any]] = []
        for machine in self.machines:
            result.append({
                "id": machine.machine_id,
                "name": machine.name,
                "switch": machine.switch_entity,
                "cycle_entity": machine.cycle_entity,
                "power_sensor": machine.power_sensor,
                "current_sensor": machine.current_sensor,
                "voltage_sensor": machine.voltage_sensor,
                "power_w": self._optional_float_state(machine.power_sensor),
                "current_a": self._optional_float_state(machine.current_sensor),
                "voltage_v": self._optional_float_state(machine.voltage_sensor),
                "cycle_active": self.machine_cycle_manager.is_protected(machine.machine_id),
                "foxcat_cycle_state": self.machine_cycle_manager.state_for(machine.machine_id).state,
                "foxcat_cycle_origin": self.machine_cycle_manager.state_for(machine.machine_id).origin,
                "automatic": bool(self.settings.get(machine.setting_key, machine.automatic_default)),
                "sheddable": machine.sheddable,
                "window_open": machine_allowed(machine, now),
                "tariff_period": tariff_period(now, self.settings),
                "tariff_start_favorable": self._tariff_start_favorable(machine, economic_view=economic_view),
            })
        return result

    async def async_set_machine_enabled(self, machine_id: str, enabled: bool) -> None:
        machine = next((item for item in self.machines if item.machine_id == machine_id), None)
        if machine is None:
            return
        self.settings[machine.setting_key] = bool(enabled)
        await self._async_save()
        await self.async_reconcile_machines()
        self.async_set_updated_data(self._build_data())

    async def async_set_device_enabled(self, device_id: str, enabled: bool) -> None:
        from .devices import apply_device_toggle

        try:
            action = apply_device_toggle(self.settings, device_id, enabled)
        except ValueError:
            return

        if action == "release_inverter":
            await self.async_set_setting("pri_enabled", False)
            return
        if action == "stop_regulation":
            await self.async_set_setting("regulation_active", False)
            return
        if action == "stop_boiler" and self.snapshot().boiler_on:
            await self.async_command_boiler(
                BOILER_STOP,
                "Boiler désactivé depuis le menu Appareils.",
                "UTILISATEUR",
            )
        if device_id == "boiler" and not enabled:
            await self.async_release_pri_100(
                "Boiler désactivé : onduleur libéré à 100 %."
            )
        if action == "reconcile_machines":
            await self.async_reconcile_machines()
        await self._async_save()
        self.async_set_updated_data(self._build_data())

    async def _async_user_switch_call(self, entity_id: str, turn_on: bool) -> bool:
        """Commande utilisateur bornée, sans polluer l'état d'exécution Boiler."""
        try:
            await asyncio.wait_for(
                self.hass.services.async_call(
                    "switch", "turn_on" if turn_on else "turn_off",
                    {"entity_id": entity_id}, blocking=True,
                ),
                timeout=3.0,
            )
            return True
        except (asyncio.TimeoutError, Exception) as err:
            _LOGGER.warning("FoxCat user switch command failed for %s: %s", entity_id, err)
            return False

    async def async_user_start_machine(self, machine_id: str) -> bool:
        """Démarrage utilisateur : priorité au cycle protégé, sans attendre l'EMS."""
        machine = next((item for item in self.machines if item.machine_id == machine_id), None)
        if machine is None or not machine.switch_entity:
            return False
        now = dt_util.now()
        self.machine_cycle_manager.force_start(
            machine.machine_id, now,
            duration_minutes=machine.cycle_duration_minutes,
            margin_minutes=machine.cycle_margin_minutes,
            origin="USER_BUTTON",
        )
        ok = await self._async_user_switch_call(machine.switch_entity, True)
        if not ok:
            # Une commande physique refusée ne doit pas laisser un faux cycle
            # protégé pendant plusieurs heures.
            self.machine_cycle_manager.force_finish(machine.machine_id)
        message_id = self.energy_bus.publish_message(
            source="UTILISATEUR", target="EMS", action=f"MACHINE_START:{machine.machine_id}",
            delta_w=0.0, now=now, frame_id=self._frame_id, machine=machine.name,
            reason="Démarrage utilisateur : cycle protégé.",
        )
        self.energy_bus.mark_processed(
            message_id, by="EMS", now=dt_util.now(),
            reason="Commande machine utilisateur prise en charge." if ok else "Commande machine utilisateur en échec.",
        )
        self.core_state["last_reason"] = (
            f"Utilisateur : démarrage {machine.name} {'envoyé' if ok else 'échoué'} ; cycle protégé actif."
        )
        self.async_set_updated_data(self._build_data())
        return ok

    async def async_user_stop_machine(self, machine_id: str) -> bool:
        """Arrêt utilisateur explicite : termine la protection puis coupe la prise."""
        machine = next((item for item in self.machines if item.machine_id == machine_id), None)
        if machine is None or not machine.switch_entity:
            return False
        self.machine_cycle_manager.force_finish(machine.machine_id)
        ok = await self._async_user_switch_call(machine.switch_entity, False)
        message_id = self.energy_bus.publish_message(
            source="UTILISATEUR", target="EMS", action=f"MACHINE_STOP:{machine.machine_id}",
            delta_w=0.0, now=dt_util.now(), frame_id=self._frame_id, machine=machine.name,
            reason="Arrêt utilisateur explicite.",
        )
        self.energy_bus.mark_processed(
            message_id, by="EMS", now=dt_util.now(),
            reason="Arrêt machine utilisateur pris en charge." if ok else "Arrêt machine utilisateur en échec.",
        )
        self.core_state["last_reason"] = f"Utilisateur : arrêt {machine.name} {'envoyé' if ok else 'échoué'}."
        self.async_set_updated_data(self._build_data())
        return ok

    async def async_user_boiler_override(self, state: str) -> bool:
        """Commande utilisateur Boiler : FORCE_ON, FORCE_OFF ou AUTO."""
        state = str(state).upper()
        if state not in {"FORCE_ON", "FORCE_OFF", "AUTO"}:
            return False
        self.core_state["boiler_user_override"] = state
        now = dt_util.now()
        if state == "AUTO":
            self.reset_core("Utilisateur : Boiler rendu à l'EMS automatique.")
            action = "BOILER_AUTO"
            ok = True
        elif state == "FORCE_OFF":
            action = "BOILER_USER_STOP"
            await self.async_command_boiler(BOILER_STOP, "Utilisateur : arrêt Boiler forcé.", "UTILISATEUR")
            ok = True
        else:
            snap = self.snapshot()
            if not bool(self.settings.get("boiler_enabled")) or not bool(self.settings.get("device_boiler_enabled", True)):
                self.core_state["last_reason"] = "Utilisateur : démarrage Boiler refusé car la fonction Boiler est désactivée."
                self.core_state["boiler_user_override"] = "AUTO"
                action = "BOILER_USER_START_BLOCKED"
                ok = False
            elif snap.boiler_safety_temp_c >= float(self.settings["boiler_temp_safety_c"]):
                self.core_state["last_reason"] = "Utilisateur : démarrage Boiler refusé par sécurité température."
                self.core_state["boiler_user_override"] = "AUTO"
                action = "BOILER_USER_START_BLOCKED"
                ok = False
            else:
                action = "BOILER_USER_START"
                await self.async_command_boiler(BOILER_HEAT_45, "Utilisateur : démarrage Boiler forcé.", "UTILISATEUR")
                ok = True
        message_id = self.energy_bus.publish_message(
            source="UTILISATEUR", target="EMS", action=action, delta_w=0.0, now=now,
            frame_id=self._frame_id, reason=f"Override Boiler={state}.",
        )
        self.energy_bus.mark_processed(
            message_id, by="EMS", now=dt_util.now(),
            reason="Commande utilisateur Boiler enregistrée." if ok else "Commande utilisateur Boiler refusée par sécurité.",
        )
        self.async_set_updated_data(self._build_data())
        return ok

    async def async_reconcile_machines(self) -> None:
        if not bool(self.settings.get("regulation_active")):
            return
        if str(self.settings.get("mode")) == MODE_MANUAL:
            # Manuel = handover complet. FoxCat ne change aucune prise machine.
            return
        now = dt_util.now()
        self._refresh_machine_cycles()
        economic_view = (
            self._economic_view(self.snapshot(), prices=self.prices(), now=now)
            if bool(self.settings.get("economic_optimizer_enabled", True)) else None
        )
        for machine in self.machines:
            socket = machine.switch_entity
            if not socket:
                continue
            cycle_active = self.machine_cycle_manager.is_protected(machine.machine_id)
            management = bool(self.settings.get(machine.setting_key, machine.automatic_default)) and bool(
                self.settings.get("device_machines_enabled", True)
            )
            allowed = machine_allowed(machine, now)
            # Règle souveraine : un cycle déjà commencé n'est jamais interrompu.
            # Pendant un délestage, seules les machines explicitement délestables
            # et sans cycle protégé actif sont coupées.
            high_load_block = bool(self.load_shed_state.get("active")) and machine.sheddable and not cycle_active
            tariff_ok = self._tariff_start_favorable(machine, economic_view=economic_view)
            # Un cycle utilisateur/protégé reste prioritaire. Seul un NOUVEAU
            # démarrage automatique est bloqué en période défavorable.
            should_on = cycle_active or (management and allowed and tariff_ok and not high_load_block)
            service = "turn_on" if should_on else "turn_off"
            try:
                await self.hass.services.async_call("switch", service, {"entity_id": socket}, blocking=False)
            except Exception as err:  # pragma: no cover
                _LOGGER.warning("FoxCat machine socket command failed for %s (%s): %s", machine.name, socket, err)

    async def _evaluate_high_load(self, snapshot: EnergySnapshot) -> None:
        """Délestage synchronisé sur chaque publication réseau.

        2 trames hautes consécutives déclenchent. 5 trames basses réarment.
        Une mesure maison invalide gèle l'état et n'est jamais assimilée à 0 W.
        """
        if not snapshot.valid:
            self.load_shed_state["reason"] = "Bilan énergétique invalide : état de délestage conservé."
            self._high_load_high_frames = 0
            self._high_load_low_frames = 0
            return
        self.load_shed_state["house_w"] = snapshot.house_w
        enabled=bool(self.settings.get("high_load_shed_enabled"))
        automatic=str(self.settings.get("mode")) != MODE_MANUAL
        if not enabled or not automatic:
            self._high_load_high_frames=self._high_load_low_frames=0
            if self.load_shed_state.get("active"):
                self.load_shed_state.update({"active":False,"reason":"Délestage indisponible ou mode Manuel","triggered_at":None})
                await self.async_reconcile_machines()
            return
        trigger=float(self.settings.get("high_load_trigger_w",5000.0))
        release=min(float(self.settings.get("high_load_release_w",3500.0)),trigger)
        if not self.load_shed_state.get("active"):
            self._high_load_low_frames=0
            self._high_load_high_frames = self._high_load_high_frames + 1 if snapshot.house_w >= trigger else 0
            if self._high_load_high_frames >= 2:
                await self._activate_high_load_shed(snapshot,trigger)
                self._high_load_high_frames=0
        else:
            self._high_load_high_frames=0
            self._high_load_low_frames = self._high_load_low_frames + 1 if snapshot.house_w <= release else 0
            if self._high_load_low_frames >= 5:
                self.load_shed_state.update({"active":False,"reason":f"5 trames sous {release:.0f} W","triggered_at":None})
                self._high_load_low_frames=0
                self.reset_core("Fin délestage : 5 trames basses confirmées.")
                await self.async_reconcile_machines()

    async def _activate_high_load_shed(self, snapshot: EnergySnapshot, trigger_w: float) -> None:
        self.load_shed_state.update({
            "active": True,
            "reason": f"Puissance maison {snapshot.house_w:.0f} W >= {trigger_w:.0f} W",
            "triggered_at": dt_util.now(),
            "house_w": snapshot.house_w,
        })
        self._high_load_since = None
        self._high_load_below_since = None
        self.reset_core("Délestage haute consommation déclenché.")

        if self._pri_task and not self._pri_task.done():
            self._pri_task.cancel()
        # En forte demande, EMS informe Onduleur Core via Energy Bus et pousse
        # une cible 100 % au worker physique sans bloquer la trame EMS.
        self.energy_bus.publish_message(
            source="EMS", target="ONDULEUR", action="DELESTAGE_LIBERATION_100", delta_w=0.0,
            now=dt_util.now(), frame_id=self._frame_id,
            reason="Délestage haute consommation : libération onduleur demandée.",
        )
        self._queue_pri_target(
            100, frame_id=self._frame_id, frame_serial=self._frame_serial,
            pv_before=snapshot.pv_w, reason="Délestage haute consommation.",
        )

        if snapshot.boiler_on:
            await self.async_command_boiler(
                BOILER_STOP,
                "Délestage haute consommation : arrêt temporaire du chauffe-eau.",
                "DELESTAGE",
            )
        await self.async_reconcile_machines()

    async def async_handle_price_change(self) -> None:
        snap = self.snapshot()
        if (
            bool(self.settings.get("regulation_active"))
            and str(self.settings.get("mode")) == MODE_DYNAMIC
            and str(self.settings.get("tariff_regime")) == TARIFF_DYNAMIC
        ):
            # Un changement de prix doit pouvoir déclencher immédiatement le
            # mode financier, notamment le passage sous 0 €/kWh. On crée un T0
            # stable avec la mesure courante puis on évalue la stratégie.
            self.reset_core("Nouvelle trame tarifaire dynamique : réévaluation immédiate.")
            self.core_state["t0"] = snap
            self._set_core_phase(PHASE_DECISION)
            await self._core_process_frame(snap)
            self._maybe_start_pri(snap)
            # Le changement de créneau/prix doit aussi réévaluer immédiatement
            # les NOUVEAUX départs LL/SL/LV. Les cycles protégés restent souverains.
            await self.async_reconcile_machines()
        self.async_set_updated_data(self._build_data(snap))

    async def async_handle_pv_change(self) -> None:
        await self._check_end_solar()
        self.async_set_updated_data(self._build_data())

    async def _check_end_solar(self) -> None:
        if not bool(self.settings.get("regulation_active")):
            self._pv_below_since = None
            return
        mode = str(self.settings.get("mode"))
        if mode not in {MODE_ECO, MODE_ZERO}:
            self._pv_below_since = None
            return
        pv = self._float_state(self.config.get(CONF_PV_SENSOR))
        # Une production bridée ne mesure pas le potentiel solaire. À PRI <100 %,
        # et particulièrement à 0 %, FoxCat interdit toute conclusion "fin solaire".
        level = self._rrcr_level()
        if 0 <= level < 100 or self.pri_state.get("solar_state") in {"PV_LIMITED","PRI_ACK_PENDING","PV_UNKNOWN"}:
            self._pv_below_since = None
            return
        threshold = float(self.settings["pri_end_solar_w"])
        now = dt_util.now()
        if pv < threshold:
            if self._pv_below_since is None:
                self._pv_below_since = now
            elif (now - self._pv_below_since).total_seconds() >= float(self.settings["pri_end_solar_confirm_s"]):
                if self._pri_task and not self._pri_task.done():
                    self._pri_task.cancel()
                await self.async_release_pri_100("Fin solaire confirmée : onduleur libéré à 100 %.")
                self.core_state["last_reason"] = (
                    "Fin solaire confirmée : onduleur libéré à 100 %, "
                    f"mode EMS conservé ({mode})."
                )
                self._pv_below_since = None
        else:
            self._pv_below_since = None

    async def _watchdog(self) -> None:
        now = dt_util.now()
        valid_phases = {PHASE_ACQUISITION, PHASE_DECISION, PHASE_WAIT_ACK}
        if self.core_state.get("phase") not in valid_phases:
            self.core_state["fsm_status"] = "ERREUR_PHASE"
            self.reset_core("Watchdog : phase EMS invalide, machine à états réinitialisée.")
        else:
            self.core_state["fsm_status"] = "OK"

        bus_timeout = max(float(self.settings.get("metronome_period_s", 30.0)) * 1.5, 45.0)
        expired = self.energy_bus.expire_pending(now=now, timeout_s=bus_timeout)
        if expired:
            self.core_state["last_reason"] = (
                "Energy Bus : ACK inter-corps expiré pour message(s) "
                + ", ".join(str(item) for item in expired)
                + "."
            )

        last = self.core_state.get("last_frame")
        if not isinstance(last, datetime):
            return
        age = (now - last).total_seconds()
        if age > float(self.settings["watchdog_timeout_s"]):
            if self.core_state.get("phase") != PHASE_ACQUISITION:
                self.reset_core(f"Watchdog : aucune nouvelle trame depuis {age:.0f} s, machine d'états réinitialisée.")

    def _pri_settle_ok(self) -> bool:
        if self._last_boiler_command_at is None:
            return True
        age = (dt_util.now() - self._last_boiler_command_at).total_seconds()
        return age >= float(self.settings.get("pri_boiler_settle_s", 30.0))

    def _dynamic_tariff_ok(self) -> bool:
        return not (
            str(self.settings.get("mode")) == MODE_DYNAMIC
            and str(self.settings.get("tariff_regime")) != TARIFF_DYNAMIC
        )

    def _maybe_start_pri(self, snapshot: EnergySnapshot) -> None:
        """Compatibilité 1.3.x : aucune horloge PRI indépendante en 1.3.200."""
        return

    def _pri_guard(self) -> bool:
        """Garde minimale de la réduction puissance onduleur."""
        if not bool(self.settings.get("regulation_active")):
            self.pri_state["guard_reason"] = "regulation_inactive"
            return False
        if not bool(self.settings.get("pri_enabled")):
            self.pri_state["guard_reason"] = "reduction_onduleur_desactivee"
            return False
        if str(self.settings.get("mode")) not in {MODE_ECO, MODE_ZERO, MODE_DYNAMIC}:
            self.pri_state["guard_reason"] = f"mode_{self.settings.get('mode')}"
            return False
        self.pri_state["guard_reason"] = "OK"
        return True


    def _rrcr_code(self) -> str:
        bits = []
        for key in (CONF_PRI_L4, CONF_PRI_L3, CONF_PRI_L2, CONF_PRI_L1):
            entity_id = self.config.get(key)
            state = self.hass.states.get(entity_id) if entity_id else None
            if not state or state.state not in {"on", "off"}:
                return "????"
            bits.append("1" if state.state == "on" else "0")
        return "".join(bits)

    def _rrcr_level(self) -> int:
        return RRCR_CODE_TO_LEVEL.get(self._rrcr_code(), -1)

    async def _apply_rrcr_level(self, level: int) -> bool:
        """Envoie une commande RRCR sans jamais bloquer Onduleur Core."""
        code = RRCR_LEVEL_TO_CODE.get(int(level))
        if code is None:
            return False
        entities = [self.config.get(CONF_PRI_L4), self.config.get(CONF_PRI_L3), self.config.get(CONF_PRI_L2), self.config.get(CONF_PRI_L1)]
        if not all(entities):
            return False
        async with self._inverter_action_lock:
            for entity_id, bit in zip(entities, code, strict=True):
                try:
                    # blocking=False : la décision PRI ne dépend jamais d'une réponse
                    # de service Home Assistant. L'état réel est contrôlé ensuite.
                    await asyncio.wait_for(
                        self.hass.services.async_call(
                            "switch", "turn_on" if bit == "1" else "turn_off",
                            {"entity_id": entity_id}, blocking=False,
                        ),
                        timeout=2.0,
                    )
                except asyncio.TimeoutError:
                    self.pri_state["actuator_last_error"] = f"Timeout service RRCR {entity_id}."
                    return False
        return True

    async def _wait_rrcr_code(self, code: str, timeout: float = 5.0) -> bool:
        end = asyncio.get_running_loop().time() + timeout
        while asyncio.get_running_loop().time() < end:
            if self._rrcr_code() == code:
                return True
            await asyncio.sleep(0.25)
        return self._rrcr_code() == code

    def _queue_pri_target(
        self,
        level: int,
        *,
        frame_id: int,
        frame_serial: int,
        pv_before: float,
        reason: str,
    ) -> None:
        """Mémorise uniquement la dernière consigne physique demandée.

        Toutes les trames sont calculées immédiatement. Le worker RRCR ne crée
        donc jamais une file de vieilles trames : il converge vers la consigne
        issue de la publication la plus récente.
        """
        self._pri_requested = {
            "level": int(level),
            "frame_id": int(frame_id),
            "frame_serial": int(frame_serial),
            "pv_before": float(pv_before),
            "reason": str(reason),
            "requested_at": dt_util.now(),
        }
        self.pri_state["actuator_target_level"] = int(level)
        self.pri_state["actuator_status"] = "QUEUED"
        if self._pri_actuator_task is None or self._pri_actuator_task.done():
            self._pri_actuator_task = self.hass.async_create_task(self._pri_actuator_loop())

    async def _pri_actuator_loop(self) -> None:
        """Applique la dernière consigne RRCR avec timeout et sans bloquer les trames."""
        try:
            while self._pri_requested is not None:
                request = self._pri_requested
                self._pri_requested = None
                target = int(request["level"])
                current = self._rrcr_level()
                self.pri_state["actuator_status"] = "EXECUTION"
                self.pri_state["actuator_target_level"] = target
                self.pri_state["actuator_last_error"] = ""

                if current == target:
                    self.pri_state["actuator_status"] = "OK"
                    continue

                try:
                    sent = await asyncio.wait_for(self._apply_rrcr_level(target), timeout=4.0)
                except asyncio.TimeoutError:
                    sent = False
                    self.pri_state["actuator_last_error"] = f"Timeout global commande RRCR {target} %."

                # Si une trame plus récente a changé la cible pendant l'envoi,
                # on ne perd pas de temps à valider une consigne déjà obsolète.
                if self._pri_requested is not None and int(self._pri_requested.get("level", target)) != target:
                    self.pri_state["actuator_status"] = "SUPERSEDED"
                    continue

                confirmed = sent and await self._wait_rrcr_code(RRCR_LEVEL_TO_CODE[target], timeout=5.0)
                if not confirmed:
                    self.pri_state["ack_rrcr"] = "FAILED"
                    self.pri_state["actuator_status"] = "FAILED"
                    if not self.pri_state.get("actuator_last_error"):
                        self.pri_state["actuator_last_error"] = f"RRCR {target} % non confirmé avant timeout."
                    # Pas de rollback bloquant : la prochaine publication reste
                    # souveraine et peut immédiatement demander une autre cible.
                    continue

                # Si plusieurs trames ont demandé la même cible pendant la
                # commutation, rattacher l'ACK physique à la plus récente.
                if self._pri_requested is not None and int(self._pri_requested.get("level", -1)) == target:
                    request = self._pri_requested
                    self._pri_requested = None

                self.pri_state.update({
                    "current_level": target,
                    "ack_rrcr": "PENDING",
                    "ack_inverter": "PENDING",
                    "ack_grid": "PENDING",
                    "pending_level": target,
                    "pending_frame_id": int(request["frame_id"]),
                    "pending_frame_serial": int(request["frame_serial"]),
                    "pending_pv_before": float(request["pv_before"]),
                    "actuator_status": "OK",
                })
                self.async_set_updated_data(self._build_data())
        except asyncio.CancelledError:
            self.pri_state["actuator_status"] = "CANCELLED"
            raise
        except Exception as err:  # pragma: no cover - defensive HA runtime
            _LOGGER.exception("FoxCat PRI actuator error: %s", err)
            self.pri_state["actuator_status"] = "FAILED"
            self.pri_state["actuator_last_error"] = str(err)

    async def async_release_pri_100(self, reason: str) -> None:
        entities = [self.config.get(CONF_PRI_L1), self.config.get(CONF_PRI_L2), self.config.get(CONF_PRI_L3), self.config.get(CONF_PRI_L4)]
        if not all(entities):
            self.pri_state.update({"current_level": 100, "target_level": 100, "code": "0000", "last_reason": f"{reason} Relais PRI non configurés."})
            return
        try:
            sent = await self._apply_rrcr_level(100)
            confirmed = sent and await self._wait_rrcr_code(RRCR_LEVEL_TO_CODE[100], timeout=5.0)
            if not confirmed:
                raise RuntimeError(f"RRCR 100 % non confirmé (code={self._rrcr_code()}).")
            self.pri_state.update({"current_level": 100, "target_level": 100, "code": "0000", "direction": "maintien", "last_reason": reason, "ack_rrcr": "OK"})
        except Exception as err:  # pragma: no cover
            _LOGGER.warning("Unable to release PRI to 100%%: %s", err)
            self.pri_state["ack_rrcr"] = "FAILED"
            self.pri_state["last_reason"] = f"Échec fail-safe 100 % : {err}"

    def _classify_pri_grid(self, snapshot: EnergySnapshot) -> str:
        """Classe le résultat réseau PRI sans lever d'exception.

        Le réseau signé FoxCat est positif en prélèvement et négatif en
        réinjection. L'ACK est OK tant que la trame reste dans l'enveloppe
        configurable ; sinon la cause est explicitement indiquée.
        """
        if not snapshot.valid:
            return "NOK_DONNEES"
        export_limit = max(float(self.settings.get("pri_export_acceptable_w", 150.0)), 0.0)
        import_limit = max(float(self.settings.get("pri_import_acceptable_w", 200.0)), 0.0)
        if snapshot.export_w > export_limit:
            return "NOK_REINJECTION"
        if snapshot.import_w > import_limit:
            return "NOK_PRELEVEMENT"
        return "OK"

    def _update_pri_pv_comparator(self, snapshot: EnergySnapshot, level: int) -> None:
        max_w=float(self.settings.get("pri_step_w",400.0))*10.0
        limit=max_w*max(level,0)/100.0
        tol=float(self.settings.get("pri_pv_compare_tolerance_w",200.0))
        err=snapshot.pv_w-limit
        if level <= 0:
            state="PV_UNKNOWN"
            potential=0.0
        elif abs(err) <= tol:
            state="PV_LIMITED"
            potential=max(limit-tol,0.0)
        elif snapshot.pv_w < limit-tol:
            state="PV_BELOW_LIMIT"
            potential=max(snapshot.pv_w,0.0)
        else:
            state="PRI_INCONSISTENT"
            potential=max(snapshot.pv_w,0.0)
        self.pri_state.update({"solar_state":state,"solar_potential_min_w":potential,
                               "pv_limit_w":limit,"pv_limit_error_w":err})

    async def _validate_pending_pri_on_frame(self, snapshot: EnergySnapshot, *, frame_serial: int | None = None) -> None:
        if not snapshot.valid:
            return
        pending=self.pri_state.get("pending_level")
        pending_frame=self.pri_state.get("pending_frame_id")
        pending_serial=self.pri_state.get("pending_frame_serial")
        current_serial = int(frame_serial if frame_serial is not None else self._frame_serial)
        if pending is None or pending_frame is None or pending_serial is None or current_serial <= int(pending_serial):
            return
        level=self._rrcr_level()
        if level != int(pending):
            self.pri_state["ack_rrcr"]="FAILED"
            self.pri_state["last_reason"]=f"ACK N+1 : RRCR {level}% != commande {pending}%."
        else:
            self.pri_state["ack_rrcr"]="OK"
            self._update_pri_pv_comparator(snapshot,level)
            self.pri_state["ack_inverter"]="OK" if self.pri_state["solar_state"]!="PRI_INCONSISTENT" else "FAILED"
            self.pri_state["ack_grid"]=self._classify_pri_grid(snapshot)
        self.pri_state["pending_level"]=None
        self.pri_state["pending_frame_id"]=None
        self.pri_state["pending_frame_serial"]=None
        self.pri_state["pending_pv_before"]=None

    async def _run_pri_frame(
        self, snapshot: EnergySnapshot, *, frame_id: int | None = None, frame_serial: int | None = None
    ) -> str:
        """Onduleur Core 1.6.150 : décision immédiate, action RRCR asynchrone."""
        self.pri_state["last_engine_run"] = dt_util.now()
        self.pri_state["engine_run_count"] = int(self.pri_state.get("engine_run_count", 0)) + 1

        if not snapshot.valid:
            self.pri_state["last_reason"] = "EMS Onduleur : snapshot énergétique incomplet."
            return "SNAPSHOT_INVALIDE"
        if not self._pri_guard():
            self.pri_state["last_reason"] = (
                "EMS Onduleur non exécuté : "
                f"{self.pri_state.get('guard_reason', 'raison inconnue')}."
            )
            return "GARDE_PRI_ACTIVE"

        current = self._rrcr_level()
        if current < 0:
            self.pri_state.update({"ack_rrcr":"FAILED","last_reason":"EMS Onduleur : code RRCR inconnu."})
            return "RRCR_INCONNU"

        self._update_pri_pv_comparator(snapshot, current)
        policy = str(self.settings.get("network_policy", NETWORK_POLICY_COMPENSATION))
        tariff_context = self.prices()
        decision = self.inverter_core.decide(
            snapshot,
            current,
            self.settings,
            policy,
            self.energy_bus.view(),
            tariff_regime=str(tariff_context.get("regime")),
            dynamic_export_value_eur_kwh=(
                float(tariff_context["export_value"])
                if isinstance(tariff_context.get("export_value"), (int, float))
                else None
            ),
        )

        target = max(0, min(100, int(decision.target_level)))
        direction = "remontee" if target > current else "descente" if target < current else "maintien"

        self.pri_state.update({
            "current_level": current,
            "target_level": target,
            "direction": direction,
            "last_reason": decision.reason,
            "pv_limit_w": decision.pv_limit_w,
            "pv_limit_ratio_pct": decision.pv_ratio * 100.0,
            "pv_at_limit": decision.pv_at_limit,
            "more_solar_possible": decision.more_solar_possible,
            "max_solar_reached": decision.max_solar_reached,
            "score_current": decision.score_current,
            "score_target": decision.score_target,
            "house_target_level": decision.house_target_level,
            "estimated_house_w": decision.estimated_house_w,
            "target_pv_w": decision.target_pv_w,
            "predicted_import_w": decision.predicted_import_w,
            "predicted_export_w": decision.predicted_export_w,
        })
        self.energy_bus.publish_inverter_state(
            status=decision.action,
            frame_id=int(frame_id if frame_id is not None else self._frame_id),
            frame_at=dt_util.now(),
            current_level=current,
            target_level=target,
            pv_w=snapshot.pv_w,
            pv_limit_w=decision.pv_limit_w,
            pv_ratio_pct=decision.pv_ratio * 100.0,
            pv_at_limit=decision.pv_at_limit,
            more_solar_possible=decision.more_solar_possible,
            max_solar_reached=decision.max_solar_reached,
            score_current=decision.score_current,
            score_target=decision.score_target,
            house_target_level=decision.house_target_level,
            estimated_house_w=decision.estimated_house_w,
            target_pv_w=decision.target_pv_w,
            predicted_import_w=decision.predicted_import_w,
            predicted_export_w=decision.predicted_export_w,
            network_policy=policy,
            reason=decision.reason,
        )

        effective_frame_id = int(frame_id if frame_id is not None else self._frame_id)
        effective_serial = int(frame_serial if frame_serial is not None else self._frame_serial)

        if target == current:
            # Une cible physique précédente devenue obsolète est remplacée par
            # le maintien demandé par la trame la plus récente.
            if self._pri_requested is not None and int(self._pri_requested.get("level", current)) != current:
                self._queue_pri_target(
                    current, frame_id=effective_frame_id, frame_serial=effective_serial,
                    pv_before=snapshot.pv_w, reason="Nouvelle trame : maintien prioritaire.",
                )
            self.pri_state["ack_grid"] = self._classify_pri_grid(snapshot)
            return "PROCESSED"

        # La décision de CETTE trame est terminée ici. La commande physique est
        # confiée au worker RRCR et ne retarde jamais les publications suivantes.
        self.pri_state.update({"ack_rrcr": "QUEUED", "ack_inverter": "PENDING", "ack_grid": "PENDING"})
        self._queue_pri_target(
            target, frame_id=effective_frame_id, frame_serial=effective_serial,
            pv_before=snapshot.pv_w, reason=decision.reason,
        )
        return "PROCESSED"


    async def async_reset_cycle(self) -> None:
        self.reset_core("Cycle EMS réinitialisé manuellement.")
        if self._pri_task and not self._pri_task.done():
            self._pri_task.cancel()
        self.pri_state.update({"ack_rrcr": "IDLE", "ack_inverter": "IDLE", "ack_grid": "IDLE", "last_reason": "Cycle PRI réinitialisé."})
        self.async_set_updated_data(self._build_data())

    async def async_diagnostic(self) -> None:
        snap = self.snapshot()
        missing = []
        if self.config.get(CONF_GRID_SIGNED_SENSOR):
            for key, label in ((CONF_PV_SENSOR, "PV"), (CONF_GRID_SIGNED_SENSOR, "réseau signé")):
                if not self._numeric_valid(self.config.get(key)):
                    missing.append(label)
        else:
            for key, label in ((CONF_PV_SENSOR, "PV"), (CONF_HOUSE_SENSOR, "maison legacy"), (CONF_GRID_EXPORT_SENSOR, "export legacy"), (CONF_GRID_IMPORT_SENSOR, "import legacy")):
                if not self._numeric_valid(self.config.get(key)):
                    missing.append(label)
        legacy_on = [eid for eid in KNOWN_LEGACY_AUTOMATIONS if self._is_on(eid)]
        parts = []
        if missing:
            parts.append("Capteurs invalides : " + ", ".join(missing))
        else:
            parts.append("Sources énergétiques valides")
        if legacy_on:
            parts.append("automatisations legacy actives : " + ", ".join(legacy_on))
        parts.append(f"réseau={snap.grid_net_w:.0f} W")
        parts.append(f"PRI={self._rrcr_level()} %")
        self.core_state["last_reason"] = "Diagnostic FoxCat : " + " | ".join(parts)
        self.async_set_updated_data(self._build_data(snap))

    async def async_analyze_solar(self, analysis_type: str = "RÉÉVALUATION MANUELLE") -> None:
        if not bool(self.settings.get("solar_advisor_enabled")):
            return
        ai_entity = self.config.get(CONF_AI_TASK)
        if ai_entity and self.hass.services.has_service("ai_task", "generate_data"):
            try:
                prompt = self._solar_prompt(analysis_type)
                structure = {
                    "decision": {"selector": {"select": {"options": ["OUI", "NON"]}}},
                    "debut": {"selector": {"text": {}}},
                    "fin": {"selector": {"text": {}}},
                    "confiance": {"selector": {"number": {"min": 0, "max": 100, "step": 1}}},
                    "potentiel": {"selector": {"select": {"options": ["Aucun", "Faible", "Moyen", "Bon", "Fort"]}}},
                    "tendance": {"selector": {"select": {"options": ["NOUVELLE", "CONFIRMÉE", "DÉCALÉE", "DÉGRADÉE", "ANNULÉE"]}}},
                    "justification": {"selector": {"text": {}}},
                }
                response = await self.hass.services.async_call(
                    "ai_task",
                    "generate_data",
                    {"entity_id": ai_entity, "task_name": f"FoxCat IA - Prévision solaire - {analysis_type}", "instructions": prompt, "structure": structure},
                    blocking=True,
                    return_response=True,
                )
                payload = response.get("data", response) if isinstance(response, dict) else {}
                decision = str(payload.get("decision", "NON"))
                potential = str(payload.get("potentiel", "Aucun"))
                trend = str(payload.get("tendance", "NOUVELLE"))
                if decision in {"OUI", "NON"} and potential in {"Aucun", "Faible", "Moyen", "Bon", "Fort"} and trend in {"NOUVELLE", "CONFIRMÉE", "DÉCALÉE", "DÉGRADÉE", "ANNULÉE"}:
                    self.solar_forecast = SolarForecast(
                        available=decision == "OUI",
                        start=str(payload.get("debut", "--:--")),
                        end=str(payload.get("fin", "--:--")),
                        confidence=max(0.0, min(100.0, float(payload.get("confiance", 0)))),
                        potential=potential,
                        trend=trend,
                        reason=str(payload.get("justification", ""))[:255],
                        raw=f"{decision} | {payload.get('debut','--:--')}-{payload.get('fin','--:--')} | {payload.get('confiance',0)}% | {potential} | {trend}",
                    )
                    await self._async_save()
                    self.async_set_updated_data(self._build_data())
                    return
            except Exception as err:  # pragma: no cover
                _LOGGER.warning("FoxCat IA : AI Task indisponible, fallback déterministe utilisé: %s", err)
        self._deterministic_solar_fallback(analysis_type)
        await self._async_save()
        self.async_set_updated_data(self._build_data())

    def _deterministic_solar_fallback(self, analysis_type: str) -> None:
        values = [
            self._optional_float_state(self.config.get(CONF_FORECAST_NOW)),
            self._optional_float_state(self.config.get(CONF_FORECAST_1H)),
            self._optional_float_state(self.config.get(CONF_FORECAST_NEXT_HOUR)),
        ]
        numeric = [v for v in values if v is not None]
        power = max(numeric) if numeric else 0.0
        min_w = float(self.settings["solar_threshold_min_w"])
        possible = float(self.settings["solar_threshold_possible_w"])
        good = float(self.settings["solar_threshold_good_w"])
        strong = float(self.settings["solar_threshold_strong_w"])
        if power >= strong:
            potential, confidence = "Fort", 85.0
        elif power >= good:
            potential, confidence = "Bon", 78.0
        elif power >= possible:
            potential, confidence = "Moyen", 70.0
        elif power >= min_w:
            potential, confidence = "Faible", 55.0
        else:
            potential, confidence = "Aucun", 30.0
        available = potential in {"Moyen", "Bon", "Fort"} and confidence >= float(self.settings["solar_confidence_min_percent"])
        peak_state = self.hass.states.get(self.config.get(CONF_FORECAST_PEAK_TODAY)) if self.config.get(CONF_FORECAST_PEAK_TODAY) else None
        peak = peak_state.state if peak_state and peak_state.state not in {"unknown", "unavailable"} else "--:--"
        self.solar_forecast = SolarForecast(
            available=available,
            start=peak if available else "--:--",
            end="--:--",
            confidence=confidence,
            potential=potential,
            trend="NOUVELLE",
            reason=f"Fallback local {analysis_type.lower()} : potentiel {potential.lower()}.",
            raw=f"{'OUI' if available else 'NON'} | {peak}---:-- | {confidence:.0f}% | {potential} | NOUVELLE",
        )

    def _solar_prompt(self, analysis_type: str) -> str:
        snap = self.snapshot()
        def st(key: str) -> str:
            eid = self.config.get(key)
            state = self.hass.states.get(eid) if eid else None
            return state.state if state else "indisponible"
        return f"""Tu es le module IA prédictif solaire de FoxCat Energy. Tu es uniquement consultatif : ne commande aucun équipement et ne modifies aucune consigne. L’EMS FoxCat reste seul décisionnaire.

Analyse: {analysis_type}
Date/heure: {dt_util.now().strftime('%d/%m/%Y %H:%M')}
PV réel: {snap.pv_w:.0f} W
Maison réelle: {snap.house_w:.0f} W
Export compteur: {snap.export_w:.0f} W
Import compteur: {snap.import_w:.0f} W
Température boiler: {snap.boiler_temp_c:.1f} °C
Confort minimal: {float(self.settings['boiler_temp_normal_c']):.0f} °C
HC: 22:00-07:00 et 11:00-17:00. HP: 07:00-11:00 et 17:00-22:00.
Forecast maintenant: {st(CONF_FORECAST_NOW)}
Cette heure: {st(CONF_FORECAST_THIS_HOUR)}
Heure suivante: {st(CONF_FORECAST_NEXT_HOUR)}
Restant aujourd'hui: {st(CONF_FORECAST_REMAINING_TODAY)}
Pic aujourd'hui: {st(CONF_FORECAST_PEAK_TODAY)}
Demain: {st(CONF_FORECAST_TOMORROW)}
Pic demain: {st(CONF_FORECAST_PEAK_TOMORROW)}

Cherche une fenêtre solaire exploitable avant la prochaine échéance énergétique pertinente. Une faible production actuelle n'annule pas une fenêtre future. Ne confonds pas production PV et surplus disponible. Si plusieurs fenêtres existent, choisis une seule fenêtre, stable et durable. À 15:00, privilégie la garantie thermique avant 17:00. Fournis uniquement les champs structurés demandés. Justification: maximum 12 mots."""

    def _legacy_conflict(self) -> bool:
        return any(self._is_on(eid) for eid in KNOWN_LEGACY_AUTOMATIONS)

    def _build_data(self, snapshot: EnergySnapshot | None = None) -> dict[str, Any]:
        snap = snapshot or self.snapshot()
        rrcr_code = self._rrcr_code() if all(self.config.get(k) for k in (CONF_PRI_L1, CONF_PRI_L2, CONF_PRI_L3, CONF_PRI_L4)) else "----"
        level = RRCR_CODE_TO_LEVEL.get(rrcr_code, -1)
        self.pri_state["current_level"] = level
        self.pri_state["code"] = rrcr_code
        prices = self.prices()
        economic = self._economic_view(snap, prices=prices)
        financial = self._financial_status_view({"economic": economic})
        return {
            "snapshot": snap,
            "settings": dict(self.settings),
            "versions": {
                "engine": VERSION,
                "dashboard": dashboard_status(self.hass).get("active_version") or "Non installé",
            },
            "migration": {"model_version": self.settings.get("configuration_model_version"), "notes": getattr(self, "_migration_notes", [])},
            "core": dict(self.core_state),
            "pri": dict(self.pri_state),
            "energy_bus": self.energy_bus.view(),
            "metronome": dict(self.metronome_state),
            "machine_cycles": self.machine_cycle_manager.snapshot(dt_util.now()),
            "machine_learning": self.machine_learning.view(),
            "solar": self.solar_forecast,
            "prices": prices,
            "economic": economic,
            "boiler_thermal": self._boiler_thermal_view(snap),
            "status_summary": {
                "mode": self.settings.get("mode", MODE_ECO),
                "network_policy": self.settings.get("network_policy", NETWORK_POLICY_COMPENSATION),
                "financial_status": financial["status"],
                "financial_detail": financial["detail"],
                "financial_code": financial["code"],
                "economic_decision": economic.get("decision", {}).get("label", "Indisponible"),
            },
            "accounting": self.accounting.view(),
            "legacy_conflict": self._legacy_conflict(),
            "load_shed": dict(self.load_shed_state),
            "machine_guard": {
                "active": snap.machine_active,
                "boiler_surplus_available_w": boiler_surplus_before_load_w(snap),
                "boiler_allowed": protected_cycle_boiler_allowed(snap, self.settings),
            },
            "machines": self.machine_states(economic),
            "machine_window": {machine.machine_id: machine_allowed(machine, dt_util.now()) for machine in self.machines},
        }
