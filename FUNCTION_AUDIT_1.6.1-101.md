# Audit anti-régression — FoxCat Energy 1.6.1 → 1.6.1-101

## Résultat automatique

- Fonctions / méthodes en 1.6.1 : **275**
- Fonctions / méthodes en 1.6.1-101 : **278**
- Fonctions supprimées : **0**
- Fonctions ajoutées : **3**

## Fonctions ajoutées

1. `FoxCatEnergyCoordinator._on_daily_counter_reset`
   - callback Home Assistant exécuté à minuit ;
   - lance le reset journalier asynchrone.

2. `FoxCatEnergyCoordinator._async_daily_counter_reset`
   - archive les compteurs de la journée précédente ;
   - remet à zéro les compteurs visibles Métronome et trames ;
   - conserve la séquence technique interne servant aux ACK PRI N+1.

3. `EnergyBus.reset_daily_counters`
   - archive le nombre de messages de la journée précédente ;
   - remet la numérotation visible des messages à 1 ;
   - clôture les messages sans ACK en TIMEOUT de fin de journée ;
   - purge le journal court de la journée précédente.

## Fonctions supprimées

**Aucune.**

## Fonctions historiques vérifiées comme toujours présentes

- machine à états EMS ;
- Watchdog ;
- Métronome principal et fallback ;
- Energy Bus ;
- ACK inter-corps ;
- ACK RRCR ;
- validation PRI N+1 ;
- PRI prédictif ;
- modes EMS ;
- gestion Boiler ;
- cycles machines protégés ;
- délestage ;
- tarification ;
- comptabilité énergétique ;
- registre FoxCat ;
- génération du dashboard.

## Conclusion

La release 1.6.1-101 ajoute uniquement la gestion journalière des compteurs et la séparation entre numéro de trame visible et séquence technique interne. Aucune fonction Python de la 1.6.1 n'a été supprimée.
