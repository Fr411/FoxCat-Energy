"""Règles pures du coordinateur, extraites pour être testées sans Home Assistant.

* A-07 : lecture tolérante d'un attribut numérique (``None``, texte, absent).
* A-13 : expiration d'une commande forcée du boiler (FORCE_ON / FORCE_OFF).
* A-23 : action sur la prise d'une machine dont la gestion automatique est coupée.
* A-27 : plages HP/HC écrites à partir des réglages, pas en dur.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

SOCKET_ON = "turn_on"
SOCKET_OFF = "turn_off"

DEFAULT_OVERRIDE_MAX_H = 6.0


# FONCTION : attr_float — Lit un attribut numérique sans jamais lever d'exception (A-07)
def attr_float(value: Any, default: float = 0.0) -> float:
    """``None``, texte non numérique ou NaN donnent ``default`` (A-07 : ``float(None)`` plantait)."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if result == result else default


# FONCTION : override_expired — Une commande forcée du boiler a-t-elle dépassé sa durée ? (A-13)
def override_expired(since: datetime | None, now: datetime, max_hours: Any = DEFAULT_OVERRIDE_MAX_H) -> bool:
    """Vrai quand FORCE_ON / FORCE_OFF dure depuis plus de ``max_hours`` (0 ou moins = jamais)."""
    limit = attr_float(max_hours, DEFAULT_OVERRIDE_MAX_H)
    if limit <= 0:
        return False
    if since is None:
        # Origine inconnue (état restauré sans date) : on repart de maintenant plutôt que d'expirer d'office.
        return False
    return now - since >= timedelta(hours=limit)


# FONCTION : machine_socket_action — Commande à envoyer à la prise d'une machine (A-23)
def machine_socket_action(
    *,
    management: bool,
    cycle_active: bool,
    keep_running: bool,
    backup_on: bool,
    high_load_block: bool,
    allowed: bool,
    tariff_ok: bool,
) -> str | None:
    """Retourne ``turn_on``, ``turn_off`` ou ``None`` (ne rien envoyer).

    Gestion automatique coupée : FoxCat rend la main et n'envoie rien, sauf pour
    couper une machine délestable pendant une urgence du disjoncteur (sécurité).
    """
    if not management and not high_load_block:
        return None
    should_on = cycle_active or keep_running or backup_on or (
        management and allowed and tariff_ok and not high_load_block
    )
    return SOCKET_ON if should_on else SOCKET_OFF


def socket_should_be_on(*, management: bool, cycle_active: bool, allowed: bool, allow_start_now: bool) -> bool:
    """Prise attendue allumée d'après le plan : cycle en cours, ou gestion active + plage ouverte + départ autorisé."""
    return bool(cycle_active or (management and allowed and allow_start_now))


def socket_sync_status(expected_on: bool, state: str | None) -> str:
    """``OK`` si la prise est dans l'état attendu, ``ECART`` sinon, ``INDISPONIBLE`` si on ne la lit pas."""
    if state in (None, "unavailable", "unknown"):
        return "INDISPONIBLE"
    return "OK" if (state == "on") == bool(expected_on) else "ECART"


def socket_sync_signature(machine_states: list[dict[str, Any]]) -> dict[str, tuple[bool, bool, bool]]:
    """Ce qui doit déclencher une réconciliation des prises : départ autorisé, plage ouverte, gestion active."""
    return {
        str(m["id"]): (bool(m.get("tariff_start_favorable")), bool(m.get("window_open")), bool(m.get("automatic")))
        for m in machine_states
        if m.get("switch")
    }


def _minutes(value: Any, default: str) -> int:
    raw = str(value or default).split(":")
    try:
        return int(raw[0]) * 60 + int(raw[1] if len(raw) > 1 else 0)
    except (ValueError, IndexError):
        return _minutes(default, "00:00") if default != "00:00" else 0


def _hhmm(minutes: int) -> str:
    minutes %= 1440
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


# FONCTION : hp_hc_windows_text — « HC : … HP : … » à partir des plages configurées (A-27)
def hp_hc_windows_text(settings: dict[str, Any]) -> str:
    """HP = les deux plages configurées ; HC = le complément sur 24 h."""
    windows = sorted(
        {
            (_minutes(settings.get("tariff_hp_start_1"), "07:00"), _minutes(settings.get("tariff_hp_end_1"), "11:00")),
            (_minutes(settings.get("tariff_hp_start_2"), "17:00"), _minutes(settings.get("tariff_hp_end_2"), "22:00")),
        }
    )
    windows = [(s, e) for s, e in windows if e > s]
    hp = " et ".join(f"{_hhmm(s)}-{_hhmm(e)}" for s, e in windows) or "aucune"
    hc_parts: list[str] = []
    cursor = 0
    for s, e in windows:
        if s > cursor:
            hc_parts.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < 1440:
        hc_parts.append((cursor, 1440))
    # La dernière plage et la première se rejoignent à minuit : « 22:00-07:00 ».
    if len(hc_parts) > 1 and hc_parts[0][0] == 0 and hc_parts[-1][1] == 1440:
        first, last = hc_parts[0], hc_parts[-1]
        hc_parts = hc_parts[1:-1] + [(last[0], first[1])]
    hc = " et ".join(f"{_hhmm(s)}-{_hhmm(e)}" for s, e in hc_parts) or "aucune"
    return f"HC: {hc}. HP: {hp}."
