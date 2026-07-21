#!/bin/bash
echo "⚠️ LANCEMENT DU ROLLBACK D'URGENCE..."
cd /home/ubuntu/stats_des_pistes/
# Annule toutes les modifications non commitées
git reset --hard HEAD
# Supprime les nouveaux fichiers non suivis
git clean -fd
echo "✅ ROLLBACK TERMINÉ. Le projet est revenu à son dernier état stable."
