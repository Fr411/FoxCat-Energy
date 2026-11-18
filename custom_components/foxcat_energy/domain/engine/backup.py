"""Mode Backup : coupure Internet.

Quand Internet tombe, FoxCat lâche les freins économiques : les machines restent alimentées,
le boiler est coupé, l'onduleur n'est plus bridé. Les sécurités restent actives
(protection du disjoncteur). L'état des prises est mémorisé avant
la coupure et rétabli au retour de la connexion, sans jamais couper un cycle en cours.

Ce module est pur (aucune dépendance Home Assistant).
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping

from ...const import BOILER_NONE, BOILER_STOP
from .models import BoilerIntent, EnergySnapshot

# Résolveurs publics : on teste seulement qu'une connexion TCP s'ouvre, rien n'est envoyé.
PROBE_HOSTS: tuple[tuple[str, int], ...] = (("1.1.1.1", 443), ("8.8.8.8", 443), ("9.9.9.9", 443))
PROBE_TIMEOUT_S = 3.0
# Retour en ligne : la connexion doit tenir ce temps avant de rendre la main.
RECOVER_AFTER_S = 60.0

TRANSITION_OFFLINE = "HORS_LIGNE"
TRANSITION_ONLINE = "EN_LIGNE"


async def probe_internet(
    hosts: Iterable[tuple[str, int]] = PROBE_HOSTS, timeout: float = PROBE_TIMEOUT_S
) -> bool:
    """Vrai si au moins une connexion TCP s'ouvre."""

    async def attempt(host: str, port: int) -> bool:
        try:
            _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
        except (OSError, asyncio.TimeoutError):
            return False
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:  # pragma: no cover - fermeture best effort
            pass
        return True

    results = await asyncio.gather(*(attempt(host, port) for host, port in hosts))
    return any(results)


@dataclass
class ConnectivityMonitor:
    """Filtre anti-rebond : hors ligne après ``offline_after_s`` d'échecs continus, en ligne après ``recover_after_s`` de succès continus."""

    offline_after_s: float = 120.0
    recover_after_s: float = RECOVER_AFTER_S
    online: bool = True
    since: datetime | None = None
    _failing_since: datetime | None = field(default=None, repr=False)
    _recovering_since: datetime | None = field(default=None, repr=False)

    def observe(self, ok: bool, now: datetime) -> str | None:
        """Enregistre un sondage ; renvoie une transition ou None."""
        if ok:
            self._failing_since = None
            if self.online:
                self._recovering_since = None
                return None
            if self._recovering_since is None:
                self._recovering_since = now
            if (now - self._recovering_since).total_seconds() >= self.recover_after_s:
                self.online, self.since, self._recovering_since = True, now, None
                return TRANSITION_ONLINE
            return None
        self._recovering_since = None
        if not self.online:
            return None
        if self._failing_since is None:
            self._failing_since = now
        if (now - self._failing_since).total_seconds() >= self.offline_after_s:
            self.online, self.since, self._failing_since = False, now, None
            return TRANSITION_OFFLINE
        return None

    def dump(self) -> dict[str, Any]:
        return {"online": self.online, "since": self.since.isoformat() if self.since else None}

    def restore(self, data: Any) -> None:
        if not isinstance(data, Mapping):
            return
        self.online = bool(data.get("online", True))
        since = data.get("since")
        try:
            self.since = datetime.fromisoformat(since) if since else None
        except (TypeError, ValueError):
            self.since = None


def backup_boiler_intent(snapshot: EnergySnapshot, settings: Mapping[str, Any] | None = None) -> BoilerIntent:
    """En Backup, le boiler est coupé : aucune chauffe tant qu'Internet est absent."""
    if snapshot.boiler_on:
        return BoilerIntent(BOILER_STOP, "Backup (Internet coupé) : boiler coupé.", "BACKUP_BOILER_COUPE")
    return BoilerIntent(BOILER_NONE, "Backup (Internet coupé) : boiler maintenu coupé.", "BACKUP_BOILER_COUPE")


def capture_socket_states(states: Mapping[str, str | None]) -> dict[str, str]:
    """Garde seulement les états exploitables (``on`` / ``off``) des prises, par machine."""
    return {machine_id: state for machine_id, state in states.items() if state in {"on", "off"}}


def plan_restore(
    saved: Mapping[str, str], current: Mapping[str, str | None], protected: Iterable[str]
) -> dict[str, str]:
    """Commandes à envoyer au retour d'Internet : l'état mémorisé, sauf prise déjà conforme ou cycle en cours."""
    keep = set(protected)
    return {
        machine_id: wanted
        for machine_id, wanted in saved.items()
        if wanted in {"on", "off"} and machine_id not in keep and current.get(machine_id) != wanted
    }


def status_view(*, online: bool, since: datetime | None, active: bool, enabled: bool, saved: Mapping[str, str]) -> dict[str, Any]:
    """Vue exposée aux capteurs."""
    return {
        "online": online,
        "since": since.isoformat() if since else None,
        "backup_active": active,
        "backup_enabled": enabled,
        "saved_machines": dict(saved),
    }
