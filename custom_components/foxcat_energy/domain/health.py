"""Santé de FoxCat : détection des pannes majeures et critiques, et alertes.

``evaluate`` transforme l'état du système en liste d'alertes (code, gravité, texte).
``AlertTracker`` les temporise (une alerte n'apparaît qu'après un délai, et ne disparaît
qu'après un retour stable) pour éviter les notifications parasites.

Module pur : aucune dépendance Home Assistant.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping

CRITICAL = "CRITIQUE"
MAJOR = "MAJEUR"
SEVERITY_RANK = {CRITICAL: 2, MAJOR: 1}

RAISE_AFTER_S = 120.0       # délai avant d'annoncer une alerte
CLEAR_AFTER_S = 60.0        # retour stable avant de la lever


@dataclass(frozen=True)
class HealthInputs:
    """Ce que le coordinateur sait de l'installation (valeurs simples, sans entité Home Assistant)."""

    regulation_active: bool = True
    mode: str = "Éco"
    snapshot_valid: bool = True
    missing_essential_sensors: tuple[str, ...] = ()
    metronome_status: str = "SYNCHRONISE"
    boiler_configured: bool = False
    boiler_temp_ok: bool = True
    boiler_safety_temp_ok: bool = True
    boiler_safety_temp_c: float | None = None
    boiler_safety_limit_c: float = 68.0
    pri_enabled: bool = False
    pri_relays_readable: bool = True
    actuator_status: str = "IDLE"
    actuator_error: str = ""
    unavailable_machines: tuple[str, ...] = ()
    price_feed_state: str = "LOCAL"
    internet_online: bool = True
    backup_active: bool = False
    load_shed_active: bool = False
    legacy_conflict: bool = False
    coordinator_update_ok: bool = True
    missing_configured_entities: tuple[str, ...] = ()


@dataclass(frozen=True)
class Alert:
    code: str
    severity: str
    title: str
    detail: str
    delay_s: float = RAISE_AFTER_S   # 0 = immédiat


def _join(items: Iterable[str]) -> str:
    return ", ".join(items)


def evaluate(h: HealthInputs) -> list[Alert]:
    """Liste des pannes constatées à cet instant (avant temporisation)."""
    alerts: list[Alert] = []
    manual = str(h.mode) == "Manuel"

    # ---- Critiques : FoxCat aveugle, ou sécurité du matériel compromise ----
    if h.regulation_active and not manual and (not h.snapshot_valid or h.metronome_status == "PERDU"):
        why = f"capteurs indisponibles : {_join(h.missing_essential_sensors)}" if h.missing_essential_sensors else "plus de publication de puissance réseau"
        alerts.append(Alert(
            "EMS_AVEUGLE", CRITICAL, "FoxCat ne reçoit plus les mesures",
            f"La régulation est gelée par sécurité ({why}). Vérifiez le compteur et le capteur photovoltaïque.",
        ))
    if h.boiler_configured and h.boiler_safety_temp_c is not None and h.boiler_safety_temp_c >= h.boiler_safety_limit_c:
        alerts.append(Alert(
            "BOILER_SURCHAUFFE", CRITICAL, "Boiler en surchauffe",
            f"Température de sécurité {h.boiler_safety_temp_c:.1f} °C, limite {h.boiler_safety_limit_c:.0f} °C. Coupez l'alimentation du boiler.",
            delay_s=0.0,
        ))
    if h.boiler_configured and h.regulation_active and not manual and not h.boiler_safety_temp_ok:
        alerts.append(Alert(
            "BOILER_SONDE_SECURITE_HS", CRITICAL, "Sonde de sécurité du boiler indisponible",
            "La protection contre la surchauffe est aveugle. FoxCat interdit toute chauffe tant que la sonde ne répond pas. Rétablissez la sonde.",
        ))
    if h.boiler_configured and h.regulation_active and not manual and not h.boiler_temp_ok and h.boiler_safety_temp_ok:
        alerts.append(Alert(
            "BOILER_SONDE_HS", CRITICAL, "Sonde de température du boiler indisponible",
            "FoxCat interdit toute chauffe tant que la sonde ne répond pas, et la reprend 60 secondes après son retour. Rétablissez la sonde.",
        ))
    if h.pri_enabled and h.regulation_active and not manual and not h.pri_relays_readable:
        alerts.append(Alert(
            "PRI_ILLISIBLE", CRITICAL, "Relais de l'onduleur illisibles",
            "FoxCat ne connaît plus le niveau de limitation de l'onduleur (relais RRCR indisponibles).",
        ))
    if h.actuator_status in {"FAILED", "TIMEOUT"}:
        alerts.append(Alert(
            "ACTIONNEUR_ECHEC", CRITICAL, "Une commande n'a pas été exécutée",
            f"Statut {h.actuator_status}" + (f" : {h.actuator_error}" if h.actuator_error else "") + ". Vérifiez l'entité commandée.",
        ))

    # ---- Majeures : service dégradé ----
    if h.metronome_status == "FALLBACK":
        alerts.append(Alert(
            "METRONOME_SECOURS", MAJOR, "Capteur de puissance principal silencieux",
            "FoxCat fonctionne sur le capteur de secours, moins fréquent. Vérifiez le capteur principal.",
        ))
    if h.price_feed_state == "DEGRADE":
        alerts.append(Alert(
            "PRIX_INDISPONIBLES", MAJOR, "Prix de bourse indisponibles",
            "Le tampon de prix est épuisé : décisions économiques suspendues, coûts comptés à 0 € d'achat.",
        ))
    if not h.internet_online:
        alerts.append(Alert(
            "INTERNET_COUPE", MAJOR, "Internet coupé",
            "Le mode Backup est actif : machines alimentées, boiler coupé." if h.backup_active
            else "Internet est coupé ; le mode Backup n'est pas actif (désactivé, mode Manuel ou régulation coupée).",
        ))
    if h.unavailable_machines:
        alerts.append(Alert(
            "MACHINE_INDISPONIBLE", MAJOR, "Prise de machine indisponible",
            f"FoxCat ne peut plus piloter : {_join(h.unavailable_machines)}.",
        ))
    if h.load_shed_active:
        alerts.append(Alert(
            "DELESTAGE_ACTIF", MAJOR, "Délestage du disjoncteur en cours",
            "La consommation approche la limite du disjoncteur : des charges sont coupées.",
            delay_s=0.0,
        ))
    if h.legacy_conflict:
        alerts.append(Alert(
            "CONFLIT_AUTOMATISATION", MAJOR, "Une ancienne automatisation pilote les mêmes équipements",
            "Désactivez l'automatisation FoxCat historique : les commandes se contrarient.",
        ))
    if not h.coordinator_update_ok:
        alerts.append(Alert(
            "FOXCAT_EN_ERREUR", MAJOR, "Le calcul FoxCat a échoué",
            "La dernière mise à jour a levé une erreur : consultez le journal Home Assistant.",
        ))
    if h.missing_configured_entities:
        alerts.append(Alert(
            "ENTITE_INTROUVABLE", MAJOR, "Entité configurée introuvable",
            f"Home Assistant ne connaît plus : {_join(h.missing_configured_entities)}.",
        ))
    return alerts


@dataclass
class _Track:
    first_seen: datetime
    last_seen: datetime
    visible_since: datetime | None = None
    alert: Alert | None = None


@dataclass
class AlertTracker:
    """Temporise les alertes : annonce après leur délai, lève après un retour stable."""

    clear_after_s: float = CLEAR_AFTER_S
    _tracks: dict[str, _Track] = field(default_factory=dict)

    def update(self, alerts: Iterable[Alert], now: datetime) -> tuple[list[dict[str, Any]], set[str], set[str]]:
        """Renvoie (alertes visibles, codes nouvellement annoncés, codes levés)."""
        current = {alert.code: alert for alert in alerts}
        raised: set[str] = set()
        cleared: set[str] = set()
        for code, alert in current.items():
            track = self._tracks.get(code)
            if track is None:
                track = self._tracks[code] = _Track(first_seen=now, last_seen=now)
            track.last_seen = now
            track.alert = alert
            if track.visible_since is None and (now - track.first_seen).total_seconds() >= alert.delay_s:
                track.visible_since = now
                raised.add(code)
        for code in list(self._tracks):
            if code in current:
                continue
            track = self._tracks[code]
            if track.visible_since is None:
                del self._tracks[code]          # jamais annoncée : on oublie sans bruit
            elif (now - track.last_seen).total_seconds() >= self.clear_after_s:
                cleared.add(code)
                del self._tracks[code]
        visible = [
            {
                "code": code,
                "severite": track.alert.severity,
                "titre": track.alert.title,
                "detail": track.alert.detail,
                "depuis": track.visible_since.isoformat(),
            }
            for code, track in self._tracks.items()
            if track.visible_since is not None and track.alert is not None
        ]
        visible.sort(key=lambda row: (-SEVERITY_RANK.get(row["severite"], 0), row["depuis"]))
        return visible, raised, cleared


def overall_status(visible: Iterable[Mapping[str, Any]]) -> str:
    """OK, MAJEUR ou CRITIQUE selon l'alerte la plus grave."""
    rank = max((SEVERITY_RANK.get(str(row.get("severite")), 0) for row in visible), default=0)
    return {2: CRITICAL, 1: MAJOR}.get(rank, "OK")
