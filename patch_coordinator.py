import os

def patch_coordinator():
    filepath = "coordinator.py"
    if not os.path.exists(filepath):
        print("Fichier coordinator.py introuvable.")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    old_block = '''        if day_ahead.get("active"):
            for machine_id, plan in (day_ahead.get("machines") or {}).items():
                rec = recommendations.setdefault(machine_id, {})
                rec["allow_start"] = bool(plan.get("allow_start_now", False))
                rec["scheduler_decision"] = plan.get("decision")
                rec["scheduler_reason"] = plan.get("reason")
                rec["best_user_window_start"] = plan.get("best_start")
                rec["best_user_window_end"] = plan.get("best_end")
                rec["user_window_now"] = plan.get("user_window_now")
                rec["day_ahead_threshold_pct"] = day_ahead.get("threshold_pct")

        price_analysis = analyze_price_curve(now=now, import_points=import_points, export_points=export_points, settings=self.settings, tomorrow_available=tomorrow_available, current_buy=tariff.get("active_buy")) if tariff_dimensions(self.settings).dynamic else {"active":False,"mode":"INACTIF","state":"HORS_DYNAMIQUE","valid":True,"series":[]}
        planner = build_flexible_load_plan(now=now,snapshot=snap,settings=self.settings,import_points=import_points,export_points=export_points,machines=self.controllable_machines,learning=learning,cycles=cycles,price_analysis=price_analysis,solar_forecast=self.solar_forecast,boiler_thermal=boiler_thermal,boiler_user_override=str(self.core_state.get("boiler_user_override","AUTO")))
        for mid,plan in (planner.get("machines") or {}).items():
            recommendations.setdefault(mid,{})["allow_start"]=bool(plan.get("allow_start_now")); recommendations[mid]["scheduler_decision"]=plan.get("decision"); recommendations[mid]["scheduler_reason"]=plan.get("reason")'''

    new_block = '''        price_analysis = analyze_price_curve(now=now, import_points=import_points, export_points=export_points, settings=self.settings, tomorrow_available=tomorrow_available, current_buy=tariff.get("active_buy")) if tariff_dimensions(self.settings).dynamic else {"active":False,"mode":"INACTIF","state":"HORS_DYNAMIQUE","valid":True,"series":[]}
        planner = build_flexible_load_plan(now=now,snapshot=snap,settings=self.settings,import_points=import_points,export_points=export_points,machines=self.controllable_machines,learning=learning,cycles=cycles,price_analysis=price_analysis,solar_forecast=self.solar_forecast,boiler_thermal=boiler_thermal,boiler_user_override=str(self.core_state.get("boiler_user_override","AUTO")))
        
        # CORRECTION : Le planificateur V1.7.1 (flexible_load_plan) est désormais la SEULE
        # source de vérité. L'ancien scheduler n'est lu que pour préserver l'affichage front-end.
        if day_ahead.get("active"):
            for machine_id, plan in (day_ahead.get("machines") or {}).items():
                rec = recommendations.setdefault(machine_id, {})
                rec["best_user_window_start"] = plan.get("best_start")
                rec["best_user_window_end"] = plan.get("best_end")
                rec["user_window_now"] = plan.get("user_window_now")
                rec["day_ahead_threshold_pct"] = day_ahead.get("threshold_pct")

        for mid, plan in (planner.get("machines") or {}).items():
            rec = recommendations.setdefault(mid, {})
            rec["allow_start"] = bool(plan.get("allow_start_now", False))
            rec["scheduler_decision"] = plan.get("decision")
            rec["scheduler_reason"] = plan.get("reason")'''

    if old_block in content:
        new_content = content.replace(old_block, new_block)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("coordinator.py a été patché avec succès !")
    else:
        print("Le bloc à remplacer n'a pas été trouvé. Le fichier est peut-être déjà patché.")

if __name__ == "__main__":
    patch_coordinator()
