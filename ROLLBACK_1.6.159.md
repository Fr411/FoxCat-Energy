# Rollback 1.6.159

Pour revenir à 1.6.158 :

1. arrêter toute modification manuelle du composant ;
2. restaurer l'archive 1.6.158 utilisée comme base ;
3. redémarrer Home Assistant ;
4. contrôler le registre des entités et les prises machines.

Le store Accounting 1.6.159 ajoute des sous-buckets tarifaires sans supprimer les totaux historiques. La 1.6.158 peut ignorer ces clés supplémentaires lors d'un retour arrière, mais une sauvegarde du `.storage` Home Assistant avant mise à jour reste recommandée.
