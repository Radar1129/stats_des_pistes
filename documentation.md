# Contexte du Projet : Stats des Pistes (LFBD / Bordeaux)

## 1. Directives de Développement & Exigences
- **Pérennité & Automatisation** : Uniquement des solutions automatisées et pérennes. Interdiction des corrections manuelles, ponctuelles ou "one-shot".
- **Commandes Clé en Main** : Fournir exclusivement des commandes terminal/bash exécutoires complètes. Aucune édition manuelle de fichier (ex: `nano`, `vim`).
- **Niveau d'Exigence** : Code propre, structuré avec séparation des responsabilités, testé (TDD) et directement opérationnel.

## 2. Architecture Générale (Backend FastAPI + SQLite)
- **Scripts Principaux** : `api.py` (FastAPI), `live_radar.py` (Flux ADS-B), `detector.py` (Analyse croisée), `check_aerovision.py` (Scraper Playwright 15min).
- **Moteurs Logiques Isolés (Fonctions Pures)** :
  - `flight_engine.py` : Qualification de phase (Priorité absolue au Programme > Télémétrie), Rapprochement IATA/ICAO (Regex intelligente 2/3 lettres), Filtre anti-bruit (Hélicos/Secours).
  - `geometry_engine.py` : Calcul mathématique strict (Cross-Track Distance). Tolérance d'axe de 400m, Heading Gate (Cap ±25°), distance max 25km. Fini les conditions de zones approximatives.
- **Middleware API** : `PrioritySortMiddleware` intégré à `api.py`. Intercepte de façon transparente les flux JSON pour trier les listes de vols (Priorité 1: APPROCHE/DÉCOLLAGE, Priorité 2: EN VOL, Priorité 3: SOL) sans corrompre les schémas Pydantic.
- **Tests** : Suite `pytest` (`test_engines.py`) garantissant la non-régression mathématique, géométrique et logique.

## 3. Règles Métier Validées
- **Qualification de Phase (Hiérarchie stricte d'évaluation)** :
  1. Sol (Vitesse < 35 kts & Alt < 100 ft) -> ROULAGE / SOL.
  2. Présence dans le programme Aérovision (ARRIVEE/DEPART) -> APPROCHE/ATTERRISSAGE ou DECOLLAGE. (Court-circuite la télémétrie).
  3. Télémétrie pure (V/S < -150 ft/min -> APPROCHE, V/S > +150 ft/min -> DECOLLAGE).
  4. Neutre -> EN VOL.
- **Rapprochement IATA / ICAO** : Extraction du préfixe via Regex `^([A-Z]{3}|[A-Z0-9]{2})(\d.*)$` et croisement via dictionnaire d'équivalence (ex: U2/EJU/EZY).

## 4. Commandes Utiles
- **Tests (Validation Architecture)** : `/home/ubuntu/stats_des_pistes/backend/venv/bin/python3 -m pytest /home/ubuntu/stats_des_pistes/backend/test_engines.py -v`
- **Redémarrer le backend** : `/home/ubuntu/stats_des_pistes/redemarrer_backend.sh`
- **Exécuter la capture Aérovision manuellement** : `/home/ubuntu/stats_des_pistes/backend/venv/bin/python3 /home/ubuntu/stats_des_pistes/backend/check_aerovision.py`
