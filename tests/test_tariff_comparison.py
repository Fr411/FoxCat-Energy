"""Modèle de tarif, valorisation, série au quart d'heure et comparateur."""
from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

COMPONENT_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT_PATH)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy.domain.accounting.series import ConsumptionSeries  # noqa: E402
from foxcat_energy.domain.tariff import grid_costs as gc, legacy, templates  # noqa: E402
from foxcat_energy.domain.tariff.compare import compare_tariffs, window_bounds  # noqa: E402
from foxcat_energy.domain.tariff.models import (  # noqa: E402
    CAPACITY_FLAT,
    CAPACITY_PEAK,
    ENERGY_FIXED,
    ENERGY_OBSERVED,
    ENERGY_PERIODS,
    INJECTION_FIXED,
    INJECTION_OBSERVED,
    CapacityTerm,
    Period,
    Tariff,
    TariffError,
    tariffs_from_json_value,
)
from foxcat_energy.domain.tariff.tariff_model import final_client_price  # noqa: E402
from foxcat_energy.domain.tariff.valuation import Slot, value_series  # noqa: E402

TZ = timezone(timedelta(hours=1))
# 2026-11-16 est un lundi.
MONDAY = datetime(2026, 11, 16, 0, 0, tzinfo=TZ)


def slot(hour: int, minute: int = 0, imp: float = 1.0, exp: float = 0.0, buy=None, sell=None, day: int = 0):
    return Slot(MONDAY.replace(hour=hour, minute=minute) + timedelta(days=day), imp, exp, buy, sell)


class PeriodTests(unittest.TestCase):
    def test_wraps_midnight(self) -> None:
        night = Period("nuit", "22:00", "07:00", 0.0)
        self.assertTrue(night.contains(23 * 60, 0))
        self.assertTrue(night.contains(3 * 60, 0))
        self.assertFalse(night.contains(12 * 60, 0))
        self.assertFalse(night.contains(7 * 60, 0))

    def test_equal_bounds_never_match(self) -> None:
        self.assertFalse(Period("x", "08:00", "08:00", 0.0).contains(8 * 60, 0))

    def test_weekdays_filter(self) -> None:
        weekend = Period("we", "00:00", "24:00", 0.0, days=(5, 6))
        self.assertTrue(weekend.contains(600, 5))
        self.assertFalse(weekend.contains(600, 0))


class ModelTests(unittest.TestCase):
    def test_roundtrip_all_templates(self) -> None:
        for tid, tariff in templates.template_catalog().items():
            again = Tariff.from_dict(tariff.to_dict())
            self.assertEqual(again, tariff, tid)

    def test_invalid_definitions_are_rejected(self) -> None:
        for raw in (
            {"id": "", "name": "x"},
            {"id": "a", "name": "x", "energy_kind": "inconnu"},
            {"id": "a", "name": "x", "energy_price": "abc"},
            {"id": "a", "name": "x", "energy_periods": [{"start": "25:00", "end": "07:00", "price": 1}]},
            {"id": "a", "name": "x", "energy_periods": [{"start": "07:00", "end": "08:00", "price": 1, "days": [9]}]},
            {"id": "a", "name": "x", "fixed_fee_eur_year": -1},
            {"id": "a", "name": "x", "capacity": {"kind": "bizarre"}},
            "pas un objet",
        ):
            with self.assertRaises(TariffError, msg=str(raw)):
                Tariff.from_dict(raw)

    def test_json_import_rejects_duplicate_ids(self) -> None:
        one = {"id": "a", "name": "A"}
        with self.assertRaises(TariffError):
            tariffs_from_json_value([one, one])
        self.assertEqual(len(tariffs_from_json_value(one)), 1)


class ValuationTests(unittest.TestCase):
    def test_fixed_price_and_injection(self) -> None:
        tariff = Tariff("t", "t", ENERGY_FIXED, 0.30, injection_kind=INJECTION_FIXED, injection_price=0.05)
        cost = value_series([slot(10, imp=2.0, exp=1.0)], tariff)
        self.assertAlmostEqual(cost.energy_eur, 0.60)
        self.assertAlmostEqual(cost.injection_revenue_eur, 0.05)
        self.assertAlmostEqual(cost.total_eur, 0.55)

    def test_periods_pick_hp_and_hc(self) -> None:
        tariff = templates.template_catalog()["wal_bi_2026"]
        hp = value_series([slot(8)], tariff).energy_eur
        hc_midday = value_series([slot(12)], tariff).energy_eur
        hc_night = value_series([slot(23)], tariff).energy_eur
        self.assertAlmostEqual(hp, templates.DEFAULT_HP_EUR_KWH)
        self.assertAlmostEqual(hc_midday, templates.DEFAULT_HC_EUR_KWH)
        self.assertAlmostEqual(hc_night, templates.DEFAULT_HC_EUR_KWH)

    def test_all_in_ignores_network_components(self) -> None:
        base = dict(energy_kind=ENERGY_FIXED, energy_price=0.30, network_default=0.10, adder_flat=0.02)
        plain = value_series([slot(10)], Tariff("a", "a", **base))
        all_in = value_series([slot(10)], Tariff("b", "b", all_in=True, **base))
        self.assertAlmostEqual(plain.network_eur, 0.12)
        self.assertAlmostEqual(all_in.network_eur, 0.0)
        self.assertAlmostEqual(all_in.energy_eur, 0.30)

    def test_observed_price_and_missing_price(self) -> None:
        tariff = Tariff("o", "o", ENERGY_OBSERVED, all_in=True, injection_kind=INJECTION_OBSERVED)
        cost = value_series([slot(10, imp=1.0, exp=1.0, buy=0.40, sell=0.10), slot(11, imp=3.0)], tariff)
        self.assertAlmostEqual(cost.energy_eur, 0.40)
        self.assertAlmostEqual(cost.unpriced_import_kwh, 3.0)
        self.assertAlmostEqual(cost.injection_revenue_eur, 0.10)

    def test_negative_energy_is_ignored_not_credited(self) -> None:
        tariff = Tariff("t", "t", ENERGY_FIXED, 0.30)
        self.assertAlmostEqual(value_series([slot(10, imp=-5.0)], tariff).energy_eur, 0.0)

    def test_fixed_fee_is_prorated(self) -> None:
        tariff = Tariff("t", "t", fixed_fee_eur_year=87.6)
        day = [Slot(MONDAY + timedelta(minutes=15 * q), 0, 0) for q in range(96)]
        # 87,6 € / 365 = 0,24 € par jour
        self.assertAlmostEqual(value_series(day, tariff).fixed_eur, 0.24, places=6)

    def test_capacity_flat(self) -> None:
        tariff = Tariff("b", "b", capacity=CapacityTerm(CAPACITY_FLAT, eur_per_year=120.0))
        month = 30 * 96
        slots = [Slot(MONDAY.replace(day=1) + timedelta(minutes=15 * q), 0, 0) for q in range(month)]
        # novembre = 30 jours : la totalité du mois vaut 120/12 = 10 €.
        self.assertAlmostEqual(value_series(slots, tariff).capacity_eur, 10.0, places=6)

    def test_capacity_peak_uses_month_peak_and_minimum(self) -> None:
        tariff = Tariff("f", "f", capacity=CapacityTerm(CAPACITY_PEAK, eur_per_kw_year=60.0, min_kw=2.5))
        first = MONDAY.replace(day=1)
        month = [Slot(first + timedelta(minutes=15 * q), 0.1, 0) for q in range(30 * 96)]
        window = month[:96]  # un jour sur 30
        # pointe 0,1 kWh/0,25 h = 0,4 kW < minimum 2,5 kW → facturé 2,5 kW
        cost = value_series(window, tariff, month_slots=month)
        self.assertAlmostEqual(cost.capacity_eur, 2.5 * 60.0 / 12.0 / 30.0, places=6)
        month[10] = Slot(month[10].at, 1.5, 0)  # pointe 6 kW
        cost = value_series(window, tariff, month_slots=month)
        self.assertAlmostEqual(cost.capacity_eur, 6.0 * 60.0 / 12.0 / 30.0, places=6)

    def test_empty_window(self) -> None:
        cost = value_series([], templates.template_catalog()["wal_mono"])
        self.assertEqual(cost.total_eur, 0.0)


class GridCostsTests(unittest.TestCase):
    """Le capacitaire et la redevance prosumer sont des coûts de l'installation, pas du tarif."""

    first = MONDAY.replace(day=1)

    def month(self, kwh: float = 0.1, days: int = 30):
        return [Slot(self.first + timedelta(minutes=15 * q), kwh, 0) for q in range(days * 96)]

    def test_from_settings_is_tolerant(self) -> None:
        costs = gc.GridCosts.from_settings({
            "grid_capacity_kind": "inconnu", "grid_capacity_eur_per_kw_year": "abc",
            "grid_capacity_min_kw": -3, "grid_prosumer_eur_per_year": None,
        })
        self.assertTrue(costs.is_empty)
        self.assertTrue(gc.GridCosts.from_settings({}).is_empty)

    def test_installation_capacity_applies_to_every_tariff(self) -> None:
        costs = gc.GridCosts(CapacityTerm(CAPACITY_PEAK, eur_per_kw_year=60.0, min_kw=2.5))
        month = self.month()
        cheap = Tariff("a", "A", ENERGY_FIXED, 0.20)
        dear = Tariff("b", "B", ENERGY_FIXED, 0.40)
        a = value_series(month, cheap, month_slots=month, grid_costs=costs)
        b = value_series(month, dear, month_slots=month, grid_costs=costs)
        # mois complet : 2,5 kW minimum × 60 / 12 = 12,50 €, identique pour les deux tarifs
        self.assertAlmostEqual(a.capacity_eur, 12.5, places=6)
        self.assertAlmostEqual(b.capacity_eur, 12.5, places=6)

    def test_installation_capacity_overrides_the_tariff_one(self) -> None:
        tariff = Tariff("t", "T", capacity=CapacityTerm(CAPACITY_FLAT, eur_per_year=1200.0))
        month = self.month(0.0)
        alone = value_series(month, tariff, month_slots=month)
        overridden = value_series(
            month, tariff, month_slots=month, grid_costs=gc.GridCosts(CapacityTerm(CAPACITY_FLAT, eur_per_year=120.0))
        )
        self.assertAlmostEqual(alone.capacity_eur, 100.0, places=6)
        self.assertAlmostEqual(overridden.capacity_eur, 10.0, places=6)

    def test_empty_grid_costs_keep_the_tariff_capacity(self) -> None:
        tariff = Tariff("t", "T", capacity=CapacityTerm(CAPACITY_FLAT, eur_per_year=120.0))
        month = self.month(0.0)
        cost = value_series(month, tariff, month_slots=month, grid_costs=gc.GridCosts())
        self.assertAlmostEqual(cost.capacity_eur, 10.0, places=6)

    def test_prosumer_fee_is_prorated_and_added_to_the_total(self) -> None:
        costs = gc.GridCosts(prosumer_eur_per_year=87.6)
        day = [Slot(MONDAY + timedelta(minutes=15 * q), 0, 0) for q in range(96)]
        cost = value_series(day, Tariff("t", "T"), grid_costs=costs)
        self.assertAlmostEqual(cost.prosumer_eur, 0.24, places=6)
        self.assertAlmostEqual(cost.total_eur, 0.24, places=6)
        self.assertAlmostEqual(cost.to_dict()["prosumer_eur"], 0.24, places=4)

    def test_comparison_gap_is_unchanged_by_grid_costs(self) -> None:
        """Mêmes coûts de réseau pour tous : l'écart entre tarifs ne dépend que de l'énergie."""
        costs = gc.GridCosts(CapacityTerm(CAPACITY_PEAK, eur_per_kw_year=60.0, min_kw=2.5), 50.0)
        month = self.month(0.2)
        tariffs = [Tariff("a", "A", ENERGY_FIXED, 0.20), Tariff("b", "B", ENERGY_FIXED, 0.30)]
        plain = compare_tariffs(month, tariffs, month_slots=month, reference_id="a")
        loaded = compare_tariffs(month, tariffs, month_slots=month, reference_id="a", grid_costs=costs)
        self.assertAlmostEqual(
            plain["tariffs"]["b"]["ecart_vs_reference_eur"], loaded["tariffs"]["b"]["ecart_vs_reference_eur"], places=6
        )
        self.assertGreater(loaded["tariffs"]["a"]["total_eur"], plain["tariffs"]["a"]["total_eur"])

    def test_region_presets(self) -> None:
        self.assertEqual(gc.region_settings("flandre")["grid_capacity_kind"], "peak_monthly")
        self.assertEqual(gc.region_settings("flandre")["grid_capacity_min_kw"], 2.5)
        self.assertEqual(gc.region_settings("bruxelles")["grid_capacity_kind"], "flat")
        self.assertEqual(gc.region_settings("wallonie"), {})
        self.assertEqual(gc.region_settings(None), {})
        self.assertEqual(gc.region_settings("flandre"), gc.region_settings("flandre"))  # copie indépendante

    def test_templates_no_longer_carry_a_capacity_term(self) -> None:
        for tid, tariff in templates.template_catalog().items():
            self.assertEqual(tariff.capacity.kind, "none", tid)


class LegacyEquivalenceTests(unittest.TestCase):
    """tariff_from_settings doit reproduire final_client_price pour les réglages actuels."""

    def assert_equivalent(self, settings: dict, base_for) -> None:
        tariff = legacy.tariff_from_settings(settings)
        self.assertIsNotNone(tariff)
        for day in (0, 5):  # un jour ouvré et un samedi
            for quarter in range(96):
                at = MONDAY + timedelta(days=day, minutes=15 * quarter)
                expected = final_client_price(base_for(at), at, settings)
                cost = value_series([Slot(at, 1.0, 0.0)], tariff)
                self.assertAlmostEqual(cost.energy_eur + cost.network_eur, expected, places=9, msg=str(at))

    def test_bi_horaire(self) -> None:
        settings = {
            "price_source": "Contractuelle / fixe", "tariff_structure": "Bi-horaire",
            "tariff_hp_price_eur_kwh": 0.40, "tariff_hc_price_eur_kwh": 0.22,
            "tariff_tou_hp_adder_eur_kwh": 0.05, "tariff_tou_hc_adder_eur_kwh": 0.03,
        }
        from foxcat_energy.domain.tariff.tariff import tariff_period

        self.assert_equivalent(settings, lambda at: 0.40 if tariff_period(at, settings) == "HP" else 0.22)

    def test_impact(self) -> None:
        settings = {
            "price_source": "Contractuelle / fixe", "tariff_structure": "Impact",
            "tariff_simple_fixed_price_eur_kwh": 0.28,
            "impact_eco_adder_eur_kwh": -0.02, "impact_medium_adder_eur_kwh": 0.01,
            "impact_peak_adder_eur_kwh": 0.06,
        }
        self.assert_equivalent(settings, lambda at: 0.28)

    def test_simple(self) -> None:
        settings = {
            "price_source": "Contractuelle / fixe", "tariff_structure": "Simple",
            "tariff_simple_fixed_price_eur_kwh": 0.31,
        }
        self.assert_equivalent(settings, lambda at: 0.31)

    def test_prices_from_entities_have_no_contract_tariff(self) -> None:
        self.assertIsNone(legacy.tariff_from_settings({"price_source": "Dynamique Day-Ahead"}))
        self.assertEqual(legacy.observed_tariff().energy_kind, ENERGY_OBSERVED)


def snap(ts: datetime, imp=0.0, exp=0.0, pv=0.0, house=0.0, valid=True):
    return SimpleNamespace(timestamp=ts, import_w=imp, export_w=exp, pv_w=pv, house_w=house, valid=valid)


class SeriesTests(unittest.TestCase):
    def test_energy_is_split_across_quarter_boundaries(self) -> None:
        series = ConsumptionSeries()
        t0 = MONDAY.replace(hour=10, minute=10)
        series.process(snap(t0, imp=4000), {"active_buy": 0.30})
        # 10 minutes à 4 kW : 5 min dans le créneau 10:00, 5 min dans 10:15.
        series.process(snap(t0 + timedelta(minutes=10), imp=4000), {"active_buy": 0.30})
        slots = series.slots(MONDAY.replace(hour=10), MONDAY.replace(hour=11))
        self.assertEqual([s.at.minute for s in slots], [0, 15])
        self.assertAlmostEqual(slots[0].import_kwh, 4.0 * 5 / 60)
        self.assertAlmostEqual(slots[1].import_kwh, 4.0 * 5 / 60)
        self.assertAlmostEqual(slots[0].buy, 0.30)

    def test_invalid_frame_resets_integration(self) -> None:
        series = ConsumptionSeries()
        t0 = MONDAY.replace(hour=10)
        series.process(snap(t0, imp=1000), {})
        series.process(snap(t0 + timedelta(minutes=1), valid=False), {})
        series.process(snap(t0 + timedelta(minutes=5), imp=1000), {})
        self.assertEqual(len(series), 0)

    def test_long_gap_is_capped(self) -> None:
        series = ConsumptionSeries()
        t0 = MONDAY.replace(hour=0)
        series.process(snap(t0, imp=1000), {})
        series.process(snap(t0 + timedelta(hours=5), imp=1000), {})
        total = sum(s.import_kwh for s in series.slots(t0, t0 + timedelta(days=1)))
        self.assertAlmostEqual(total, 1.0)  # 1 kW pendant 1 h maximum

    def test_dump_restore_roundtrip(self) -> None:
        series = ConsumptionSeries()
        t0 = MONDAY.replace(hour=8)
        series.process(snap(t0, imp=2000, exp=100), {"active_buy": 0.4, "export_value": 0.05})
        series.process(snap(t0 + timedelta(minutes=20), imp=2000, exp=100), {"active_buy": 0.4, "export_value": 0.05})
        restored = ConsumptionSeries()
        restored.restore(series.dump())
        a = series.slots(t0.replace(hour=0), t0.replace(hour=23))
        b = restored.slots(t0.replace(hour=0), t0.replace(hour=23))
        self.assertEqual(len(a), len(b))
        for x, y in zip(a, b):
            self.assertAlmostEqual(x.import_kwh, y.import_kwh, places=5)
            self.assertAlmostEqual(x.buy, y.buy, places=5)
            self.assertAlmostEqual(x.sell, y.sell, places=5)

    def test_restore_is_tolerant(self) -> None:
        series = ConsumptionSeries()
        for raw in (None, "x", {}, {"schema": 99, "slots": []}, {"schema": 1, "slots": [[1, 2], "?", [0] * 9]}):
            series.restore(raw)
            self.assertIsNone(series.last_valid_ts)
        series.restore({"schema": 1, "slots": [[1, "a", 0, 0, 0, 0, 0, 0, 0]]})
        self.assertEqual(len(series), 0)

    def test_retention_prunes_old_slots(self) -> None:
        series = ConsumptionSeries(retention_days=3)
        old = MONDAY - timedelta(days=10)
        series.process(snap(old, imp=1000), {})
        series.process(snap(old + timedelta(minutes=5), imp=1000), {})
        self.assertEqual(len(series), 1)
        series.process(snap(MONDAY, valid=False), {})  # coupure : l'intégration repart de zéro
        series.process(snap(MONDAY, imp=1000), {})
        series.process(snap(MONDAY + timedelta(minutes=5), imp=1000), {})
        everything = series.slots(old - timedelta(days=1), MONDAY + timedelta(days=1))
        self.assertEqual(len(everything), 1)
        self.assertGreaterEqual(everything[0].at, MONDAY - timedelta(days=3))


class CompareTests(unittest.TestCase):
    def test_ranking_and_reference_gap(self) -> None:
        cheap = Tariff("cheap", "Pas cher", ENERGY_FIXED, 0.20)
        dear = Tariff("dear", "Cher", ENERGY_FIXED, 0.40)
        result = compare_tariffs([slot(10, imp=10.0)], [dear, cheap], reference_id="dear")
        self.assertEqual(result["cheapest"], "cheap")
        self.assertEqual(list(result["tariffs"]), ["cheap", "dear"])
        self.assertAlmostEqual(result["tariffs"]["cheap"]["ecart_vs_reference_eur"], -2.0)
        self.assertAlmostEqual(result["tariffs"]["dear"]["ecart_vs_reference_eur"], 0.0)
        self.assertIn("comportement constant", result["method"])

    def test_empty(self) -> None:
        result = compare_tariffs([], [])
        self.assertIsNone(result["cheapest"])

    def test_window_bounds(self) -> None:
        now = MONDAY.replace(day=18, hour=14, minute=7)
        self.assertEqual(window_bounds(now, "today")[0], now.replace(hour=0, minute=0))
        self.assertEqual(window_bounds(now, "month")[0].day, 1)
        with self.assertRaises(ValueError):
            window_bounds(now, "year")


class EndToEndTests(unittest.TestCase):
    """Une journée de trames → série → comparaison des modèles."""

    def test_day_of_frames_feeds_every_template(self) -> None:
        series = ConsumptionSeries()
        buy = 0.32
        total_import_kwh = 0.0
        ts = MONDAY
        series.process(snap(ts, imp=500), {"active_buy": buy})
        for _ in range(24 * 60):
            ts += timedelta(minutes=1)
            import_w = 3000.0 if 17 <= ts.hour < 21 else 400.0
            total_import_kwh += import_w / 1000.0 / 60.0
            series.process(snap(ts, imp=import_w, house=import_w), {"active_buy": buy, "export_value": 0.04})
        window = series.slots(MONDAY, MONDAY + timedelta(days=1))
        tariffs = [legacy.observed_tariff(), *templates.template_catalog().values()]
        result = compare_tariffs(window, tariffs, month_slots=window, reference_id=legacy.ACTIVE_TARIFF_ID)
        self.assertAlmostEqual(result["import_kwh"], total_import_kwh, places=2)
        self.assertEqual(set(result["tariffs"]), {t.id for t in tariffs})
        observed = result["tariffs"][legacy.ACTIVE_TARIFF_ID]
        self.assertAlmostEqual(observed["energie_eur"], total_import_kwh * buy, places=2)
        self.assertAlmostEqual(observed["ecart_vs_reference_eur"], 0.0)
        for entry in result["tariffs"].values():
            self.assertEqual(entry["import_sans_prix_kwh"], 0.0)


if __name__ == "__main__":
    unittest.main()
