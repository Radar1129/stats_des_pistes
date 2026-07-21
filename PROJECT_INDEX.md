# INDEX DU PROJET : RADAR LFBD

## 1. STRUCTURE GLOBALE
- `/home/ubuntu/stats_des_pistes/` : Racine du projet.
  - `/backend/` : Logique serveur (Python/FastAPI), écoute radar, base de données.
  - `/frontend/` : Interface utilisateur (React, Vite, Leaflet).

## 2. BACKEND (Les Moteurs)
- `api.py` : Serveur FastAPI. Expose les routes pour le frontend et sert le cache. (À redémarrer via Uvicorn).
- `detector.py` : Le processus qui tourne en boucle pour écouter l'ADS-B en direct, appliquer la machine à états (fenêtre de 5 min) et insérer les vols réels dans la BDD.
- `check_aerovision.py` : Le scraper (CRON) qui aspire l'API AJAX de l'aéroport pour mettre à jour le programme du jour.
- `generate_score.py` : Calcule la performance de détection quotidienne.

## 3. DONNÉES & CACHE
- `scraped_cache.json` : Fichier vital. Contient le programme du jour. Écrasé chaque nuit et lu par `api.py`. À purger manuellement en cas de corruption.
- `stats_pistes.db` : Base SQLite contenant l'historique des vols détectés physiquement.

## 4. FRONTEND (L'Affichage)
- `src/App.jsx` : Le chef d'orchestre. Contient la logique de réconciliation (Alerte Live, Malus physique -2000, Auto-scroll).
- `isBordeauxMovement` : Fonction clé définissant si un avion est actif (plafond 1500m) ou au sol (plafond 500m).
