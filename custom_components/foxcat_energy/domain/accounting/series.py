"""Série de consommation au quart d'heure.

Elle conserve la vérité physique (kWh importés, exportés, produits, consommés)
et les prix réellement observés, indépendamment du tarif. Un autre tarif peut
ainsi être rejoué après coup (comparateur). Le ledger historique reste inchangé.

Module pur : aucune dépendance à Home Assistant.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ..tariff.valuation import Slot

SLOT_SECONDS = 900
MAX_INTEGRATION_GAP_S = 3600.0
DEFAULT_RETENTION_DAYS = 62
SCHEMA = 1

# Indices d'un enregistrement de créneau.
_IMP, _EXP, _PV, _HOUSE, _BUY_W, _BUY_T, _SELL_W, _SELL_T = range(8)


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    result = float(value)
    return result if result == result and abs(result) != float("inf") else None


def slot_start(at: datetime) -> datetime:
    return at.replace(minute=(at.minute // 15) * 15, second=0, microsecond=0)


class ConsumptionSeries:
    """Tampon borné de créneaux d'un quart d'heure."""

    def __init__(self, retention_days: int = DEFAULT_RETENTION_DAYS) -> None:
        self.retention = timedelta(days=max(int(retention_days), 2))
        self._slots: dict[int, list[float]] = {}
        self.last_valid_ts: datetime | None = None
        self.revision = 0

    # -- intégration -------------------------------------------------------
    def process(self, snapshot: Any, prices: dict[str, Any]) -> bool:
        """Intègre une trame. Renvoie ``True`` si la série a changé."""
        now = snapshot.timestamp
        if not snapshot.valid:
            self.last_valid_ts = None
            return False
        previous = self.last_valid_ts
        self.last_valid_ts = now
        if previous is None:
            return False
        dt = (now - previous).total_seconds()
        if dt <= 0:
            return False
        if dt > MAX_INTEGRATION_GAP_S:
            previous = now - timedelta(seconds=MAX_INTEGRATION_GAP_S)

        imp_w = max(float(snapshot.import_w), 0.0)
        exp_w = max(float(snapshot.export_w), 0.0)
        pv_w = max(float(snapshot.pv_w), 0.0)
        house_w = max(float(snapshot.house_w), 0.0)
        buy = _number(prices.get("active_buy"))
        sell = _number(prices.get("export_value"))

        cursor = previous
        while cursor < now:
            boundary = slot_start(cursor) + timedelta(seconds=SLOT_SECONDS)
            end = min(boundary, now)
            seconds = (end - cursor).total_seconds()
            if seconds > 0:
                self._add(slot_start(cursor), seconds, imp_w, exp_w, pv_w, house_w, buy, sell)
            cursor = end
        self._prune(now)
        self.revision += 1
        return True

    def _add(
        self, start: datetime, seconds: float, imp_w: float, exp_w: float,
        pv_w: float, house_w: float, buy: float | None, sell: float | None,
    ) -> None:
        hours = seconds / 3600.0
        record = self._slots.setdefault(int(start.timestamp()), [0.0] * 8)
        record[_IMP] += imp_w / 1000.0 * hours
        record[_EXP] += exp_w / 1000.0 * hours
        record[_PV] += pv_w / 1000.0 * hours
        record[_HOUSE] += house_w / 1000.0 * hours
        if buy is not None:
            record[_BUY_W] += buy * seconds
            record[_BUY_T] += seconds
        if sell is not None:
            record[_SELL_W] += sell * seconds
            record[_SELL_T] += seconds

    def _prune(self, now: datetime) -> None:
        limit = int((now - self.retention).timestamp())
        for key in [k for k in self._slots if k < limit]:
            del self._slots[key]

    # -- lecture -----------------------------------------------------------
    def slots(self, start: datetime, end: datetime) -> list[Slot]:
        """Créneaux dont le début est dans ``[start, end)`` (datetimes avec fuseau)."""
        low, high = int(start.timestamp()), int(end.timestamp())
        tz = start.tzinfo
        result: list[Slot] = []
        for key in sorted(k for k in self._slots if low <= k < high):
            record = self._slots[key]
            result.append(Slot(
                at=datetime.fromtimestamp(key, tz),
                import_kwh=record[_IMP],
                export_kwh=record[_EXP],
                buy=record[_BUY_W] / record[_BUY_T] if record[_BUY_T] > 0 else None,
                sell=record[_SELL_W] / record[_SELL_T] if record[_SELL_T] > 0 else None,
            ))
        return result

    def __len__(self) -> int:
        return len(self._slots)

    # -- persistance -------------------------------------------------------
    def dump(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "slots": [
                [key, *[round(value, 6) for value in record]]
                for key, record in sorted(self._slots.items())
            ],
        }

    def restore(self, raw: Any) -> None:
        """Lecture tolérante : une donnée invalide est ignorée, jamais fatale."""
        self._slots = {}
        self.last_valid_ts = None  # ne jamais intégrer l'arrêt de Home Assistant
        if not isinstance(raw, dict) or raw.get("schema") != SCHEMA:
            return
        for row in raw.get("slots") or []:
            if not isinstance(row, (list, tuple)) or len(row) != 9:
                continue
            values = [_number(item) for item in row]
            if any(value is None for value in values):
                continue
            self._slots[int(values[0])] = [float(v) for v in values[1:]]
        self.revision += 1
