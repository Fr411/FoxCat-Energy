# Proposition : standardiser la configuration tarifaire (Belgique)

Source de référence : « Guide des Tarifs et Contrats d'Énergie en Belgique » (nov. 2026).

## 1. Constat : ce que FoxCat suit déjà

| Élément du guide | Dans FoxCat | État |
|---|---|---|
| Contrat fixe / variable / dynamique | `price_source` (contractuelle, variable, intégration, Day-Ahead) | Couvert |
| Wallonie mono-horaire | `distribution_profile = Simple` | Couvert |
| Wallonie bi-horaire 2026 (nuit + 11h-17h, 7j/7) | `tariff_hp_*` : HP 07-11 et 17-22, HC le reste | Couvert (défauts corrects) |
| Wallonie Impact (5 plages, 3 niveaux) | `impact_*` : ECO 01-07 et 11-17, PIC 17-22, MEDIUM | Couvert |
| Complément réseau par plage | `tariff_tou_hp/hc_adder`, `impact_*_adder` | Couvert |
| Réinjection (compensation, facturée, zéro, non valorisée) | `network_policy` | Couvert |
| Prosumer wallon (redevance) | rien | Absent |
| Flandre : tarif capacitaire (moyenne mensuelle des pointes 1/4 h, min 2,5 kW) | rien (le délestage protège le disjoncteur, pas ce coût) | Absent |
| Bruxelles : forfait capacitaire (~47 €/an, x2 au-delà de 13 kVA) | rien | Absent |

## 2. Problèmes de configuration constatés

1. **Le formulaire d'installation mélange contrat et réseau.** Famille « HP/HC » = Mono ou Bi ; famille « Dynamique » = Simple ou Impact. Impossible de choisir Impact avec un contrat fixe, ou bi-horaire avec un contrat dynamique, alors que `distribution_profile` est déjà indépendant dans le moteur (et exposé après coup dans l'entité `select` « profil de distribution Belgique »).
2. **Prix HP et HC obligatoires** en bi-horaire (`config_flow.py`), même quand le prix de fourniture est unique et que seul le complément réseau change.
3. **Capteurs de prix par défaut codés en dur** sur un fournisseur précis (`sensor.luminus_luminus_dynamic_wallonia_*`, `..._comfyflex_wallonia_*` dans `config_flow.py` et `runtime/registry.py`). Sur une autre installation, ces valeurs sont fausses.
4. **Aucune notion de région ni de gestionnaire de réseau.** Chaque installation ressaisit à la main les plages et compléments.
5. **Découpage HP/HC par horloge**, à partir de la puissance du capteur réseau. Un seul comptage suffit, mais le résultat est une estimation, pas les index du compteur.
6. **Pas de coût capacitaire** (Flandre, Bruxelles) ni de redevance prosumer (Wallonie).

## 3. Proposition

### 3.1 Trois axes indépendants, un seul schéma de réglages

```
contrat      : fixe | variable | dynamique        -> price_source
réseau       : mono | bi-horaire | impact | capacitaire -> distribution_profile
région/GRD   : wallonie | flandre | bruxelles | autre   -> grid_region (nouveau)
```

Le formulaire pose trois questions dans cet ordre. Les prix HP/HC ne sont demandés que si le contrat lui-même est bi-horaire. Avec un contrat fixe ou dynamique, seul le complément réseau est demandé.

### 3.2 Profils régionaux prédéfinis (`domain/tariff/regions.py`)

Un fichier de données par région, versionné (millésime 2026), qui remplit les réglages par défaut :

- Wallonie : plages bi-horaires et Impact du guide, option prosumer (compteur intelligent oui/non, kWe onduleur).
- Flandre : mode capacitaire, minimum 2,5 kW, terme proportionnel.
- Bruxelles : forfait selon puissance (< ou > 13 kVA).
- « Autre » : saisie manuelle, comme aujourd'hui.

L'utilisateur peut toujours surcharger. Les valeurs chiffrées (€/kW, €/kWe, forfait) restent éditables car elles changent chaque année.

### 3.3 Capteurs de prix sans valeur par défaut propriétaire

Remplacer les entités Luminus par des champs vides (ou un sélecteur de fournisseur proposant des motifs de noms). Ne jamais prérégler une entité qui peut ne pas exister.

### 3.4 Nouveaux calculs

- **Coût capacitaire (Flandre)** : mémoriser la pointe 1/4 h du mois en cours, calculer `max(pointe_moyenne_mensuelle, 2,5 kW) x tarif €/kW/an / 12`, l'exposer en capteur et l'ajouter au ledger.
- **Forfait Bruxelles / prosumer wallon** : coût fixe réparti dans le temps, exposé à part.
- **Source du découpage HP/HC** : option « horloge FoxCat » (défaut) ou « index du compteur » si l'utilisateur fournit les capteurs HP/HC.

### 3.5 Migration et tests

- Migration : conserver `tariff_structure` / `price_source` existants et déduire `grid_region = autre`, sans changer le comportement des installations actuelles.
- Tests : un cas par combinaison du tableau (contrat x réseau x région), plus les plages de 11h à 17h et la bascule HP/HC.
- Documenter le tableau de la section 1 dans le README.

## 4. Ordre de réalisation proposé

1. Formulaire en trois questions et suppression des défauts Luminus (corrige les points 1 à 3, faible risque).
2. Profils régionaux Wallonie (valeurs déjà connues).
3. Coût capacitaire Flandre.
4. Forfait Bruxelles et redevance prosumer.
5. Option « index du compteur ».

## 5. À valider avant de coder

- Les plages Flandre et Bruxelles ne figurent pas dans le guide (seulement la structure tarifaire). Il faut les valeurs du gestionnaire de réseau (Fluvius, Sibelga) pour les profils.
- Les montants du guide sont des moyennes ; l'utilisateur doit pouvoir saisir les siens.
