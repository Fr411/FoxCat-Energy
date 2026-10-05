# Rollback 1.7.0 → 1.6.160

1. Arrêter/recharger l'intégration FoxCat Energy.
2. Restaurer le dossier `custom_components/foxcat_energy` depuis l'archive 1.6.160.
3. Redémarrer Home Assistant.
4. Vérifier le mode EMS : la 1.6.160 utilise encore le sélecteur polymorphe `Dynamique / Bihoraire / ...`.
5. Si nécessaire, sélectionner manuellement le mode correspondant au contrat/politique utilisé avant rollback.

L'Accounting V2 est conservé au même format de base ; la ventilation historique n'est pas réécrite par la 1.7.0.
