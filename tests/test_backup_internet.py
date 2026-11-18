"""Coupure Internet : sondage, anti-rebond, boiler coupé et rétablissement des prises."""
from __future__ import annotations

import asyncio
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy.const import BOILER_NONE, BOILER_STOP, DEFAULT_SETTINGS  # noqa: E402
from foxcat_energy.domain.engine import backup as bk  # noqa: E402
from foxcat_energy.domain.engine.models import EnergySnapshot  # noqa: E402

T0 = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)


def at(seconds: float) -> datetime:
    return T0 + timedelta(seconds=seconds)


class MonitorTests(unittest.TestCase):
    def make(self):
        return bk.ConnectivityMonitor(offline_after_s=120.0, recover_after_s=60.0)

    def test_starts_online_and_stays_online_while_probes_succeed(self):
        m = self.make()
        self.assertTrue(m.online)
        self.assertIsNone(m.observe(True, at(0)))

    def test_short_outage_is_ignored(self):
        m = self.make()
        for t in (0, 30, 60, 90):
            self.assertIsNone(m.observe(False, at(t)))
        self.assertIsNone(m.observe(True, at(100)))     # revenu avant 120 s
        self.assertTrue(m.online)

    def test_long_outage_goes_offline_once(self):
        m = self.make()
        transitions = [m.observe(False, at(t)) for t in (0, 30, 60, 90, 120, 150)]
        self.assertEqual(transitions.count(bk.TRANSITION_OFFLINE), 1)
        self.assertFalse(m.online)

    def test_flapping_connection_does_not_return_online_too_early(self):
        m = self.make()
        for t in (0, 120):
            m.observe(False, at(t))
        self.assertFalse(m.online)
        m.observe(True, at(150))
        m.observe(False, at(180))                       # rechute : le chrono de retour repart
        m.observe(True, at(210))
        self.assertIsNone(m.observe(True, at(240)))
        self.assertFalse(m.online)
        self.assertEqual(m.observe(True, at(280)), bk.TRANSITION_ONLINE)
        self.assertTrue(m.online)

    def test_state_survives_a_restart(self):
        m = self.make()
        for t in (0, 120):
            m.observe(False, at(t))
        other = self.make()
        other.restore(m.dump())
        self.assertFalse(other.online)
        self.assertIsNotNone(other.since)

    def test_garbage_restore_keeps_defaults(self):
        m = self.make()
        m.restore("n'importe quoi")
        m.restore({"online": True, "since": "pas une date"})
        self.assertTrue(m.online)
        self.assertIsNone(m.since)


class ProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_open_port_means_online(self):
        server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        try:
            self.assertTrue(await bk.probe_internet([("127.0.0.1", port)], timeout=1.0))
        finally:
            server.close()
            await server.wait_closed()

    async def test_closed_port_means_offline(self):
        server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        server.close()
        await server.wait_closed()
        self.assertFalse(await bk.probe_internet([("127.0.0.1", port)], timeout=1.0))

    async def test_one_reachable_host_is_enough(self):
        server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0)
        good = server.sockets[0].getsockname()[1]
        try:
            self.assertTrue(await bk.probe_internet([("127.0.0.1", 1), ("127.0.0.1", good)], timeout=1.0))
        finally:
            server.close()
            await server.wait_closed()


def snap(temp, *, on=False, safety=None):
    return EnergySnapshot(
        timestamp=T0, pv_w=0.0, house_w=500.0, export_w=0.0, import_w=500.0, grid_net_w=-500.0,
        boiler_temp_c=temp, boiler_safety_temp_c=temp if safety is None else safety, boiler_power_w=0.0,
        inverter_power_w=0.0, boiler_on=on, boiler_setpoint_c=45.0, machine_active=False,
    )


class BackupBoilerTests(unittest.TestCase):
    def test_running_boiler_is_cut_whatever_its_temperature(self):
        for temp in (30.0, 44.0, 50.0):
            intent = bk.backup_boiler_intent(snap(temp, on=True), DEFAULT_SETTINGS)
            self.assertEqual(intent.action, BOILER_STOP)
            self.assertEqual(intent.origin, "BACKUP_BOILER_COUPE")

    def test_piege_cold_tank_is_not_heated_in_backup(self):
        self.assertEqual(bk.backup_boiler_intent(snap(30.0, on=False), DEFAULT_SETTINGS).action, BOILER_NONE)

    def test_idle_boiler_stays_idle(self):
        self.assertEqual(bk.backup_boiler_intent(snap(48.0), DEFAULT_SETTINGS).action, BOILER_NONE)


class RestoreTests(unittest.TestCase):
    def test_only_usable_states_are_saved(self):
        saved = bk.capture_socket_states({"a": "on", "b": "off", "c": "unavailable", "d": None})
        self.assertEqual(saved, {"a": "on", "b": "off"})

    def test_machine_held_off_before_the_outage_is_switched_off_again(self):
        plan = bk.plan_restore({"washer": "off", "dryer": "on"}, {"washer": "on", "dryer": "on"}, [])
        self.assertEqual(plan, {"washer": "off"})

    def test_piege_running_cycle_is_never_cut_on_return(self):
        plan = bk.plan_restore({"washer": "off"}, {"washer": "on"}, ["washer"])
        self.assertEqual(plan, {})

    def test_nothing_to_do_when_states_already_match(self):
        self.assertEqual(bk.plan_restore({"washer": "on"}, {"washer": "on"}, []), {})

    def test_unknown_current_state_still_restores(self):
        self.assertEqual(bk.plan_restore({"washer": "off"}, {"washer": None}, []), {"washer": "off"})

    def test_status_view_is_serialisable(self):
        view = bk.status_view(online=False, since=T0, active=True, enabled=True, saved={"washer": "off"})
        self.assertEqual(view["since"], T0.isoformat())
        self.assertTrue(view["backup_active"])


if __name__ == "__main__":
    unittest.main()
