# FoxCat Energy 1.6.158 — Audit d'impact

## Objectif

V1.6.158 corrige le socle financier des régimes **Dynamique** et **Bi-horaire HP/HC** sans supprimer de fonction historique.

Règles de référence :

- **Luminus Dynamic** = référence financière du régime Dynamique.
- **Luminus ComfyFlex** = référence financière du régime HP/HC.
- Nord Pool / ENTSO-E ne remplacent pas les prix contractuels FoxCat ; ils peuvent rester des indicateurs temporels externes de pics/creux.
- La politique réseau utilisateur s'appelle désormais **Injection tarifée**.
- Une valeur économique de réinjection **positive** signifie un revenu ; une valeur **négative** signifie un coût.
- Si l'export est rémunérateur, le PRI est libéré à **100 %**, quel que soit le régime tarifaire et même si le prédictif Day-Ahead est désactivé.

## Fichiers modifiés

- `README.md`
- `custom_components/foxcat_energy/accounting/manager.py`
- `custom_components/foxcat_energy/config_flow.py`
- `custom_components/foxcat_energy/const.py`
- `custom_components/foxcat_energy/coordinator.py`
- `custom_components/foxcat_energy/dashboard/dashboard.yaml`
- `custom_components/foxcat_energy/economic_optimizer.py`
- `custom_components/foxcat_energy/engine/modes/dynamic.py`
- `custom_components/foxcat_energy/engine/pri.py`
- `custom_components/foxcat_energy/inverter_core.py`
- `custom_components/foxcat_energy/manifest.json`
- `custom_components/foxcat_energy/registry.py`
- `custom_components/foxcat_energy/sensor.py`
- `custom_components/foxcat_energy/strings.json`
- `custom_components/foxcat_energy/translations/fr.json`

## Anti-régression fonctions

Inventaire AST de tous les `.py` du composant :

- 1.6.157 : **348 fonctions/méthodes**
- 1.6.158 : **349 fonctions/méthodes**
- ajoutée : `EnergyAccounting._add_signed`
- supprimée : **0**

## 1. Luminus Dynamic : lecture native de la courbe

Le parseur Day-Ahead accepte maintenant un ordre de clés de prix spécifique au fournisseur.

Pour l'achat dynamique, FoxCat privilégie :

- `all_in` dans `today` / `tomorrow`.

Pour la réinjection dynamique, FoxCat privilégie :

- `injection` dans `today` / `tomorrow`.

Cela évite de mélanger prix d'achat et prix d'export lorsqu'une ligne fournisseur contient plusieurs composantes.

La décision dynamique expose maintenant aussi :

- position sur la courbe en % ;
- rang du prix courant dans l'horizon ;
- nombre de points utilisés ;
- tendance `HAUSSE` / `STABLE` / `BAISSE`.

## 2. Séparation stricte Dynamic / ComfyFlex

### Dynamique

Sources par défaut :

- `sensor.luminus_luminus_dynamic_wallonia_prix_actuel`
- `sensor.luminus_luminus_dynamic_wallonia_prix_heure_suivante`
- `sensor.luminus_luminus_dynamic_wallonia_prix_d_injection`
- min/max/moyenne Dynamic aujourd'hui/demain.

### HP/HC

Sources par défaut :

- `sensor.luminus_luminus_comfyflex_wallonia_prix_heures_pleines_jour`
- `sensor.luminus_luminus_comfyflex_wallonia_prix_heures_creuses_nuit`
- `sensor.luminus_luminus_comfyflex_wallonia_prix_d_injection`

Le dashboard généré utilise `pricing.active_buy` / `pricing.next_buy` pour afficher le tarif actif. Il ne retombe plus sur une source Dynamic lorsque le régime HP/HC est actif.

## 3. Convention de réinjection

Pour une source `luminus_luminus_dynamic`, FoxCat impose :

- positif = revenu de réinjection ;
- négatif = coût de réinjection.

Cette détection fournisseur corrige automatiquement les installations 1.6.157 qui avaient conservé l'ancien réglage de signe.

## 4. PRI

Règle souveraine :

`export_value > 0  =>  PRI = 100 %`

Elle est appliquée :

- en Dynamique ;
- en HP/HC ;
- indépendamment de `predictive_pricing_enabled`.

Le kill-switch prédictif ne peut donc plus détruire une production PV qui possède une valeur économique positive.

## 5. Accounting signé

Nouveaux compteurs :

- `export_revenue_eur`
- `export_cost_eur`

Le compteur historique `export_value_eur` devient le **solde signé** de la réinjection.

Formule :

`coût net = coût import + coût réinjection - revenu réinjection`

Les stores 1.6.157 sont migrés sans perdre les revenus déjà accumulés.

## 6. Coût marginal solaire/réseau

Pour une charge flexible, FoxCat compare maintenant le coût marginal du démarrage immédiat :

`coût effectif = part solaire × valeur réinjection + part réseau × prix achat`

avec le meilleur coût futur connu.

Conséquences :

- un prix élevé ne bloque plus automatiquement une charge si du solaire rend le coût marginal réellement meilleur ;
- une réinjection très rémunératrice peut au contraire rendre préférable l'export et le report ;
- une réinjection négative favorise l'absorption locale du surplus.

Le Boiler utilise le même principe pour décider si un mélange solaire + réseau est préférable au créneau futur réservé.

## 7. Terminologie

Le libellé utilisateur devient **Injection tarifée**.

L'ancien texte `Injection facturée` n'est conservé que comme alias de migration interne et reconnaissance d'anciens dashboards.
