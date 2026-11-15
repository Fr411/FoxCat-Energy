"""A-14 : chaque prix HP / HC porte le complément de sa propre période, quelle que soit l'heure."""
from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy.const import DEFAULT_SETTINGS  # noqa: E402
from foxcat_energy.domain.tariff.tariff_model import final_client_price, hp_hc_final_prices  # noqa: E402

NIGHT = datetime(2026, 11, 15, 3, 0)   # HC
DAY = datetime(2026, 11, 15, 8, 0)     # HP


def settings(**extra):
    base = dict(DEFAULT_SETTINGS)
    base.update(distribution_profile="Bi-horaire (jour / nuit)", tariff_tou_hp_adder_eur_kwh=0.05,
                tariff_tou_hc_adder_eur_kwh=0.01)
    base.update(extra)
    return base


class PeriodAdderTests(unittest.TestCase):
    def test_hp_and_hc_prices_are_independent_of_the_evaluation_time(self):
        s = settings()
        for at in (NIGHT, DAY):
            hp, hc = hp_hc_final_prices(0.35, 0.25, at, s)
            self.assertAlmostEqual(hp, 0.40, msg=at)
            self.assertAlmostEqual(hc, 0.26, msg=at)

    def test_active_price_is_unchanged(self):
        s = settings()
        self.assertAlmostEqual(final_client_price(0.35, DAY, s), 0.40)
        self.assertAlmostEqual(final_client_price(0.25, NIGHT, s), 0.26)

    def test_missing_prices_stay_missing(self):
        self.assertEqual(hp_hc_final_prices(None, None, DAY, settings()), (None, None))
        hp, hc = hp_hc_final_prices(0.35, None, DAY, settings())
        self.assertAlmostEqual(hp, 0.40)
        self.assertIsNone(hc)

    def test_all_in_prices_get_no_complement(self):
        hp, hc = hp_hc_final_prices(0.35, 0.25, DAY, settings(price_is_all_in=True))
        self.assertEqual((hp, hc), (0.35, 0.25))

    def test_period_override_is_ignored_outside_the_bi_hourly_profile(self):
        s = settings(distribution_profile="Simple")
        hp, hc = hp_hc_final_prices(0.35, 0.25, DAY, s)
        self.assertEqual((hp, hc), (0.35, 0.25))
        impact = settings(distribution_profile="Impact", impact_peak_adder_eur_kwh=0.07)
        at_peak = datetime(2026, 11, 15, 18, 0)
        self.assertAlmostEqual(final_client_price(0.30, at_peak, impact, "HC"), 0.37)


if __name__ == "__main__":
    unittest.main()
