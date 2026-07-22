
## [2026-07-21] - Refonte de la Pré-détection & Restructuration Frontend

### 🚀 Nouveautés & Logique Métier
- **Cycle de validation des vols à 2 niveaux** :
  - **`🟠 Pré-détecté`** : Assignation automatique du "pari" dès qu'une trame radar ADS-B correspond à un vol du programme.
  - **`🟢 Détection confirmée`** : Statut réservé à la confirmation réseau/base de données.
- **Persistance de la pré-détection (`localStorage`)** :
  - Enregistrement des paires `vol_heure` dans la clé `radar_pre_detectes`.
  - Le badge **`🟠 Pré-détecté`** reste désormais verrouillé sur la ligne du tableau, même une fois l'avion sorti du champ radar live.
- **Raffinage du design visuel** :
  - Le surlignage (fond rose + liseré rouge) s'active **uniquement quand l'avion est physiquement en direct** sur l'antenne.
  - Suppression définitive du cadre/contour bleu (`outline`) sur la ligne cible temporelle.

### 🛠️ Corrections & Robustesse React
- **Restructuration de `App.jsx`** : Réalignement strict de la séquence d'exécution des Hooks React (`useState` $\rightarrow$ Calculs & Matching $\rightarrow$ `useEffect` $\rightarrow$ Early Returns $\rightarrow$ JSX) pour éradiquer la zone morte temporaire et l'erreur React #310.
- **Audit Scraper (`check_aerovision.py`)** : Inspection du cache JSON (`scraped_cache.json`) et analyse de la tolérance aux anomalies de publication sur le site de l'aéroport.

## [2026-07-21] - Stabilisation des phases de vol (Anti-bruit ADS-B)

### 🛠️ Améliorations
- **Suppression du label `EN TRANSIT`** : Remplacé par **`✈️ EN VOL`** pour un affichage plus clair.
- **Ajout de seuils de tolérance (Anti-yoyo)** dans `getPhaseDeVol` :
  - **`🚕 ROULAGE / SOL`** : Prioritaire pour toute altitude $< 100\text{ m}$ avec faible taux vertical, ou altitude $< 300\text{ m}$ sans pente forte.
  - **`🛫 DÉCOLLAGE`** : Déclenché uniquement si $\text{txVert} > +150\text{ ft/min}$ (élimine les micro-variations).
  - **`🛬 EN APPROCHE`** : Déclenché uniquement si $\text{txVert} < -150\text{ ft/min}$.

## [Unreleased] - 2026-07-22

### Ajouté
* **Collecteur automatique (`collector.py`)** : Script asynchrone autonome récupérant les vols LFBD sur une fenêtre glissante de 3 jours ($J-1$, $J$, $J+1$) toutes les 5 minutes.
* **Base de données (`lfbd_schedule.db`)** : Table SQLite `flights` idempotente avec clé primaire unique (`uid`).

### Modifié
* **API Backend (`backend/api.py`)** : Route `@app.get("/api/vols/expected")` raccordée directement à la base SQLite `lfbd_schedule.db` (remplace l'ancien fichier `scraped_cache.json`).

## [Unreleased] - 2026-07-22 (Suite)

### Modifié
* **API Backend (`backend/api.py`)** : Réécriture de la route `/api/vols/direct` pour respecter le cahier des charges (Bloc 1). Ajout d'une redondance via `concurrent.futures` interrogeant simultanément `adsb.lol` et `opendata.adsb.fi`.
* **Stabilité serveur** : Nettoyage des processus zombies (`live_radar.py`) qui saturaient la mémoire et risquaient de provoquer des blocages (rate-limit) auprès des API communautaires.

## [Unreleased] - 2026-07-23

### Réparé
* **Maintenance (`redemarrer_backend.sh`)** : Résolution du bug de l'historique vide. Le script de maintenance ne relançait que l'API et laissait les moteurs radar mourir en silence. Il redémarre désormais l'intégralité de la stack (API `uvicorn` + Capteurs `live_radar.py` et `detector.py`) pour garantir l'alimentation continue de la base `bordeaux_stats.db`.
