from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .const import TARIFF_DYNAMIC

NETWORK_COMPENSATION = "Compensation"
NETWORK_BILLED_EXPORT = "Injection tarifée"


@dataclass(slots=True)
class InverterDecision:
    current_level: int
    target_level: int
    action: str
    reason: str
    pv_limit_w: float
    pv_ratio: float
    pv_at_limit: bool
    more_solar_possible: bool
    max_solar_reached: bool
    score_current: float = 0.0
    score_target: float = 0.0
    house_target_level: int = 100
    estimated_house_w: float = 0.0
    target_pv_w: float = 0.0
    predicted_import_w: float = 0.0
    predicted_export_w: float = 0.0


class InverterCore:
    """Second cœur FoxCat : uniquement responsable de la puissance onduleur.

    Depuis 1.5.5, la politique ``Injection tarifée`` n'avance plus d'un palier
    à chaque battement. Le métronome garantit uniquement une trame fraîche.
    Sur cette trame, le moteur simule tous les paliers RRCR disponibles
    (0, 10, ..., 100 %) et commande directement le meilleur compromis réseau.
    """

    @staticmethod
    def _score_grid(
        import_w: float,
        export_w: float,
        *,
        import_target_w: float,
        import_max_w: float,
        export_max_w: float,
        weight_import: float,
        weight_export: float,
    ) -> float:
        """Score réseau : plus petit = meilleur.

        Le léger import est une cible et non une obligation absolue. Les sorties
        hors enveloppe (réinjection au-delà du maximum ou import excessif) sont
        fortement pénalisées pour éviter qu'un simple écart de quantification
        de 10 % ne choisisse un palier agressif.
        """
        import_w = max(float(import_w), 0.0)
        export_w = max(float(export_w), 0.0)
        base = abs(import_w - import_target_w) * weight_import
        base += export_w * weight_export
        if import_w > import_max_w:
            base += (import_w - import_max_w) * weight_import * 4.0
        if export_w > export_max_w:
            base += (export_w - export_max_w) * weight_export * 4.0
        return base

    @staticmethod
    def _nearest_level_for_power(power_w: float, inverter_w: float) -> int:
        if inverter_w <= 0:
            return 100
        raw = max(0.0, min(100.0, float(power_w) / inverter_w * 100.0))
        # RRCR FoxCat expose uniquement les paliers de 10 %.
        return max(0, min(100, int(round(raw / 10.0) * 10)))

    def decide(
        self,
        snapshot: Any,
        current_level: int,
        settings: dict[str, Any],
        network_policy: str,
        bus_state: dict[str, Any] | None = None,
        *,
        tariff_regime: str | None = None,
        dynamic_export_value_eur_kwh: float | None = None,
    ) -> InverterDecision:
        inverter_w = max(float(settings.get("inverter_power_w", 4000.0)), 1.0)
        step_pct = max(int(round(float(settings.get("pri_step_percent", 10.0)))), 10)
        tolerance_w = max(float(settings.get("pri_pv_compare_tolerance_w", 200.0)), 0.0)
        ratio_threshold = min(max(float(settings.get("pri_ceiling_ratio", 0.92)), 0.50), 1.0)

        current = max(0, min(100, int(current_level)))
        limit_w = inverter_w * current / 100.0
        pv_w = max(float(snapshot.pv_w), 0.0)
        ratio = (pv_w / limit_w) if limit_w > 0 else 0.0
        pv_at_limit = (
            current > 0
            and (pv_w >= max(limit_w - tolerance_w, 0.0) or ratio >= ratio_threshold)
        )
        max_solar = current > 0 and not pv_at_limit
        more_possible = current < 100 and pv_at_limit

        # Compensation : règle économique souveraine. Toute la production PV
        # disponible est libérée immédiatement ; le réseau sert de tampon.
        # Aucun calcul d'injection ne doit brider l'onduleur dans cette politique.
        if network_policy == NETWORK_COMPENSATION:
            target = 100
            return InverterDecision(
                current, target,
                "LIBERATION" if target > current else "MAINTIEN",
                "Compensation : onduleur libéré à 100 %, réseau utilisé comme tampon.",
                limit_w, ratio, pv_at_limit, more_possible, max_solar,
            )

        # DYNAMIQUE uniquement : la valeur économique normalisée de l'export
        # remplace le simple état binaire « Injection tarifée ». Une valeur
        # positive signifie une recette pour l'utilisateur; une valeur négative
        # signifie qu'il paie pour injecter. Règle souveraine 1.6.158 : une
        # réinjection rémunératrice libère toujours le PRI à 100 %, même si le
        # prédictif prix est coupé. Le kill-switch ne peut pas détruire un kWh
        # solaire qui possède une valeur de vente positive.
        if (
            tariff_regime == TARIFF_DYNAMIC
            and dynamic_export_value_eur_kwh is not None
            and dynamic_export_value_eur_kwh > 0.0
        ):
            target = 100
            return InverterDecision(
                current, target,
                "LIBERATION" if target > current else "MAINTIEN",
                f"Dynamique : export valorisé à {dynamic_export_value_eur_kwh:.4f} €/kWh, PRI libéré à 100 %.",
                limit_w, ratio, pv_at_limit, more_possible, max_solar,
            )

        # Si la valeur dynamique d'export est négative, ou si elle est nulle/
        # indisponible, le moteur prédictif ci-dessous conserve sa cible locale
        # de quasi-zéro injection. Les régimes non dynamiques passent également
        # exactement par ce chemin historique.
        # Injection tarifée : calcul prédictif du meilleur palier.
        export_limit = max(float(settings.get("network_billed_export_max_w", 50.0)), 0.0)
        import_target = max(float(settings.get("network_billed_import_target_w", 100.0)), 0.0)
        import_high = max(float(settings.get("network_billed_import_max_w", 250.0)), import_target)
        weight_import = max(float(settings.get("pri_weight_import", 1.0)), 0.01)
        weight_export = max(float(settings.get("pri_weight_export", 2.0)), 0.01)
        score_margin = max(float(settings.get("pri_score_margin", 25.0)), 0.0)

        export_w = max(float(snapshot.export_w), 0.0)
        import_w = max(float(snapshot.import_w), 0.0)

        # Bilan physique sur la même trame : PV + import = maison + export.
        # Cette valeur est préférable pour le calcul PRI car elle reste alignée
        # sur le compteur réseau qui donne le battement du métronome.
        estimated_house_w = max(pv_w + import_w - export_w, 0.0)
        target_pv_w = max(estimated_house_w - import_target, 0.0)
        house_target_level = self._nearest_level_for_power(target_pv_w, inverter_w)

        current_score = self._score_grid(
            import_w,
            export_w,
            import_target_w=import_target,
            import_max_w=import_high,
            export_max_w=export_limit,
            weight_import=weight_import,
            weight_export=weight_export,
        )

        # Lorsque le PV est sous le plafond actuel, sa puissance mesurée est une
        # bonne estimation du potentiel solaire disponible. Une remontée de PRI
        # ne peut alors rien apporter et la simulation la traite comme telle.
        # Si le PV touche le plafond (ou si le niveau vaut 0 %), le potentiel
        # supérieur est inconnu : on suppose qu'un palier supérieur peut remplir
        # son plafond. C'est sûr côté réseau car le plafond calculé reste dérivé
        # de la consommation maison et de l'import cible.
        # V1.6.150 : un import hors enveloppe autorise aussi une libération
        # immédiate du plafond PRI. Relever un plafond ne crée pas de solaire ;
        # si du potentiel existe il est récupéré, sinon la production reste
        # inchangée et la publication réseau suivante réévalue la situation.
        solar_is_capped = pv_at_limit or current == 0 or import_w > import_high

        candidates: list[tuple[float, int, float, float, float]] = []
        for level in range(0, 101, 10):
            candidate_limit_w = inverter_w * level / 100.0

            if level == current:
                predicted_pv_w = pv_w
            elif level < current:
                # En descendant, on connaît au minimum la production actuelle.
                predicted_pv_w = min(pv_w, candidate_limit_w)
            elif solar_is_capped:
                # Potentiel solaire inconnu au-dessus du plafond actuel : on
                # simule le plafond candidat. Si le soleil manque réellement,
                # le résultat sera seulement davantage d'import, jamais plus
                # de réinjection que ce que permet ce plafond.
                predicted_pv_w = candidate_limit_w
            else:
                # PV non bridé : relever le PRI ne crée pas de soleil.
                predicted_pv_w = min(pv_w, candidate_limit_w)

            grid_w = predicted_pv_w - estimated_house_w
            predicted_export_w = max(grid_w, 0.0)
            predicted_import_w = max(-grid_w, 0.0)
            candidate_score = self._score_grid(
                predicted_import_w,
                predicted_export_w,
                import_target_w=import_target,
                import_max_w=import_high,
                export_max_w=export_limit,
                weight_import=weight_import,
                weight_export=weight_export,
            )
            candidates.append(
                (candidate_score, level, predicted_import_w, predicted_export_w, predicted_pv_w)
            )

        # Score minimal. En cas d'égalité, rester le plus près possible du
        # niveau courant afin d'éviter une commutation RRCR inutile.
        best = min(candidates, key=lambda row: (row[0], abs(row[1] - current), row[1]))
        best_score, target, predicted_import, predicted_export, predicted_pv = best

        # Hystérésis : un faible gain de score ne justifie pas une commutation.
        # Une situation hors enveloppe garde toutefois la priorité et peut
        # commander immédiatement le palier calculé.
        outside_envelope = export_w > export_limit or import_w > import_high
        improvement = current_score - best_score
        if target != current and not outside_envelope and improvement < score_margin:
            target = current
            best_score = current_score
            predicted_import = import_w
            predicted_export = export_w
            predicted_pv = pv_w

        target_limit_w = inverter_w * target / 100.0
        action = "REDUCTION" if target < current else "LIBERATION" if target > current else "MAINTIEN"

        if target == current:
            reason = (
                "PRI prédictif : niveau maintenu à "
                f"{current} %. Maison estimée={estimated_house_w:.0f} W, "
                f"réseau={export_w:.0f} W export/{import_w:.0f} W import, "
                f"cible import≈{import_target:.0f} W."
            )
        else:
            reason = (
                "PRI prédictif : calcul direct "
                f"{current}% -> {target}%. Maison estimée={estimated_house_w:.0f} W, "
                f"PV cible≈{target_pv_w:.0f} W, plafond choisi={target_limit_w:.0f} W, "
                f"réseau prévu≈{predicted_export:.0f} W export/{predicted_import:.0f} W import "
                f"(score {current_score:.0f}->{best_score:.0f})."
            )

        target_ratio = (predicted_pv / target_limit_w) if target_limit_w > 0 else 0.0
        target_at_limit = (
            target > 0
            and (
                predicted_pv >= max(target_limit_w - tolerance_w, 0.0)
                or target_ratio >= ratio_threshold
            )
        )

        return InverterDecision(
            current_level=current,
            target_level=target,
            action=action,
            reason=reason,
            pv_limit_w=limit_w,
            pv_ratio=ratio,
            pv_at_limit=pv_at_limit,
            more_solar_possible=(target < 100 and target_at_limit),
            max_solar_reached=(target > 0 and not target_at_limit),
            score_current=current_score,
            score_target=best_score,
            house_target_level=house_target_level,
            estimated_house_w=estimated_house_w,
            target_pv_w=target_pv_w,
            predicted_import_w=predicted_import,
            predicted_export_w=predicted_export,
        )
