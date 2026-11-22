"""Retour physique du pilotage onduleur (ACK LOGO) et disponibilité de la commande.

Le code RRCR commandé par FoxCat (switches L4 L3 L2 L1) n'est confirmé
« physiquement » que si le contrôleur (ex. Siemens LOGO) renvoie l'état réel
de ses relais. Ce module compare ce retour au code attendu. Il ne dépend pas de
Home Assistant et reste donc testable seul.
"""
from __future__ import annotations

from typing import Iterable

ACK_LOGO_NOT_CONFIGURED = "NON_CONFIGURE"
ACK_LOGO_ABSENT = "ABSENT"
ACK_LOGO_OK = "OK"
ACK_LOGO_FAILED = "FAILED"

AVAILABILITY_NOT_CONFIGURED = "NON_CONFIGURE"
AVAILABILITY_OK = "DISPONIBLE"
AVAILABILITY_DEGRADED = "DEGRADE"
AVAILABILITY_DOWN = "INDISPONIBLE"

UNREADABLE_CODE = "????"


# FONCTION : feedback_code — Code RRCR relu sur les retours (L4 L3 L2 L1)
def feedback_code(states: Iterable[str | None] | None) -> str | None:
    """Code relu sur les retours, dans l'ordre L4 L3 L2 L1.

    ``None`` : retours non configurés (au moins une entité absente de la config).
    ``"????"`` : un retour est configuré mais illisible (indisponible, inconnu…).
    """
    if states is None:
        return None
    bits: list[str] = []
    for state in states:
        if state == "on":
            bits.append("1")
        elif state == "off":
            bits.append("0")
        else:
            return UNREADABLE_CODE
    return "".join(bits)


# FONCTION : classify_ack_logo — Compare le retour physique au code commandé
def classify_ack_logo(expected_code: str | None, fb_code: str | None) -> str:
    """ACK LOGO : OK si le retour correspond, FAILED s'il diffère, ABSENT si illisible."""
    if fb_code is None:
        return ACK_LOGO_NOT_CONFIGURED
    if fb_code == UNREADABLE_CODE:
        return ACK_LOGO_ABSENT
    if expected_code is None or expected_code == UNREADABLE_CODE:
        return ACK_LOGO_ABSENT
    return ACK_LOGO_OK if fb_code == expected_code else ACK_LOGO_FAILED


# FONCTION : command_blocked — La garde PRI interdit-elle toute commande ?
def command_blocked(availability: str | None) -> bool:
    """Vrai quand le retour est configuré mais illisible (contrôleur ou liaison coupés).

    Une commande envoyée dans ce cas ne peut être ni confirmée ni garantie : la garde
    PRI suspend les décisions et les envois. ``DEGRADE`` ne bloque pas (écart signalé).
    """
    return availability == AVAILABILITY_DOWN


# FONCTION : command_availability — Disponibilité de la chaîne de commande
def command_availability(
    commanded_code: str | None, fb_code: str | None, logo_online: str | None = None
) -> str:
    """Disponibilité de la chaîne de commande onduleur.

    ``logo_online`` : état de l'entité « LOGO en ligne » (``None`` si non configurée ;
    tout état autre que ``on``, y compris indisponible, vaut contrôleur hors ligne).

    - ``NON_CONFIGURE`` : ni retour ni « LOGO en ligne » configurés (comportement historique).
    - ``INDISPONIBLE`` : « LOGO en ligne » différent de ``on``, ou retour configuré mais illisible.
    - ``DEGRADE`` : retour lisible mais différent de l'état commandé côté Home Assistant.
    - ``DISPONIBLE`` : retour lisible et identique à l'état commandé.
    """
    if logo_online is not None and logo_online != "on":
        return AVAILABILITY_DOWN
    if fb_code is None:
        return AVAILABILITY_NOT_CONFIGURED if logo_online is None else AVAILABILITY_OK
    if fb_code == UNREADABLE_CODE:
        return AVAILABILITY_DOWN
    if commanded_code is None or commanded_code == UNREADABLE_CODE:
        return AVAILABILITY_DEGRADED
    return AVAILABILITY_OK if fb_code == commanded_code else AVAILABILITY_DEGRADED
