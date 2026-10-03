from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


BUS_WAIT_ACK = "WAIT_ACK"
BUS_ACK_RECEIVED = "ACK_RECEIVED"
BUS_ACK_PROCESSED = "ACK_PROCESSED"
BUS_NOK_BUSY = "NOK_BUSY"
BUS_NOK_REJECTED = "NOK_REJECTED"
BUS_TIMEOUT = "TIMEOUT"


@dataclass(slots=True)
class EnergyIntent:
    message_id: int
    source: str
    target: str
    action: str
    delta_w: float
    created_at: datetime
    frame_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    status: str = BUS_WAIT_ACK
    ack_at: datetime | None = None
    ack_by: str | None = None
    ack_reason: str = ""
    processed_at: datetime | None = None


class EnergyBus:
    """Communication EMS CORE <-> corps Onduleur avec ACK explicite.

    Le bus ne prend aucune décision énergétique. Il transporte les intentions,
    mémorise leurs accusés de réception et expose un historique court pour les
    diagnostics. L'ACK de transport (message reçu/traité) est volontairement
    distinct des ACK physiques RRCR/onduleur/réseau.
    """

    def __init__(self) -> None:
        self.last_ems_intent: EnergyIntent | None = None
        self._messages: list[EnergyIntent] = []
        self._next_message_id = 1
        self._daily_message_count = 0
        self._previous_day_message_count = 0
        self._last_daily_reset_at: datetime | None = None
        self.inverter_state: dict[str, Any] = {
            "status": "INITIALISATION",
            "more_solar_possible": False,
            "max_solar_reached": False,
            "pv_at_limit": False,
        }
        self.last_grid_frame_id = 0
        self.last_grid_frame_at: datetime | None = None
        self.frame_state: dict[str, Any] = {}
        self._frame_history: list[dict[str, Any]] = []
        self.last_transport_event = "Energy Bus : initialisation."

    def publish_message(
        self,
        *,
        source: str,
        target: str,
        action: str,
        delta_w: float,
        now: datetime,
        frame_id: int | None = None,
        **metadata: Any,
    ) -> int:
        """Publie un télégramme inter-corps avec ACK obligatoire."""
        message = EnergyIntent(
            message_id=self._next_message_id,
            source=str(source).upper(),
            target=str(target).upper(),
            action=action,
            delta_w=float(delta_w),
            created_at=now,
            frame_id=frame_id,
            metadata=dict(metadata),
        )
        self._next_message_id += 1
        self._daily_message_count += 1
        if message.source == "EMS":
            self.last_ems_intent = message
        self._messages.append(message)
        if len(self._messages) > 100:
            self._messages = self._messages[-100:]
        self.last_transport_event = (
            f"Energy Bus : {message.source} -> {message.target} : message #{message.message_id} "
            f"{action} envoyé, ACK attendu."
        )
        return message.message_id

    def publish_ems_intent(
        self,
        *,
        source: str,
        action: str,
        delta_w: float,
        now: datetime,
        target: str = "ONDULEUR",
        frame_id: int | None = None,
        **metadata: Any,
    ) -> int:
        # Compatibilité historique : les appels existants restent valides, mais
        # le corps source est désormais explicitement EMS sur le bus. Une origine
        # fournie par l'appelant reste souveraine afin d'éviter un doublon kwargs.
        metadata.setdefault("origin", source)
        return self.publish_message(
            source="EMS", target=target, action=action, delta_w=delta_w,
            now=now, frame_id=frame_id, **metadata,
        )

    def reset_daily_counters(self, now: datetime) -> dict[str, int]:
        """Réinitialise les identifiants visibles du bus à chaque nouvelle journée.

        Les messages encore en attente sont clôturés en TIMEOUT de fin de journée
        avant purge afin qu'aucun ordre inter-corps ne traverse silencieusement
        la frontière de minuit. Les ACK physiques restent gérés par leurs propres
        machines à états.
        """
        previous_count = int(self._daily_message_count)
        for message in self._messages:
            if message.status == BUS_WAIT_ACK:
                message.status = BUS_TIMEOUT
                message.ack_reason = "Fin de journée : ACK non reçu avant reset journalier."

        self._previous_day_message_count = previous_count
        self._daily_message_count = 0
        self._next_message_id = 1
        self._messages.clear()
        self.last_ems_intent = None
        self.last_grid_frame_id = 0
        self.last_grid_frame_at = None
        self.frame_state = {}
        self._frame_history.clear()
        self.inverter_state.update({"frame_id": 0, "frame_at": None})
        self._last_daily_reset_at = now
        self.last_transport_event = (
            "Energy Bus : reset journalier à minuit — "
            f"{previous_count} message(s) sur la journée précédente."
        )
        return {"previous_day_message_count": previous_count}

    def pending_for(self, target: str) -> EnergyIntent | None:
        target = str(target).upper()
        for message in reversed(self._messages):
            if message.target.upper() == target and message.status == BUS_WAIT_ACK:
                return message
        return None

    def acknowledge_pending(
        self,
        *,
        target: str,
        now: datetime,
        processed: bool = False,
        reason: str = "Message reçu.",
    ) -> int | None:
        message = self.pending_for(target)
        if message is None:
            return None
        message.status = BUS_ACK_PROCESSED if processed else BUS_ACK_RECEIVED
        message.ack_at = now
        message.ack_by = target
        message.ack_reason = reason
        if processed:
            message.processed_at = now
        label = "ACK TRAITÉ" if processed else "ACK REÇU"
        self.last_transport_event = (
            f"Energy Bus : {target} -> {message.source} : {label} #{message.message_id} : {reason}"
        )
        return message.message_id

    def mark_processed(self, message_id: int, *, by: str, now: datetime, reason: str) -> bool:
        message = self._find(message_id)
        if message is None:
            return False
        if message.status in {BUS_NOK_BUSY, BUS_NOK_REJECTED, BUS_TIMEOUT}:
            return False
        message.status = BUS_ACK_PROCESSED
        message.ack_at = message.ack_at or now
        message.ack_by = by
        message.ack_reason = reason
        message.processed_at = now
        self.last_transport_event = f"Energy Bus : {by} -> {message.source} : ACK TRAITÉ #{message_id} : {reason}"
        return True

    def mark_nok(
        self,
        message_id: int,
        *,
        by: str,
        now: datetime,
        reason: str,
        busy: bool = False,
    ) -> bool:
        message = self._find(message_id)
        if message is None or message.status == BUS_TIMEOUT:
            return False
        message.status = BUS_NOK_BUSY if busy else BUS_NOK_REJECTED
        message.ack_at = now
        message.ack_by = by
        message.ack_reason = reason
        self.last_transport_event = f"Energy Bus : {by} -> {message.source} : NOK #{message_id} : {reason}"
        return True

    def reject_pending(
        self,
        *,
        target: str,
        now: datetime,
        reason: str,
        busy: bool = False,
    ) -> int | None:
        message = self.pending_for(target)
        if message is None:
            return None
        message.status = BUS_NOK_BUSY if busy else BUS_NOK_REJECTED
        message.ack_at = now
        message.ack_by = target
        message.ack_reason = reason
        self.last_transport_event = (
            f"Energy Bus : {target} -> {message.source} : NOK #{message.message_id} : {reason}"
        )
        return message.message_id

    def expire_pending(self, *, now: datetime, timeout_s: float) -> list[int]:
        expired: list[int] = []
        timeout = max(float(timeout_s), 1.0)
        for message in self._messages:
            if message.status != BUS_WAIT_ACK:
                continue
            if (now - message.created_at).total_seconds() >= timeout:
                message.status = BUS_TIMEOUT
                message.ack_reason = "Aucun ACK reçu avant expiration du délai."
                expired.append(message.message_id)
                self.last_transport_event = (
                    f"Energy Bus : {message.source} : TIMEOUT ACK #{message.message_id} vers {message.target}."
                )
        return expired

    def expire_frames(self, *, now: datetime, timeout_s: float = 10.0) -> list[tuple[int, str]]:
        """Ferme explicitement toute trame restée PENDING anormalement longtemps."""
        expired: list[tuple[int, str]] = []
        timeout = max(float(timeout_s), 1.0)
        for item in self._frame_history:
            frame_at = item.get("frame_at")
            if not isinstance(frame_at, datetime) or (now - frame_at).total_seconds() < timeout:
                continue
            for core_key, label in (("ems", "EMS"), ("inverter", "ONDULEUR")):
                if item.get(f"{core_key}_status") == "PENDING":
                    item[f"{core_key}_status"] = "TIMEOUT"
                    item[f"{core_key}_processed_at"] = now
                    item[f"{core_key}_reason"] = f"Trame non clôturée avant {timeout:.0f} s."
                    expired.append((int(item.get("frame_id", 0)), label))
        if self.frame_state:
            current_id = int(self.frame_state.get("frame_id", -1))
            history_current = next((x for x in reversed(self._frame_history) if int(x.get("frame_id", -2)) == current_id), None)
            if history_current is not None:
                self.frame_state.update(history_current)
        if expired:
            self.last_transport_event = (
                "Energy Bus : Watchdog trame : "
                + ", ".join(f"#{fid}/{core}=TIMEOUT" for fid, core in expired)
            )
        return expired

    def _find(self, message_id: int) -> EnergyIntent | None:
        for message in reversed(self._messages):
            if message.message_id == int(message_id):
                return message
        return None

    def publish_inverter_state(self, **state: Any) -> None:
        self.inverter_state.update(state)

    def on_grid_frame(self, frame_id: int, now: datetime, **data: Any) -> None:
        """Ouvre une trame unique qui sera consommée par les deux corps."""
        self.last_grid_frame_id = int(frame_id)
        self.last_grid_frame_at = now
        self.frame_state = {
            "frame_id": int(frame_id),
            "frame_at": now,
            "ems_status": "PENDING",
            "inverter_status": "PENDING",
            "ems_reason": "",
            "inverter_reason": "",
            **data,
        }
        self._frame_history.append(dict(self.frame_state))
        if len(self._frame_history) > 20:
            self._frame_history = self._frame_history[-20:]

    def mark_frame_core(self, frame_id: int, core: str, status: str, *, now: datetime, reason: str = "") -> None:
        """Marque le traitement d'une trame par EMS ou Onduleur Core."""
        core_key = "ems" if str(core).upper() == "EMS" else "inverter"
        if int(self.frame_state.get("frame_id", -1)) == int(frame_id):
            self.frame_state[f"{core_key}_status"] = status
            self.frame_state[f"{core_key}_processed_at"] = now
            self.frame_state[f"{core_key}_reason"] = reason
        for item in reversed(self._frame_history):
            if int(item.get("frame_id", -1)) == int(frame_id):
                item[f"{core_key}_status"] = status
                item[f"{core_key}_processed_at"] = now
                item[f"{core_key}_reason"] = reason
                break

    @staticmethod
    def _message_view(intent: EnergyIntent | None) -> dict[str, Any] | None:
        if intent is None:
            return None
        return {
            "message_id": intent.message_id,
            "source": intent.source,
            "target": intent.target,
            "action": intent.action,
            "delta_w": intent.delta_w,
            "created_at": intent.created_at,
            "frame_id": intent.frame_id,
            "metadata": dict(intent.metadata),
            "status": intent.status,
            "ack_at": intent.ack_at,
            "ack_by": intent.ack_by,
            "ack_reason": intent.ack_reason,
            "processed_at": intent.processed_at,
        }

    def view(self) -> dict[str, Any]:
        intent = self.last_ems_intent
        pending = next((m for m in reversed(self._messages) if m.status == BUS_WAIT_ACK), None)
        return {
            "last_grid_frame_id": self.last_grid_frame_id,
            "last_grid_frame_at": self.last_grid_frame_at,
            "ems_intent": self._message_view(intent),
            "pending_message": self._message_view(pending),
            "last_transport_event": self.last_transport_event,
            "message_count": self._daily_message_count,
            "previous_day_message_count": self._previous_day_message_count,
            "last_daily_reset_at": self._last_daily_reset_at,
            "pending_count": sum(1 for m in self._messages if m.status == BUS_WAIT_ACK),
            "frame": dict(self.frame_state),
            "frame_history": [dict(item) for item in self._frame_history],
            "last_message": self._message_view(self._messages[-1] if self._messages else None),
            "inverter": dict(self.inverter_state),
        }
