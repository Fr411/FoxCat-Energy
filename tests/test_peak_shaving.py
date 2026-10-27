"""Tests de l'écrêtage de pointe configurable (peak_shaving.py + menu EMS)."""
from __future__ import annotations

import json
from pathlib import Path
import unittest

from foxcat_energy import peak_shaving as peak
from foxcat_energy.const import (
    CONF_MAIN_BREAKER_CURRENT_A,
    CONF_MAIN_BREAKER_VOLTAGE_V,
    DEFAULT_SETTINGS,
)
from foxcat_energy.vpp import evaluate_v2h

COMPONENT = Path(__file__).resolve().parents[1] / "custom_components" / "foxcat_energy"

PEAK_FORM_KEYS = {
    peak.CONF_PEAK_ENABLED,
    CONF_MAIN_BREAKER_CURRENT_A,
    CONF_MAIN_BREAKER_VOLTAGE_V,
    peak.CONF_PEAK_PHASES,
    peak.CONF_PEAK_MEASURE_BASIS,
    peak.CONF_PEAK_TRIGGER_RATIO_PCT,
    peak.CONF_PEAK_TRIGGER_W,
    peak.CONF_PEAK_RELEASE_RATIO_PCT,
    peak.CONF_PEAK_RELEASE_W,
    peak.CONF_PEAK_CONFIRM_FRAMES,
    peak.CONF_PEAK_RELEASE_FRAMES,
    peak.CONF_PEAK_SHED_BOILER,
    peak.CONF_PEAK_SHED_MACHINES,
    peak.CONF_PEAK_RELEASE_INVERTER,
    peak.CONF_PEAK_BLOCK_FLEXIBLE,
    peak.CONF_PEAK_V2H_ASSIST,
    peak.CONF_PEAK_V2H_TARGET_RATIO_PCT,
}


def _cfg(**settings) -> peak.PeakShavingConfig:
    return peak.PeakShavingConfig.from_settings(settings)


def _run(cfg, measures, *, active=False):
    """Rejoue une série de mesures ; retourne la liste (index, événement)."""
    high = low = 0
    events = []
    for index, measured in enumerate(measures):
        step = peak.evaluate_step(
            cfg, active=active, measured_w=measured, high_frames=high, low_frames=low
        )
        high, low = step.high_frames, step.low_frames
        if step.event == peak.EVENT_TRIGGER:
            active = True
            events.append((index, step.event))
        elif step.event == peak.EVENT_RELEASE:
            active = False
            events.append((index, step.event))
    return events


class LegacyBehaviourTests(unittest.TestCase):
    """Les défauts doivent reproduire exactement FoxCat <= 1.7.6."""

    def test_trigger_is_ninety_percent_of_breaker(self) -> None:
        cfg = _cfg(**{CONF_MAIN_BREAKER_CURRENT_A: 25, CONF_MAIN_BREAKER_VOLTAGE_V: 230})
        self.assertEqual(peak.breaker_limit_w(cfg), 5750.0)
        self.assertAlmostEqual(peak.trigger_w(cfg), 5175.0)

    def test_without_breaker_uses_absolute_threshold_and_two_frames(self) -> None:
        cfg = _cfg(high_load_shed_enabled=True)
        self.assertIsNone(peak.breaker_limit_w(cfg))
        self.assertEqual(peak.trigger_w(cfg), 5000.0)
        self.assertEqual(peak.required_confirm_frames(cfg), 2)
        self.assertEqual(_run(cfg, [6000, 6000]), [(1, peak.EVENT_TRIGGER)])
        self.assertEqual(_run(cfg, [6000, 100, 6000]), [])

    def test_with_breaker_one_frame_triggers(self) -> None:
        cfg = _cfg(**{CONF_MAIN_BREAKER_CURRENT_A: 25})
        self.assertEqual(peak.required_confirm_frames(cfg), 1)
        self.assertEqual(_run(cfg, [6000]), [(0, peak.EVENT_TRIGGER)])

    def test_release_needs_five_low_frames_by_default(self) -> None:
        cfg = _cfg(high_load_shed_enabled=True)
        events = _run(cfg, [3000] * 6, active=True)
        self.assertEqual(events, [(4, peak.EVENT_RELEASE)])
        # Une trame haute remet le compteur à zéro.
        events = _run(cfg, [3000, 3000, 3000, 3000, 4000, 3000, 3000], active=True)
        self.assertEqual(events, [])

    def test_default_settings_match_module_defaults(self) -> None:
        for key, value in peak.DEFAULTS.items():
            self.assertIn(key, DEFAULT_SETTINGS, key)
            self.assertEqual(DEFAULT_SETTINGS[key], value, key)
        self.assertEqual(DEFAULT_SETTINGS[peak.CONF_PEAK_TRIGGER_W], 5000.0)
        self.assertEqual(DEFAULT_SETTINGS[peak.CONF_PEAK_RELEASE_W], 3500.0)

    def test_all_menu_fields_are_known_settings(self) -> None:
        # _entry_option_settings ne retient que les clés présentes dans DEFAULT_SETTINGS.
        for key in PEAK_FORM_KEYS:
            self.assertIn(key, DEFAULT_SETTINGS, key)


class HysteresisAndConfigurationTests(unittest.TestCase):
    def test_release_is_always_below_trigger(self) -> None:
        # 10 A : déclenchement 2070 W alors que le réarmement absolu par défaut est 3500 W.
        cfg = _cfg(**{CONF_MAIN_BREAKER_CURRENT_A: 10})
        self.assertAlmostEqual(peak.trigger_w(cfg), 2070.0)
        self.assertLessEqual(peak.release_w(cfg), 2070.0 * 0.95 + 1e-9)
        self.assertLess(peak.release_w(cfg), peak.trigger_w(cfg))

    def test_release_ratio_replaces_absolute_with_breaker(self) -> None:
        cfg = _cfg(**{CONF_MAIN_BREAKER_CURRENT_A: 40, peak.CONF_PEAK_RELEASE_RATIO_PCT: 60})
        self.assertAlmostEqual(peak.release_w(cfg), 40 * 230 * 0.60)

    def test_phases_multiply_capacity(self) -> None:
        cfg = _cfg(**{CONF_MAIN_BREAKER_CURRENT_A: 25, peak.CONF_PEAK_PHASES: 3})
        self.assertEqual(peak.breaker_limit_w(cfg), 25 * 230 * 3)

    def test_custom_trigger_ratio_and_frames(self) -> None:
        cfg = _cfg(**{
            CONF_MAIN_BREAKER_CURRENT_A: 25,
            peak.CONF_PEAK_TRIGGER_RATIO_PCT: 80,
            peak.CONF_PEAK_CONFIRM_FRAMES: 3,
            peak.CONF_PEAK_RELEASE_FRAMES: 2,
        })
        self.assertAlmostEqual(peak.trigger_w(cfg), 4600.0)
        self.assertEqual(_run(cfg, [5000, 5000, 5000]), [(2, peak.EVENT_TRIGGER)])
        self.assertEqual(_run(cfg, [1000, 1000], active=True), [(1, peak.EVENT_RELEASE)])

    def test_grid_import_basis_ignores_solar_covered_load(self) -> None:
        legacy = _cfg(**{CONF_MAIN_BREAKER_CURRENT_A: 25})
        grid = _cfg(**{CONF_MAIN_BREAKER_CURRENT_A: 25, peak.CONF_PEAK_MEASURE_BASIS: "grid_import"})
        # Maison 6500 W, dont 4500 W couverts par le solaire : import 2000 W.
        self.assertTrue(peak.peak_signal(_cfg(high_load_shed_enabled=True, **{CONF_MAIN_BREAKER_CURRENT_A: 25}),
                                         peak.measured_power_w(legacy, house_w=6500, import_w=2000)))
        self.assertEqual(peak.measured_power_w(grid, house_w=6500, import_w=2000), 2000)
        self.assertEqual(peak.measured_power_w(grid, house_w=6500, import_w=-300), 0.0)

    def test_invalid_values_fall_back_to_safe_defaults(self) -> None:
        cfg = _cfg(**{
            CONF_MAIN_BREAKER_CURRENT_A: "abc",
            CONF_MAIN_BREAKER_VOLTAGE_V: 0,
            peak.CONF_PEAK_TRIGGER_RATIO_PCT: float("nan"),
            peak.CONF_PEAK_MEASURE_BASIS: "n'importe quoi",
            peak.CONF_PEAK_SHED_BOILER: "oui",
            peak.CONF_PEAK_RELEASE_FRAMES: 999,
        })
        self.assertIsNone(peak.breaker_limit_w(cfg))
        self.assertEqual(cfg.breaker_voltage_v, 230.0)
        self.assertEqual(cfg.trigger_ratio, 0.90)
        self.assertEqual(cfg.measure_basis, peak.BASIS_HOUSE)
        self.assertTrue(cfg.shed_boiler)
        self.assertEqual(cfg.release_frames, 30)

    def test_settings_override_config_entry_values(self) -> None:
        cfg = peak.PeakShavingConfig.from_settings(
            {CONF_MAIN_BREAKER_CURRENT_A: 32},
            {CONF_MAIN_BREAKER_CURRENT_A: 20, CONF_MAIN_BREAKER_VOLTAGE_V: 240},
        )
        self.assertEqual(cfg.breaker_current_a, 32.0)
        self.assertEqual(cfg.breaker_voltage_v, 240.0)

    def test_validation_flags_inconsistent_thresholds(self) -> None:
        bad_ratio = _cfg(**{
            CONF_MAIN_BREAKER_CURRENT_A: 25,
            peak.CONF_PEAK_TRIGGER_RATIO_PCT: 80,
            peak.CONF_PEAK_RELEASE_RATIO_PCT: 85,
        })
        self.assertIn("peak_release_ratio_too_high", peak.validate(bad_ratio))
        bad_abs = _cfg(**{peak.CONF_PEAK_TRIGGER_W: 3000, peak.CONF_PEAK_RELEASE_W: 3500})
        self.assertIn("peak_release_not_below_trigger", peak.validate(bad_abs))
        self.assertEqual(peak.validate(_cfg()), [])


class V2HRatiosTests(unittest.TestCase):
    BASE = dict(
        enabled=True, price_status="NORMAL", breaker_limit_w=5750.0,
        max_power_w=5000.0, soc_pct=80.0, min_soc_pct=25.0,
    )

    def test_default_ratios_are_unchanged(self) -> None:
        decision = evaluate_v2h(house_w=5300.0, **self.BASE)
        self.assertTrue(decision["peak_shaving"])
        self.assertAlmostEqual(decision["peak_trigger_w"], 5175.0)
        self.assertAlmostEqual(decision["target_power_w"], 5300.0 - 5750.0 * 0.8)

    def test_custom_ratios_move_trigger_and_target(self) -> None:
        decision = evaluate_v2h(house_w=4700.0, trigger_ratio=0.8, target_ratio=0.7, **self.BASE)
        self.assertTrue(decision["peak_shaving"])
        self.assertAlmostEqual(decision["peak_trigger_w"], 4600.0)
        self.assertAlmostEqual(decision["target_power_w"], 4700.0 - 5750.0 * 0.7)

    def test_peak_assist_can_be_disabled_without_losing_tariff_shield(self) -> None:
        off = evaluate_v2h(house_w=5600.0, peak_assist=False, **self.BASE)
        self.assertFalse(off["peak_shaving"])
        self.assertFalse(off["active"])
        shield = evaluate_v2h(
            house_w=2000.0, peak_assist=False, **{**self.BASE, "price_status": "TRÈS ÉLEVÉ"}
        )
        self.assertTrue(shield["tariff_shield"])
        self.assertTrue(shield["active"])


class TranslationTests(unittest.TestCase):
    def _step(self, relative: str) -> dict:
        data = json.loads((COMPONENT / relative).read_text(encoding="utf-8"))
        return data["options"]

    def test_every_menu_field_is_translated_in_both_files(self) -> None:
        for relative in ("strings.json", "translations/fr.json"):
            options = self._step(relative)
            step = options["step"]["peak_shaving"]
            self.assertEqual(set(step["data"]), PEAK_FORM_KEYS, relative)
            self.assertTrue(set(step["data_description"]) <= set(step["data"]), relative)
            self.assertIn("peak_shaving", options["step"]["ems"]["menu_options"], relative)
            for code in peak.validate(_cfg(**{peak.CONF_PEAK_TRIGGER_W: 3000, peak.CONF_PEAK_RELEASE_W: 4000})):
                self.assertIn(code, options["error"], relative)
            for code in ("peak_release_ratio_too_high", "peak_release_not_below_trigger", "peak_trigger_missing"):
                self.assertIn(code, options["error"], relative)

    def test_options_flow_exposes_the_peak_shaving_step(self) -> None:
        source = (COMPONENT / "config_flow.py").read_text(encoding="utf-8")
        self.assertIn("async def async_step_peak_shaving", source)
        self.assertIn('"peak_shaving": _peak_shaving_schema', source)
        self.assertIn('menu_options=["ems_core", "ia", "peak_shaving", "init"]', source)


if __name__ == "__main__":
    unittest.main()
