"""A-03 : un réglage que le moteur ne lit pas doit être déclaré inactif (et inversement)."""
from __future__ import annotations

import re
import sys
import types
import unittest
from pathlib import Path

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"
package = types.ModuleType("foxcat_energy")
package.__path__ = [str(COMPONENT)]
sys.modules.setdefault("foxcat_energy", package)

from foxcat_energy.const import (  # noqa: E402
    INACTIVE_SETTING_REASON,
    INACTIVE_SETTINGS,
    NUMBER_DEFINITIONS,
    SWITCH_DEFINITIONS,
)

# Fichiers qui déclarent ou exposent un réglage sans le lire.
_DECLARATIONS = {"const.py", "number.py", "switch.py"}
# Code inatteignable depuis le réglage `mode` (voir A-02) : une lecture ici ne compte pas.
_DEAD_CODE = {"ecs_solar.py", "dynamic.py", "flexible_boiler.py"}


def _sources() -> dict[str, str]:
    return {
        str(path.relative_to(COMPONENT)): path.read_text(encoding="utf-8")
        for path in COMPONENT.rglob("*.py")
        if "__pycache__" not in path.parts
    }


class InactiveSettingsTests(unittest.TestCase):
    def test_every_inactive_key_is_a_real_entity(self):
        for key in INACTIVE_SETTINGS:
            self.assertTrue(key in NUMBER_DEFINITIONS or key in SWITCH_DEFINITIONS, key)

    def test_a_setting_read_by_no_code_must_be_declared_inactive(self):
        sources = _sources()
        for key in [*NUMBER_DEFINITIONS, *SWITCH_DEFINITIONS]:
            readers = [
                name for name, text in sources.items()
                if Path(name).name not in _DECLARATIONS and re.search(rf"[\"']{re.escape(key)}[\"']", text)
            ]
            live = [name for name in readers if Path(name).name not in _DEAD_CODE]
            # Le calibre et la tension du disjoncteur sont lus via les constantes CONF_MAIN_BREAKER_*.
            if key in {"main_breaker_current_a", "main_breaker_voltage_v"}:
                continue
            if not live:
                self.assertIn(key, INACTIVE_SETTINGS, f"{key} n'est lu par aucun code actif : à déclarer inactif")

    def test_an_actively_read_setting_is_not_marked_inactive(self):
        sources = _sources()
        # Lus seulement par des méthodes du coordinateur qui ne sont jamais appelées (A-02) : exclus de la recherche.
        never_called = {"pri_boiler_settle_s", "dynamic_negative_price_charge_enabled",
                        "dynamic_grid_charge_threshold_eur_kwh"}
        for key in INACTIVE_SETTINGS - never_called:
            live = [
                name for name, text in sources.items()
                if Path(name).name not in _DECLARATIONS | _DEAD_CODE and re.search(rf"[\"']{re.escape(key)}[\"']", text)
            ]
            self.assertEqual(live, [], f"{key} est lu par du code actif : ne pas le déclarer inactif")

    def test_entities_apply_the_inactive_flag(self):
        for name in ("number.py", "switch.py"):
            text = (COMPONENT / name).read_text(encoding="utf-8")
            self.assertIn("INACTIVE_SETTINGS", text)
            self.assertIn("_attr_entity_registry_enabled_default = False", text)
            self.assertIn("EntityCategory.DIAGNOSTIC", text)
            self.assertIn('"statut": "inactif"', text)
        self.assertIn("Sans effet", INACTIVE_SETTING_REASON)

    def test_unread_form_setting_was_removed_from_the_engine(self):
        # `step_pct` (pri_step_percent) était calculé sans être utilisé.
        self.assertNotIn("pri_step_percent", (COMPONENT / "runtime" / "inverter_core.py").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
