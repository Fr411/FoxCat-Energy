# FoxCat Energy 1.6.158 — Rapport de tests

## Tests statiques

- compilation de tous les fichiers Python : OK
- parsing `manifest.json` : OK
- parsing `strings.json` : OK
- parsing `translations/fr.json` : OK
- parsing YAML du dashboard officiel : OK

## Tests purs exécutés

1. **Parser Luminus Dynamic**
   - `today/tomorrow[].all_in` lu comme prix d'achat : OK
   - `today/tomorrow[].injection` lu comme valeur d'export : OK

2. **Position sur courbe**
   - construction d'une courbe 24 h ;
   - calcul de la zone dynamique et de la position en % : OK

3. **PRI export rémunérateur**
   - prédictif activé : cible 100 % : OK
   - prédictif désactivé : cible 100 % : OK
   - `engine/pri.py` : cible 100 % : OK
   - `inverter_core.py` : cible 100 % : OK

4. **Accounting export positif**
   - revenu de réinjection comptabilisé : OK
   - revenu déduit du coût net : OK

5. **Accounting export négatif**
   - coût de réinjection comptabilisé : OK
   - coût ajouté au coût net : OK

6. **Prix achat négatif**
   - coût d'import reste signé négatif : OK
   - coût net peut devenir négatif : OK

7. **HP/HC**
   - courbe calculée uniquement à partir des prix HP/HC fournis : OK
   - aucun point Dynamic injecté dans la série HP/HC : OK

8. **Courbe backend/dashboard**
   - le coordinator publie les points achat/réinjection réellement utilisés par le moteur : OK
   - le dashboard officiel trace `pricing.curve` au lieu de reconstruire une courbe fournisseur séparée : OK
   - parsing YAML après ajout de la carte ApexCharts : OK
   - dashboard client harmonisé : 0 référence directe ComfyFlex pour un prix actif générique, parsing YAML : OK

## Limitation

Le runtime de test ne contient pas une instance Home Assistant complète. Les tests d'intégration sur matériel réel restent nécessaires pour valider :

- changement de régime à chaud ;
- valeurs exactes des entités Luminus de l'installation ;
- publication réseau / PRI réel ;
- persistance Accounting après redémarrage ;
- rendu frontend des dashboards personnalisés.
