"""Tarif capacitaire flamand : pointe facturée = moyenne des pointes mensuelles (≤ 12 mois, minimum 2,5 kW)."""
from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy.domain.accounting.series import ConsumptionSeries  # noqa: E402
from foxcat_energy.domain.tariff.compare import compare_tariffs  # noqa: E402
from foxcat_energy.domain.tariff.grid_costs import GridCosts  # noqa: E402
from foxcat_energy.domain.tariff.models import CAPACITY_PEAK, CapacityTerm, ENERGY_FIXED, Tariff  # noqa: E402
from foxcat_energy.domain.tariff.valuation import Slot, billed_peak_kw  # noqa: E402

FLEMISH = GridCosts(capacity=CapacityTerm(kind=CAPACITY_PEAK, eur_per_kw_year=55.0, min_kw=2.5))


class BilledPeakTests(unittest.TestCase):
    def test_average_of_monthly_peaks_each_floored_at_the_minimum(self):
        # 1,0 kW (relevé à 2,5), 4,0 kW et 6,0 kW en cours : moyenne (2,5 + 4 + 6) ÷ 3
        self.assertAlmostEqual(billed_peak_kw(6.0, 2.5, [1.0, 4.0]), (2.5 + 4.0 + 6.0) / 3)

    def test_without_history_only_the_current_month_counts(self):
        self.assertAlmostEqual(billed_peak_kw(6.0, 2.5, None), 6.0)
        self.assertAlmostEqual(billed_peak_kw(1.0, 2.5, []), 2.5)

    def test_at_most_twelve_months_are_averaged(self):
        history = [10.0] + [3.0] * 11            # le plus ancien (10 kW) sort de la fenêtre de 12 mois
        self.assertAlmostEqual(billed_peak_kw(3.0, 2.5, history), 3.0)


class CapacityCostTests(unittest.TestCase):
    def _slots(self, kw: float):
        start = datetime(2026, 11, 1, 0, 0)
        slots = [Slot(at=start + timedelta(minutes=15 * i), import_kwh=0.1, export_kwh=0.0) for i in range(96 * 10)]
        slots[40] = Slot(at=slots[40].at, import_kwh=kw * 0.25, export_kwh=0.0)
        return slots

    def _capacity(self, history):
        tariff = Tariff(id="t", name="T", energy_kind=ENERGY_FIXED, energy_price=0.3)
        slots = self._slots(6.0)
        result = compare_tariffs(slots, [tariff], month_slots=slots, grid_costs=FLEMISH, peak_history_kw=history)
        return result["tariffs"]["t"]["capacitaire_eur"]

    def test_history_changes_the_estimate(self):
        alone = self._capacity(None)
        averaged = self._capacity([2.5, 2.5, 2.5])
        self.assertGreater(alone, averaged)
        ratio = averaged / alone
        self.assertAlmostEqual(ratio, ((2.5 * 3 + 6.0) / 4) / 6.0, places=4)


class SeriesPeakTests(unittest.TestCase):
    def _feed(self, series, start, kw, minutes):
        for i in range(minutes + 1):
            series.process(
                SimpleNamespace(timestamp=start + timedelta(minutes=i), valid=True, import_w=kw * 1000,
                                export_w=0.0, pv_w=0.0, house_w=kw * 1000), {})

    def test_peak_is_the_quarter_hour_average_not_an_instantaneous_point(self):
        series = ConsumptionSeries()
        start = datetime(2026, 11, 15, 12, 0)
        for i in range(16):  # 6 kW pendant 5 minutes puis 0 W : moyenne du quart d'heure = 2 kW
            watts = 6000 if i <= 5 else 0
            series.process(SimpleNamespace(timestamp=start + timedelta(minutes=i), valid=True, import_w=watts,
                                           export_w=0.0, pv_w=0.0, house_w=watts), {})
        self.assertAlmostEqual(series.monthly_peaks()["2026-11"], 2.0, places=2)

    def test_previous_months_feed_the_history_and_survive_a_restart(self):
        series = ConsumptionSeries()
        self._feed(series, datetime(2026, 9, 10, 12, 0), 3.0, 30)
        self._feed(series, datetime(2026, 10, 10, 12, 0), 5.0, 30)
        self._feed(series, datetime(2026, 11, 10, 12, 0), 4.0, 30)
        self.assertEqual([round(p) for p in series.previous_peaks_kw(datetime(2026, 11, 1))], [3, 5])
        restored = ConsumptionSeries()
        restored.restore(series.dump())
        self.assertEqual([round(p) for p in restored.previous_peaks_kw(datetime(2026, 11, 1))], [3, 5])

    def test_old_store_without_peaks_is_rebuilt_from_the_kept_slots(self):
        series = ConsumptionSeries()
        self._feed(series, datetime(2026, 11, 10, 12, 0), 4.0, 30)
        dumped = series.dump()
        dumped.pop("monthly_peaks")
        restored = ConsumptionSeries()
        restored.restore(dumped)
        self.assertAlmostEqual(restored.monthly_peaks()["2026-11"], 4.0, places=1)

    def test_only_thirteen_months_are_kept(self):
        series = ConsumptionSeries()
        for month in range(1, 13):
            series._note_peak(datetime(2025, month, 1), 1.0)
        for month in range(1, 5):
            series._note_peak(datetime(2026, month, 1), 1.0)
        series._prune(datetime(2026, 5, 1))
        self.assertEqual(len(series.monthly_peaks()), 13)


if __name__ == "__main__":
    unittest.main()
