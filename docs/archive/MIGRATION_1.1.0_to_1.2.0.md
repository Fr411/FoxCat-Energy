# Migration FoxCat Energy 1.1.0 → 1.2.0

## Mise à jour complète recommandée

Remplacer le dossier `custom_components/foxcat_energy` complet par celui de la V1.2.0, puis redémarrer Home Assistant.

Les `unique_id` existants des entités historiques ne sont pas renommés. Les nouvelles entités sont ajoutées sans supprimer les anciennes.

## Changements de comportement à connaître

1. `Confort` n'existe plus. Un ancien mode Confort est converti en `Manuel`.
2. `Manuel` ne pilote plus automatiquement les prises machines. Il laisse aussi le boiler et le PRI à l'utilisateur ; seule la sécurité thermique dure reste souveraine.
3. `Économie énergie` pilote maintenant le boiler **et** le PRI : le surplus utile est d'abord valorisé dans l'ECS, puis le PRI traite l'excédent résiduel.
4. `Zéro injection` ne cible plus la consommation maison. Il corrige la réinjection réelle, avec zéro partiel si une marche de 400 W provoquerait trop d'import.
5. `Prix dynamique` fonctionne uniquement lorsque `Régime tarifaire = Dynamique`.
6. Si le prix d'achat dynamique devient négatif, FoxCat peut charger le boiler depuis le réseau jusqu'à 65 °C. Cette fonction peut être désactivée par le switch dédié.

## Nouveaux réglages à vérifier après redémarrage

- `select.*regime_tarifaire*`
- `select.*pri_niveau_manuel*`
- `switch.*charge_reseau_si_prix_dynamique_negatif*`
- `number.*seuil_charge_reseau_prix_negatif*`
- `number.*prix_achat_heures_pleines*`
- `number.*prix_achat_heures_creuses*`
- `number.*prix_fixe_de_reinjection*`
- `number.*temporisation_pri_apres_action_boiler*`

Les entity_id exacts peuvent recevoir un suffixe Home Assistant ; les noms visibles ci-dessus servent de repère.

## Reconfiguration

Le flux Reconfigurer doit maintenant fonctionner sans `500 Internal Server Error`. Les changements ne sont appliqués qu'après **Enregistrer et quitter**.

## Rollback

1. `Régulation FoxCat active = OFF`.
2. `Libérer l'onduleur à 100 %`.
3. Restaurer le dossier V1.1.0.
4. Redémarrer Home Assistant.
