"""Scénarios d'économie avec pièges : FoxCat est comparé à un comportement naïf (« sans FoxCat »).

Chaque scénario rejoue des décisions réelles (optimiseur économique, planificateur de charges,
boiler dynamique, PRI) sur des courbes de prix fabriquées. Les pièges vérifient que FoxCat ne
« gagne » pas en dégradant le confort ni en attendant sans raison.
Lancer le rapport lisible : python3 tests/test_scenarios_economie.py
"""
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

from foxcat_energy.const import BOILER_HEAT_45, BOILER_STOP, DEFAULT_SETTINGS, TARIFF_DYNAMIC  # noqa: E402
from foxcat_energy.domain.engine.models import BoilerIntent, EnergySnapshot  # noqa: E402
from foxcat_energy.domain.engine.modes.dynamic_boiler_v2 import evaluate_dynamic_boiler_v2  # noqa: E402
from foxcat_energy.domain.engine.pri import decide_dynamic  # noqa: E402
from foxcat_energy.domain.loads.flexible_load_planner import build_flexible_load_plan  # noqa: E402
from foxcat_energy.domain.loads.machines import MachineDefinition  # noqa: E402
from foxcat_energy.domain.pricing.economic_optimizer import (  # noqa: E402
    PricePoint, average_price, evaluate_market, recommend_flexible_load,
)

UTC = timezone.utc
DAY = datetime(2026, 11, 16, 0, 0, tzinfo=UTC)
SETTINGS = dict(DEFAULT_SETTINGS)
SETTINGS.update(mode="Dynamique", price_source="Dynamique", tariff_regime="Dynamique")


def snap(now, *, export_w=0.0, temp=50.0, on=False, pv_w=0.0):
    return EnergySnapshot(
        timestamp=now, pv_w=pv_w, house_w=500.0, export_w=export_w, import_w=500.0,
        grid_net_w=export_w - 500.0, boiler_temp_c=temp, boiler_safety_temp_c=temp,
        boiler_power_w=1800.0 if on else 0.0, inverter_power_w=pv_w, boiler_on=on,
        boiler_setpoint_c=45.0, machine_active=False,
    )


def points(curve):
    return [PricePoint(DAY + timedelta(hours=h), p, "SCENARIO") for h, p in enumerate(curve)]


def hours(*blocks):
    """hours((6, 0.12), (3, 0.20)) → 6 heures à 0,12 puis 3 heures à 0,20."""
    out = []
    for count, price in blocks:
        out += [price] * count
    return out


# Courbe type Day-Ahead sur 48 h : nuit creuse, pic du soir, nuit suivante creuse.
DAY_AHEAD = hours((6, 0.12), (3, 0.20), (8, 0.18), (4, 0.42), (3, 0.22)) + hours((6, 0.10), (18, 0.20))


def run_machine(curve, request_h, deadline_h, *, export_w=0.0, export_value=0.04, energy=1.2,
                duration=2.0, active=False, pv_w=0.0, open_windows=True):
    """Interroge le planificateur de charges (décideur en tarif dynamique) toutes les 15 min."""
    pts = points(curve)
    request = DAY + timedelta(hours=request_h, minutes=5)
    deadline = DAY + timedelta(hours=deadline_h)
    windows = dict(on_1="00:00:00", off_1="23:59:00", on_2="00:00:00", off_2="23:59:00") if open_windows else {}
    machine = MachineDefinition("washer", "Lave-linge", "switch.washer", cycle_duration_minutes=duration * 60,
                                deadline=f"{deadline.hour:02d}:00", max_delay_hours=24, **windows)
    learning = {"washer": {"average_duration_s_10": duration * 3600, "average_energy_wh_10": energy * 1000}}
    settings = dict(SETTINGS, **{machine.setting_key: True})
    export_pts = [] if export_value is None else points([export_value] * len(curve))
    now, start, last = request, None, None
    while now < deadline:
        s = snap(now, export_w=export_w, pv_w=pv_w)
        plan = build_flexible_load_plan(
            now=now, snapshot=s, settings=settings, import_points=pts, export_points=export_pts,
            machines=[machine], learning=learning, cycles={"washer": {"protected": active}} if active else {},
            price_analysis={"active": True, "mode": "DYNAMIQUE"}, solar_forecast=None,
        )
        last = plan["machines"]["washer"]
        if last["allow_start_now"]:
            start = now
            break
        now += timedelta(minutes=15)

    def cost(at):
        return None if at is None else energy * (average_price(pts, at, duration) or 0.0)

    naive = cost(request)
    smart = cost(start)
    return {"start": start, "request": request, "naive": naive, "smart": smart, "last": last,
            "saving": None if smart is None else naive - smart}


def boiler_day(curve, *, smart=True, with_end=False):
    """24 h de ballon : douches à 7 h et 19 h. Retourne (coût €, température mini, température aux douches)."""
    pts = points(curve)
    temp, on, cost, coldest, at_shower = 50.0, False, 0.0, 99.0, []
    for q in range(96):
        now = DAY + timedelta(minutes=15 * q)
        h = q // 4
        if q % 4 == 0 and h in (7, 19):
            at_shower.append(round(temp, 1))
            temp -= 6.0
        if smart:
            prices = {"regime": TARIFF_DYNAMIC, "active_buy": curve[h], "export_value": 0.04}
            market = evaluate_market(now=now, snapshot=snap(now, temp=temp, on=on), prices=prices,
                                     settings=SETTINGS, import_points=pts, export_points=[])
            intent = evaluate_dynamic_boiler_v2(
                snap(now, temp=temp, on=on), BoilerIntent("AUCUNE", "base", "AUCUNE"), SETTINGS,
                {"decision": market.as_dict()},
            )
            if intent.action == BOILER_HEAT_45:
                on = True
            elif intent.action == BOILER_STOP:
                on = False
            if on and temp >= 45.0:
                on = False
        else:  # thermostat classique : reprise à 43 °C, arrêt à 45 °C, sans regarder le prix
            if temp < 43.0:
                on = True
            elif temp >= 45.0:
                on = False
        if on:
            cost += 1.8 * 0.25 * curve[h]
            temp += 7.7 * 0.25
        temp -= 0.25 * 0.25
        coldest = min(coldest, temp)
    return (cost, coldest, at_shower, temp) if with_end else (cost, coldest, at_shower)


def boiler_end_temp(*, smart):
    """Température du ballon à 24 h (même simulation que boiler_day)."""
    return boiler_day(DAY_AHEAD, smart=smart, with_end=True)[3]


class MachineScenarios(unittest.TestCase):
    def test_01_pic_du_soir_le_cycle_attend_la_nuit(self):
        r = run_machine(DAY_AHEAD, 18, 31)           # demandé à 18 h, à finir avant 7 h
        self.assertIsNotNone(r["start"], "le cycle ne doit pas rester bloqué")
        self.assertGreater(r["start"] - r["request"], timedelta(hours=2))
        self.assertGreater(r["saving"], 0.15)         # 1,2 kWh × (0,42 − 0,10)

    def test_02_piege_prix_plat_pas_d_attente_inutile(self):
        r = run_machine([0.20] * 48, 18, 31)
        self.assertEqual(r["start"], r["request"])

    def test_03_piege_le_pic_arrive_apres_on_demarre_maintenant(self):
        curve = hours((10, 0.12), (4, 0.45), (34, 0.20))
        r = run_machine(curve, 8, 30)                 # 8 h : bas de courbe, pic à 10-14 h
        self.assertEqual(r["start"], r["request"])

    def test_04_piege_prix_negatif_on_consomme(self):
        curve = hours((10, 0.20), (3, -0.05), (35, 0.20))
        r = run_machine(curve, 10, 30)
        self.assertEqual(r["start"], r["request"])

    def test_05_piege_prix_indisponible_le_recommandeur_refuse_de_deviner(self):
        pts = points(DAY_AHEAD)
        now = DAY + timedelta(hours=18, minutes=5)
        out = recommend_flexible_load(
            now=now, snapshot=snap(now), prices={"regime": TARIFF_DYNAMIC, "active_buy": None},
            settings=SETTINGS, import_points=pts, duration_hours=2.0, energy_kwh=1.2, active=False,
        )
        self.assertEqual(out["decision"], "PRIX_INDISPONIBLE")
        self.assertFalse(out["allow_start"])

    def test_06_piege_soleil_gratuit_meilleur_que_la_nuit_creuse(self):
        curve = hours((10, 0.30), (4, 0.25), (10, 0.30)) + hours((6, 0.10), (18, 0.20))
        r = run_machine(curve, 12, 31, export_w=2500.0, pv_w=4000.0)   # surplus 2,5 kW, injection 0,04 €
        self.assertEqual(r["start"], r["request"])

    def test_06b_piege_injection_penalisee_le_surplus_est_a_consommer_meme_si_la_nuit_est_moins_chere(self):
        curve = hours((10, 0.15), (4, 0.15), (10, 0.15)) + hours((6, 0.10), (18, 0.20))
        r = run_machine(curve, 12, 31, export_w=2500.0, pv_w=4000.0, export_value=-0.05)   # injecter coûte 5 c€/kWh
        self.assertEqual(r["start"], r["request"])

    def test_06c_piege_injection_penalisee_mais_pas_de_surplus_on_attend_la_nuit(self):
        curve = hours((10, 0.15), (4, 0.15), (10, 0.15)) + hours((6, 0.10), (18, 0.20))
        r = run_machine(curve, 12, 31, export_w=0.0, pv_w=0.0, export_value=-0.05)
        self.assertGreater(r["start"] - r["request"], timedelta(hours=2))

    def test_06d_piege_surplus_partiel_ne_bat_pas_une_nuit_nettement_moins_chere(self):
        curve = hours((10, 0.30), (4, 0.30), (10, 0.30)) + hours((6, 0.10), (18, 0.20))
        r = run_machine(curve, 12, 31, export_w=300.0, pv_w=1500.0, export_value=0.04)   # machine de 600 W, 300 W de surplus
        self.assertGreater(r["start"] - r["request"], timedelta(hours=2))

    def test_06e_piege_prix_d_injection_inconnu_le_solaire_n_est_pas_suppose_gratuit(self):
        curve = hours((10, 0.30), (4, 0.30), (10, 0.30)) + hours((6, 0.10), (18, 0.20))
        r = run_machine(curve, 12, 31, export_w=2500.0, pv_w=4000.0, export_value=None)
        self.assertGreater(r["start"] - r["request"], timedelta(hours=2))

    def test_07_piege_cycle_en_cours_jamais_interrompu_au_pic(self):
        r = run_machine(DAY_AHEAD, 18, 31, active=True)      # cycle déjà lancé à 18 h, prix 0,42 €
        self.assertEqual(r["start"], r["request"])
        self.assertEqual(r["last"]["decision"], "CONTINUE")

    def test_08_piege_ecart_trop_faible_pas_de_report(self):
        curve = hours((18, 0.20), (4, 0.205), (26, 0.20))   # 0,5 c€ d'écart : sous le seuil de 2 c€
        r = run_machine(curve, 18, 31)
        self.assertEqual(r["start"], r["request"])

    def test_08b_piege_plages_horaires_par_defaut_respectees(self):
        # Plages par défaut 21 h 30-7 h et 10 h 30-17 h : demandé à 18 h, jamais lancé avant 21 h 30.
        r = run_machine([0.20] * 48, 18, 31, open_windows=False)
        self.assertIsNotNone(r["start"])
        self.assertGreaterEqual(r["start"].hour * 60 + r["start"].minute, 21 * 60 + 30)

    def test_09_piege_revente_chere_on_vend_puis_on_consomme_la_nuit(self):
        curve = hours((10, 0.30), (4, 0.25), (10, 0.30)) + hours((6, 0.10), (18, 0.20))
        r = run_machine(curve, 12, 31, export_w=2500.0, pv_w=4000.0, export_value=0.35)
        self.assertGreater(r["start"] - r["request"], timedelta(hours=2))
        self.assertGreater(r["saving"], 0.0)


class BoilerScenarios(unittest.TestCase):
    def test_10_boiler_dynamique_coute_moins_que_le_thermostat_et_garde_le_confort(self):
        smart_cost, smart_min, smart_showers = boiler_day(DAY_AHEAD, smart=True)
        naive_cost, naive_min, naive_showers = boiler_day(DAY_AHEAD, smart=False)
        self.assertLess(smart_cost, naive_cost)
        self.assertGreaterEqual(min(smart_showers), 40.0, f"douches à {smart_showers}")

    def test_11_piege_confort_pic_de_4h_ballon_jamais_sous_le_seuil_de_necessite(self):
        # Seuil de nécessité ECS de FoxCat : 38 °C (boiler_necessity_temp_c) ; marge d'un quart d'heure de chauffe.
        _, smart_min, _ = boiler_day(DAY_AHEAD, smart=True)
        self.assertGreaterEqual(smart_min, SETTINGS["boiler_necessity_temp_c"] - 1.0,
                                f"ballon descendu à {smart_min:.1f} °C pendant le pic")

    def test_11b_piege_l_economie_du_boiler_n_est_pas_du_confort_en_moins(self):
        """On rend au ballon la chaleur qui lui manque en fin de journée, au prix moyen du jour."""
        smart_cost, _, _ = boiler_day(DAY_AHEAD, smart=True)
        naive_cost, _, _ = boiler_day(DAY_AHEAD, smart=False)
        smart_end, naive_end = boiler_end_temp(smart=True), boiler_end_temp(smart=False)
        average_price_day = sum(DAY_AHEAD[:24]) / 24
        rattrapage = max(naive_end - smart_end, 0.0) * 0.234 * average_price_day   # 0,234 kWh par °C
        self.assertLess(smart_cost + rattrapage, naive_cost, f"fins de journée {smart_end:.1f} / {naive_end:.1f} °C")

    def test_12_piege_securite_thermique_prime_sur_le_prix_negatif(self):
        now = DAY + timedelta(hours=12)
        s = snap(now, temp=69.0, on=True)
        intent = evaluate_dynamic_boiler_v2(s, BoilerIntent("AUCUNE", "b", "AUCUNE"), SETTINGS, {"decision": {}})
        self.assertEqual(intent.action, BOILER_STOP)


class PriScenarios(unittest.TestCase):
    def test_13_injection_payante_pas_de_bridage_onduleur(self):
        s = snap(DAY + timedelta(hours=12), export_w=3000.0, pv_w=4000.0)
        self.assertEqual(decide_dynamic(s, 100, SETTINGS, 0.10, False).target_level, 100)

    def test_14_piege_injection_negative_on_bride_pour_ne_pas_payer(self):
        s = snap(DAY + timedelta(hours=12), export_w=3000.0, pv_w=4000.0)
        self.assertLess(decide_dynamic(s, 100, SETTINGS, -0.05, False).target_level, 100)

    def test_15_piege_injection_negative_mais_rien_n_est_injecte(self):
        s = snap(DAY + timedelta(hours=12), export_w=0.0, pv_w=0.0)
        self.assertEqual(decide_dynamic(s, 100, SETTINGS, -0.05, False).target_level, 100)


def report() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print()
    r = run_machine(DAY_AHEAD, 18, 31)
    print(f"Machine 1,2 kWh demandée à 18 h : démarre à {r['start']:%H:%M} (demain), "
          f"coût {r['smart']:.3f} € contre {r['naive']:.3f} € sans FoxCat, économie {r['saving']:.3f} €")
    print(f"  décision du planificateur à la fin : {r['last']['decision']}")
    sc, sm, sh = boiler_day(DAY_AHEAD, smart=True)
    nc, nm, nh = boiler_day(DAY_AHEAD, smart=False)
    print(f"Boiler 24 h : FoxCat {sc:.3f} € (mini {sm:.1f} °C, douches {sh}) ; thermostat {nc:.3f} € (mini {nm:.1f} °C, douches {nh})")
    print(f"  température à 24 h : FoxCat {boiler_end_temp(smart=True):.1f} °C, thermostat {boiler_end_temp(smart=False):.1f} °C")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(report())
