#!/bin/bash
echo "🛑 Arrêt des services..."
pkill -9 -f uvicorn
pkill -9 -f api.py
pkill -9 -f detector.py
pkill -9 -f live_radar.py

echo "🧹 Nettoyage du cache..."
rm -f /home/ubuntu/stats_des_pistes/backend/scraped_cache.json

echo "🚀 Démarrage de l'API Web..."
cd /home/ubuntu/stats_des_pistes/backend || exit 1
nohup python3 -m uvicorn api:app --host 127.0.0.1 --port 8000 > uvicorn.log 2>&1 &

echo "📡 Démarrage des capteurs Radar..."
nohup ./venv/bin/python3 live_radar.py > live_radar.log 2>&1 &
nohup ./venv/bin/python3 detector.py > detector.log 2>&1 &

sleep 2
echo "✅ Tous les services (API + Radar) sont relancés !"
