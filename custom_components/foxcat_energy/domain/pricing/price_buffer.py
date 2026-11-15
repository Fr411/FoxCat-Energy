"""Tampon local des prix de bourse : fonctionnement sans Internet.

Les prix du lendemain sont publiés vers 14 h. Une fois reçus, FoxCat les garde
(persistés sur disque par le coordinateur) : si la connexion tombe, le plan de
route des prochaines 24 à 36 h reste calculable localement.

Ce module est pur (aucune dépendance Home Assistant) : il lit le tampon sous la
forme ``{horodatage ISO: prix}`` déjà stocké par le coordinateur.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Mapping

# Une tranche reste « en cours » au plus 65 min après son début (heure + marge).
SLOT_MAX_AGE = timedelta(minutes=65)
# On garde un peu de passé pour connaître le prix de la tranche en cours.
BUFFER_PAST = timedelta(hours=3)
DEFAULT_STEP = timedelta(hours=1)

FEED_LIVE = "EN_LIGNE"
FEED_BUFFER = "TAMPON"
FEED_DEGRADED = "DEGRADE"
FEED_LOCAL = "LOCAL"

FEED_LABELS = {
    FEED_LIVE: "Prix reçus en direct",
    FEED_BUFFER: "Hors ligne : prix lus dans le tampon local",
    FEED_DEGRADED: "Hors ligne : tampon épuisé, repli autoconsommation et confort",
    FEED_LOCAL: "Tarif local : aucune connexion nécessaire",
}


def _parse(timestamp: Any, reference: datetime) -> datetime | None:
    try:
        at = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if at.tzinfo is None and reference.tzinfo is not None:
        at = at.replace(tzinfo=reference.tzinfo)
    return at


def _series(store: Mapping[str, Any] | None, now: datetime) -> list[tuple[datetime, float]]:
    if not isinstance(store, Mapping):
        return []
    rows: list[tuple[datetime, float]] = []
    for timestamp, price in store.items():
        at = _parse(timestamp, now)
        if at is None:
            continue
        try:
            rows.append((at, float(price)))
        except (TypeError, ValueError):
            continue
    rows.sort(key=lambda row: row[0])
    return rows


def current_price(store: Mapping[str, Any] | None, now: datetime) -> float | None:
    """Prix de la tranche en cours, ou None si le tampon ne la couvre pas."""
    candidate: tuple[datetime, float] | None = None
    for at, price in _series(store, now):
        if at <= now:
            candidate = (at, price)
        else:
            break
    if candidate is None or now - candidate[0] > SLOT_MAX_AGE:
        return None
    return candidate[1]


def next_price(store: Mapping[str, Any] | None, now: datetime) -> float | None:
    """Prix de la première tranche strictement future."""
    for at, price in _series(store, now):
        if at > now:
            return price
    return None


def covered_until(store: Mapping[str, Any] | None, now: datetime) -> datetime | None:
    """Fin de la dernière tranche connue (dernier point + pas de la série)."""
    rows = _series(store, now)
    if not rows:
        return None
    step = DEFAULT_STEP
    if len(rows) >= 2:
        gap = rows[-1][0] - rows[-2][0]
        if timedelta(minutes=1) <= gap <= timedelta(hours=2):
            step = gap
    return rows[-1][0] + step


def prune(store: dict[str, Any], now: datetime, horizon_hours: int) -> bool:
    """Retire les points trop anciens ou trop lointains. True si modifié."""
    changed = False
    limit = now + timedelta(hours=horizon_hours)
    for key in list(store):
        at = _parse(key, now)
        if at is None or at < now - BUFFER_PAST or at > limit:
            del store[key]
            changed = True
    return changed


def feed_status(
    *, uses_market_prices: bool, live_ok: bool, store: Mapping[str, Any] | None, now: datetime
) -> dict[str, Any]:
    """État du flux de prix : en ligne, tampon local ou repli."""
    if not uses_market_prices:
        return {"state": FEED_LOCAL, "label": FEED_LABELS[FEED_LOCAL], "buffer_until": None, "hours_left": None}
    end = covered_until(store, now)
    hours_left = round((end - now).total_seconds() / 3600.0, 1) if end and end > now else 0.0
    if live_ok:
        state = FEED_LIVE
    elif end is not None and now < end:
        state = FEED_BUFFER
    else:
        state = FEED_DEGRADED
    return {
        "state": state,
        "label": FEED_LABELS[state],
        "buffer_until": end.isoformat() if end else None,
        "hours_left": hours_left,
    }
