"""Démarrage prévu du boiler en heures creuses : reproduit la règle réelle du boiler."""
from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy.const import DEFAULT_SETTINGS  # noqa: E402
from foxcat_energy.domain.pricing.boiler_plan import plan_boiler_hc  # noqa: E402
from foxcat_energy.domain.pricing.dynamic_planner import boiler_lane  # noqa: E402

UTC = timezone.utc
DAY = datetime(2026, 11, 28, 0, 0, tzinfo=UTC)
SETTINGS = dict(DEFAULT_SETTINGS)


def ts(hour, minute=0, day=0):
    return int((DAY + timedelta(days=day, hours=hour, minutes=minute)).timestamp())


# HC : nuit 22 h → 07 h, midi 11 h → 17 h (HP 07-11 et 17-22).
HC = [(ts(-2), ts(7)), (ts(11), ts(17)), (ts(22), ts(7, day=1)), (ts(11, day=1), ts(17, day=1))]


def plan(now, temp, **kw):
    args = dict(now_ts=now, settings=SETTINGS, temp_c=temp, boiler_on=False, hc_windows=HC, mode="Éco")
    args.update(kw)
    return plan_boiler_hc(**args)


class BoilerHcPlanTests(unittest.TestCase):
    def test_cold_water_waits_for_the_last_failback_of_the_window(self):
        result = plan(ts(5), 40.0)
        self.assertEqual(result["status"], "PROGRAMME")
        window_end = ts(7)
        heating_s = result["heating_min"] * 60
        # démarre au plus tard : durée de chauffe + marge de 30 min avant la fin des HC
        self.assertAlmostEqual(result["start_ts"], window_end - heating_s - 30 * 60, delta=180)
        self.assertGreater(result["start_ts"], ts(5))
        self.assertLessEqual(result["end_ts"], window_end)

    def test_failback_already_reached_starts_now(self):
        result = plan(ts(6, 20), 38.0)
        self.assertEqual(result["status"], "MAINTENANT")
        self.assertLessEqual(result["start_ts"], ts(6, 20) + 60)

    def test_without_waiting_option_it_starts_when_hc_open(self):
        result = plan(ts(5), 40.0, settings=dict(SETTINGS, boiler_hc_wait_failback=False))
        self.assertEqual(result["status"], "MAINTENANT")

    def test_warm_water_starts_only_after_it_cools_below_threshold(self):
        # 50 °C, refroidissement 0,5 °C/h : passe sous 43 °C vers 19 h → première HC exploitable = nuit 22 h
        result = plan(ts(5), 50.0)
        self.assertEqual(result["status"], "PROGRAMME")
        self.assertGreaterEqual(result["start_ts"], ts(22))
        self.assertLess(result["start_ts"], ts(7, day=1))

    def test_very_hot_water_needs_no_grid_heating(self):
        result = plan(ts(5), 62.0)
        self.assertEqual(result["status"], "AUCUN_BESOIN")
        self.assertIsNone(result["start_ts"])

    def test_heating_in_progress(self):
        result = plan(ts(5), 40.0, boiler_on=True)
        self.assertEqual(result["status"], "EN_COURS")

    def test_hc_disabled_manual_and_sensor_missing(self):
        self.assertEqual(plan(ts(5), 40.0, settings=dict(SETTINGS, boiler_allow_hc=False))["status"], "HC_DESACTIVE")
        self.assertEqual(plan(ts(5), 40.0, mode="Manuel")["status"], "MANUEL")
        self.assertEqual(plan(ts(5), None)["status"], "SONDE_INDISPONIBLE")
        self.assertEqual(plan(ts(5), 40.0, settings=dict(SETTINGS, boiler_enabled=False))["status"], "DESACTIVE")

    def test_lane_carries_schedule(self):
        schedule = plan(ts(5), 40.0)
        lane = boiler_lane(None, [[ts(-2), ts(7)]], source="HEURES_CREUSES", schedule=schedule)
        self.assertEqual(lane["start_ts"], schedule["start_ts"])
        self.assertEqual(lane["status"], "PROGRAMME")
        self.assertEqual(lane["segments"], [[schedule["start_ts"], schedule["end_ts"]]])
        self.assertEqual(lane["priority_rank"], 1)

    def test_lane_from_flexible_planner_segments(self):
        lane = boiler_lane(
            {"decision": "WAIT", "segments": [{"start": "2026-11-28T01:00:00+00:00", "end": "2026-11-28T02:00:00+00:00"}]},
            None, source="PLANIFICATEUR_CHARGES", heating_min=50,
        )
        self.assertEqual(lane["status"], "PROGRAMME")
        self.assertEqual(lane["start_ts"], ts(1))
        self.assertEqual(lane["heating_min"], 50)


if __name__ == "__main__":
    unittest.main()
