# FoxCat Energy 1.6.160 — Test report

## Compilation

- `python -m compileall custom_components/foxcat_energy` : OK.
- dashboard client YAML : OK.
- dashboard intégré YAML : OK.

## Boiler Dynamic V2

- surplus solaire 2 000 W, résistance 1 800 W, position 90 %, T=50 °C -> `BOOST_65 / DYNAMIC_BOOST_SOLAIRE` : OK.
- absence de surplus, position 64 %, T=42 °C -> `CHAUFFE_45 / DYNAMIC_FALLBACK_ECS` : OK.
- absence de surplus, position 66 %, T=42 °C -> attente, aucune chauffe réseau : OK.
- position 20 %, T=44 °C -> `CHAUFFE_45`, pas de BOOST réseau : OK.
- position 20 %, T=50 °C -> attente, pas de BOOST réseau : OK.
- mode non Dynamique -> intention du moteur historique restituée sans modification : OK.

## Modes

- options : `Économie énergie`, `Zéro injection`, `Bihoraire`, `Dynamique`, `Manuel` : OK.
- alias `ECS solaire` -> `Bihoraire` : OK.
- alias `Prix dynamique` -> `Dynamique` : OK.

## Anti-régression AST

- 377 -> 378 fonctions/méthodes.
- +1 / -0.
