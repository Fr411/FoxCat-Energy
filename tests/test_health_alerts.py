"""Alertes de panne FoxCat : détection, gravité, temporisation."""
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

from foxcat_energy.domain import health as hl  # noqa: E402

T0 = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


def codes(**kwargs) -> dict[str, str]:
    return {alert.code: alert.severity for alert in hl.evaluate(hl.HealthInputs(**kwargs))}


class EvaluateTests(unittest.TestCase):
    def test_healthy_installation_has_no_alert(self):
        self.assertEqual(codes(boiler_configured=True, boiler_safety_temp_c=50.0), {})

    def test_blind_ems_is_critical(self):
        found = codes(snapshot_valid=False, missing_essential_sensors=("puissance réseau",))
        self.assertEqual(found.get("EMS_AVEUGLE"), hl.CRITICAL)

    def test_lost_metronome_is_critical_but_fallback_is_only_major(self):
        self.assertEqual(codes(metronome_status="PERDU").get("EMS_AVEUGLE"), hl.CRITICAL)
        self.assertEqual(codes(metronome_status="FALLBACK").get("METRONOME_SECOURS"), hl.MAJOR)

    def test_boiler_overheat_is_critical_and_immediate(self):
        alert = next(a for a in hl.evaluate(hl.HealthInputs(boiler_configured=True, boiler_safety_temp_c=69.0)))
        self.assertEqual((alert.code, alert.severity, alert.delay_s), ("BOILER_SURCHAUFFE", hl.CRITICAL, 0.0))

    def test_piege_overheat_alert_even_in_manual_mode_and_regulation_off(self):
        found = codes(boiler_configured=True, boiler_safety_temp_c=70.0, mode="Manuel", regulation_active=False)
        self.assertIn("BOILER_SURCHAUFFE", found)

    def test_dead_boiler_probe_is_critical(self):
        found = codes(boiler_configured=True, boiler_temp_ok=False, boiler_safety_temp_ok=True)
        self.assertEqual(found, {"BOILER_SONDE_HS": hl.CRITICAL})

    def test_piege_no_duplicate_when_the_safety_probe_is_also_dead(self):
        found = codes(boiler_configured=True, boiler_temp_ok=False, boiler_safety_temp_ok=False)
        self.assertEqual(found, {"BOILER_SONDE_SECURITE_HS": hl.CRITICAL})

    def test_piege_dead_probe_is_ignored_when_foxcat_is_not_driving_the_boiler(self):
        self.assertEqual(codes(boiler_configured=True, boiler_temp_ok=False, mode="Manuel"), {})
        self.assertEqual(codes(boiler_configured=True, boiler_temp_ok=False, regulation_active=False), {})
        self.assertEqual(codes(boiler_configured=False, boiler_temp_ok=False), {})

    def test_unreadable_inverter_relays_are_critical_only_when_pri_is_on(self):
        self.assertEqual(codes(pri_enabled=True, pri_relays_readable=False), {"PRI_ILLISIBLE": hl.CRITICAL})
        self.assertEqual(codes(pri_enabled=False, pri_relays_readable=False), {})

    def test_failed_command_is_critical_with_its_reason(self):
        alert = hl.evaluate(hl.HealthInputs(actuator_status="FAILED", actuator_error="switch indisponible"))[0]
        self.assertEqual(alert.code, "ACTIONNEUR_ECHEC")
        self.assertIn("switch indisponible", alert.detail)

    def test_major_alerts(self):
        found = codes(
            price_feed_state="DEGRADE", internet_online=False, unavailable_machines=("Lave-linge",),
            load_shed_active=True, legacy_conflict=True, coordinator_update_ok=False,
            missing_configured_entities=("sensor.pv",),
        )
        self.assertEqual(set(found), {
            "PRIX_INDISPONIBLES", "INTERNET_COUPE", "MACHINE_INDISPONIBLE", "DELESTAGE_ACTIF",
            "CONFLIT_AUTOMATISATION", "FOXCAT_EN_ERREUR", "ENTITE_INTROUVABLE",
        })
        self.assertTrue(all(severity == hl.MAJOR for severity in found.values()))

    def test_internet_alert_tells_whether_backup_is_active(self):
        on = hl.evaluate(hl.HealthInputs(internet_online=False, backup_active=True))[0]
        off = hl.evaluate(hl.HealthInputs(internet_online=False, backup_active=False))[0]
        self.assertIn("Backup est actif", on.detail)
        self.assertIn("n'est pas actif", off.detail)

    def test_piege_manual_mode_does_not_report_a_frozen_regulation(self):
        self.assertEqual(codes(snapshot_valid=False, mode="Manuel"), {})
        self.assertEqual(codes(snapshot_valid=False, regulation_active=False), {})


class TrackerTests(unittest.TestCase):
    def alert(self, delay=120.0, code="X", severity=hl.MAJOR):
        return hl.Alert(code, severity, "titre", "détail", delay_s=delay)

    def test_alert_appears_only_after_its_delay(self):
        tracker = hl.AlertTracker()
        visible, raised, _ = tracker.update([self.alert()], at(0))
        self.assertEqual((visible, raised), ([], set()))
        visible, raised, _ = tracker.update([self.alert()], at(119))
        self.assertEqual(visible, [])
        visible, raised, _ = tracker.update([self.alert()], at(121))
        self.assertEqual(raised, {"X"})
        self.assertEqual(visible[0]["code"], "X")

    def test_piege_micro_fault_never_notifies(self):
        tracker = hl.AlertTracker()
        tracker.update([self.alert()], at(0))
        visible, raised, cleared = tracker.update([], at(30))
        self.assertEqual((visible, raised, cleared), ([], set(), set()))

    def test_immediate_alert_is_visible_at_once(self):
        tracker = hl.AlertTracker()
        visible, raised, _ = tracker.update([self.alert(delay=0.0, severity=hl.CRITICAL)], at(0))
        self.assertEqual(raised, {"X"})
        self.assertEqual(hl.overall_status(visible), hl.CRITICAL)

    def test_alert_is_cleared_only_after_a_stable_return(self):
        tracker = hl.AlertTracker(clear_after_s=60.0)
        tracker.update([self.alert(delay=0.0)], at(0))
        visible, _, cleared = tracker.update([], at(30))
        self.assertEqual(len(visible), 1)               # encore visible : retour pas encore stable
        self.assertEqual(cleared, set())
        visible, _, cleared = tracker.update([], at(61))
        self.assertEqual((visible, cleared), ([], {"X"}))

    def test_piege_flapping_does_not_renotify(self):
        tracker = hl.AlertTracker(clear_after_s=60.0)
        tracker.update([self.alert(delay=0.0)], at(0))
        tracker.update([], at(20))
        _, raised, cleared = tracker.update([self.alert(delay=0.0)], at(40))
        self.assertEqual((raised, cleared), (set(), set()))

    def test_critical_alerts_are_listed_first(self):
        tracker = hl.AlertTracker()
        visible, _, _ = tracker.update(
            [self.alert(0.0, "A", hl.MAJOR), self.alert(0.0, "B", hl.CRITICAL)], at(0)
        )
        self.assertEqual([row["code"] for row in visible], ["B", "A"])

    def test_overall_status(self):
        self.assertEqual(hl.overall_status([]), "OK")
        self.assertEqual(hl.overall_status([{"severite": hl.MAJOR}]), hl.MAJOR)
        self.assertEqual(hl.overall_status([{"severite": hl.MAJOR}, {"severite": hl.CRITICAL}]), hl.CRITICAL)


if __name__ == "__main__":
    unittest.main()
