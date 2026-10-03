# FoxCat Energy 1.6.157 — Plan de validation pas-à-pas

## 0. Préparation

1. Sauvegarder le dossier `custom_components/foxcat_energy` de la 1.6.156.
2. Sauvegarder la configuration Home Assistant.
3. Installer la 1.6.157 puis redémarrer Home Assistant.
4. Ouvrir **Paramètres > Appareils et services > FoxCat Energy > Configurer > Boiler**.
5. Renseigner :
   - Volume Boiler réel ;
   - Puissance nominale de la résistance ;
   - Température eau froide réseau ;
   - conserver la sonde Résistance de sécurité configurée.
6. Vérifier que les deux switches existent :
   - `switch.foxcat_predictive_pricing_enabled`
   - `switch.foxcat_solar_forecast_arbitrage`
7. Vérifier les nouveaux capteurs `sensor.foxcat_boiler_*`.
8. Conserver une trace des états de `Décision économique EMS`, du PRI, de la puissance réseau et de la température Boiler pendant les essais.

## 1. Non-régression HP/HC — obligatoire avant Dynamique

1. Choisir **Bi-horaire HP/HC**.
2. Tester une période HP avec Boiler au-dessus du minimum ECS.
3. Tester une période HC avec Boiler sous sa consigne normale.
4. Basculer les deux nouveaux kill-switches ON puis OFF.
5. Vérifier qu'ils ne changent pas les décisions HP/HC.
6. Vérifier que les transitions PRI habituelles restent identiques.
7. Vérifier que la notification, les bilans et Accounting continuent à évoluer normalement.

**Critère d'acceptation :** aucun comportement HP/HC ne doit dépendre de l'indice Day-Ahead ni des deux nouveaux kill-switches.

## 2. Modèle thermique Boiler

Exemple de contrôle manuel :

- volume = 250 L ;
- résistance = 1800 W ;
- température mesurée = 40 °C ;
- consigne confort = 45 °C.

Valeur attendue :

`E_th = 250 × 1.163 × 5 / 1000 = 1.45375 kWh`

Durée théorique :

`1.45375 / 1.8 = 0.8076 h`, soit environ 48,5 minutes.

Vérifier que les capteurs FoxCat sont cohérents avec ce calcul.

## 3. Dynamique — bas de courbe / prix d'achat négatif

Préconditions :

- régime Dynamique ;
- prédictif prix ON ;
- série Day-Ahead >= 6 points, idéalement 24 ;
- prix actuel placé sous 35 % de l'amplitude journalière.

### Cas A — réglage historique « charge réseau prix négatif » ON

1. Fournir un prix d'achat inférieur à `dynamic_grid_charge_threshold_eur_kwh`.
2. Mettre le Boiler sous son niveau de stockage utile.
3. Vérifier que l'intention historique `PRIX_NEGATIF_RESEAU` est conservée.
4. Vérifier que le stockage 65 °C reste possible comme en 1.6.156.
5. Vérifier que la sécurité 68 °C arrête toujours le Boiler.

### Cas B — réglage historique OFF

1. Désactiver « Charge réseau si prix dynamique négatif ».
2. Conserver un prix inférieur au seuil.
3. Sans surplus PV suffisant et au-dessus du minimum ECS : vérifier que le Boiler n'est pas lancé depuis le réseau.
4. Avec un surplus PV supérieur à la puissance nominale de la résistance : vérifier que la chauffe locale peut être autorisée.
5. Sous le minimum ECS : vérifier que le confort minimal reste prioritaire.

## 4. Dynamique — médiane 0,35 à 0,70

1. Régler/observer un prix dont l'indice relatif est entre 0,35 et 0,70.
2. Vérifier l'attribut `plage_tarifaire_dynamique = MEDIAN`.
3. Sans surplus suffisant : Boiler ne doit pas démarrer sur le réseau.
4. Avec surplus >= puissance résistance : Boiler peut chauffer.
5. Une machine inactive ne peut démarrer que si le surplus couvre sa puissance moyenne estimée.
6. Même si le meilleur bloc thermique calculé inclut l'heure courante, `boiler_charge_maintenant` doit rester `false` en médiane hors confort prioritaire.

## 5. Dynamique — crête > 0,70

1. Régler/observer un prix proche du maximum Day-Ahead.
2. Vérifier `plage_tarifaire_dynamique = HAUT`.
3. Boiler au-dessus du minimum ECS : aucun nouveau chargement réseau.
4. Nouvelle machine flexible : démarrage économique refusé.
5. Machine déjà en cycle protégé : elle doit continuer, sans interruption.
6. Boiler sous le minimum ECS : la chauffe minimale doit rester prioritaire.

## 6. Réservation thermique Day-Ahead

1. Renseigner volume et puissance réels du Boiler.
2. Créer/observer un besoin thermique nécessitant par exemple 2,2 h de chauffe.
3. Vérifier que FoxCat réserve **3 blocs horaires consécutifs**.
4. Vérifier que la fenêtre choisie est celle dont le prix moyen est minimal parmi les blocs continus disponibles.
5. Vérifier les attributs :
   - énergie manquante ;
   - durée estimée ;
   - début/fin de réservation ;
   - prix moyen du bloc.
6. Vérifier que la réservation ne déclenche effectivement la chauffe réseau que lorsque la plage actuelle est BAS.

## 7. Prix d'export dynamique signé / PRI

### Export valorisé

1. Politique = Injection tarifée.
2. Régime = Dynamique.
3. Valeur économique d'export normalisée > 0.
4. PRI initial < 100 %.
5. À la prochaine trame réseau, vérifier cible PRI = **100 %**.

### Export coûteux

1. Valeur d'export normalisée < 0.
2. Créer une réinjection physique significative.
3. Vérifier que le PRI prédictif cherche le palier de quasi-zéro injection/local-consumption.
4. Vérifier que le réseau signé reste la cadence des décisions ; les prix ne doivent pas créer leur propre boucle de commande.

### Compensation

1. Politique = Compensation.
2. Régime = Dynamique.
3. Fournir une valeur d'export positive puis négative.
4. Vérifier dans les deux cas : cible PRI = **100 %**.

## 8. Kill-switch prédictif prix

1. En Dynamique, mettre `switch.foxcat_predictive_pricing_enabled` OFF.
2. Vérifier que la décision expose un repli standard (`repli_dynamique_standard = true`).
3. Vérifier que les bandes BAS/MEDIAN/HAUT ne commandent plus le Boiler ou les nouveaux départs machines.
4. Remettre ON et attendre une nouvelle trame réseau.

## 9. Kill-switch solaire

1. En Dynamique, mettre `switch.foxcat_solar_forecast_arbitrage` OFF.
2. Vérifier que l'IA / télémétrie Forecast.Solar continue d'être disponible.
3. Vérifier que la prévision solaire n'influence plus l'intention dynamique du Boiler.
4. Passer HP/HC : le switch ne doit créer aucun changement de comportement.

## 10. Repli standard par Day-Ahead incomplet

1. Fournir moins de 6 points valides sur l'horizon dynamique.
2. Vérifier que FoxCat signale un repli standard.
3. Vérifier que la décision se comporte selon la logique dynamique 1.6.156.
4. Restaurer une série >= 6 points et vérifier le retour automatique à l'indice relatif.

## 11. Sécurité 68 °C

1. Simuler/observer la sonde Résistance à 67,5 °C puis 68,0 °C ou plus.
2. À >= seuil de sécurité, vérifier :
   - arrêt du Boiler s'il chauffe ;
   - aucun nouveau démarrage automatique ;
   - aucun forçage utilisateur ne doit contourner la sécurité ;
   - aucune bande de prix ne doit contourner la sécurité.
3. Vérifier le journal FoxCat et l'entité de sécurité thermique.

## 12. MachineCycleManager

1. Démarrer un cycle machine et le laisser entrer en état protégé.
2. Passer ensuite en prix HAUT.
3. Vérifier que le cycle continue.
4. Vérifier que l'optimiseur affiche `CYCLE_EN_COURS` et ne tente pas d'arrêt.
5. Vérifier que les nouvelles charges secondaires sont bloquées si le confort ECS minimum réclame le créneau.

## 13. Critère de validation release

La 1.6.157 est validée si :

- HP/HC est inchangé sur l'installation ;
- aucune régression de cycle machine n'est observée ;
- sécurité 68 °C souveraine ;
- Compensation toujours 100 % ;
- export dynamique positif libère le PRI ;
- export dynamique négatif déclenche la logique zéro-injection ;
- MEDIAN ne charge jamais le réseau opportunément ;
- HAUT bloque les nouveaux prélèvements opportunistes ;
- BAS exploite/réserve les heures les moins chères ;
- les kill-switches rétablissent immédiatement un fonctionnement conservateur.
