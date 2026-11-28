"""Mode de fonctionnement d'une machine : Automatique, Manuel ou Arrêt.

- **Automatique** : FoxCat (planificateur) commande la prise.
- **Manuel** : FoxCat ne commande plus la prise, l'utilisateur l'allume et l'éteint depuis Home Assistant.
  Revient seul en Automatique après 24 h.
- **Arrêt** : la prise est coupée et aucun départ n'est autorisé (un cycle en cours n'est jamais interrompu).

Le réglage historique « gestion automatique » (booléen) reste la source lue par le moteur : il vaut ``True``
seulement en mode Automatique.
"""
from __future__ import annotations

from datetime import datetime, timedelta

MACHINE_MODE_AUTO = "Automatique"
MACHINE_MODE_MANUAL = "Manuel"
MACHINE_MODE_OFF = "Arrêt"
MACHINE_MODES = [MACHINE_MODE_AUTO, MACHINE_MODE_MANUAL, MACHINE_MODE_OFF]
MANUAL_TIMEOUT = timedelta(hours=24)


def mode_key(machine_id: str) -> str:
    return f"machine_{machine_id}_mode"


def manual_since_key(machine_id: str) -> str:
    return f"machine_{machine_id}_manual_since"


def reconcile_mode(mode: object, enabled: bool) -> str:
    """Mode cohérent avec le booléen historique (modifié par un profil, un ancien interrupteur ou un service).

    Booléen vrai : Automatique. Booléen faux : on garde Manuel/Arrêt s'il est déjà choisi, sinon Manuel.
    """
    if enabled:
        return MACHINE_MODE_AUTO
    return str(mode) if mode in (MACHINE_MODE_MANUAL, MACHINE_MODE_OFF) else MACHINE_MODE_MANUAL


def manual_expired(mode: str, since_iso: object, now: datetime) -> bool:
    """Vrai si le mode Manuel dure depuis 24 h ou plus (ou si son début est inconnu ou illisible)."""
    if mode != MACHINE_MODE_MANUAL:
        return False
    try:
        since = datetime.fromisoformat(str(since_iso))
    except (TypeError, ValueError):
        return True
    if since.tzinfo is None and now.tzinfo is not None:
        since = since.replace(tzinfo=now.tzinfo)
    return now - since >= MANUAL_TIMEOUT


def manual_until(since_iso: object) -> str | None:
    """Heure (ISO) du retour automatique, ou ``None`` si le début est inconnu."""
    try:
        return (datetime.fromisoformat(str(since_iso)) + MANUAL_TIMEOUT).isoformat()
    except (TypeError, ValueError):
        return None
