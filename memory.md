# Context Technique & Architecture - Stats des Pistes (LFBD)

## 1. Detection Radar (`backend/detector.py`)
- **Pistes Principales (05/23)** :
  - Atterrissage : Distance <= 6.0 km, Altitude <= 600 m, Cap +/- 15°.
  - Décollage : Distance <= 2.5 km, Altitude <= 350 m, Cap +/- 30° (pour intégrer les virages rapides / SIDs) si Taux Vertical > 100 ft/min.
- **Pistes Secondaires (11/29)** :
  - Atterrissage : Distance <= 4.0 km, Altitude <= 400 m, Cap +/- 15°.
  - Décollage : Distance <= 2.5 km, Altitude <= 350 m, Cap +/- 30° si Taux Vertical > 100 ft/min.

## 2. Engine de Matching V2 (`backend/api.py`)
- **Table de conversion Compagnies (`AIRLINES_MAP`)** : Normalisation ICAO / IATA (ex: `EJU`/`EZY`/`U2` -> `EASYJET`).
- **Filtres Stricts** :
  - Incompatibilité Sens (Arrivée vs Décollage).
  - Incompatibilité Compagnie (Bloque le matching entre compagnies différentes).
- **Matrice de Scoring & Attribution Globale** :
  - Match Compagnie : +100 pts
  - Match Chiffres N° de Vol / Callsign : +150 pts (exact) / +80 pts (partiel)
  - Match Ville / Route : +120 pts
  - Pénalité Temps : -1 pt par tranche de 2 minutes d'écart
  - Tri global par score décroissant pour éviter les affectations opportunistes.

## 3. Alerte Live Frontend (`frontend/src/App.jsx`)
- Fonction `isBordeauxMovement` alignée sur les plafonds backend (Max 600m général, Max 400m pour axe 11/29).

## Synthèse des modifications (Matching & QFU) - 20/07/2026

### 1. Algorithme de Matching Intelligent (`api.py`)
- **Ingestion BDD complète** : Ajout des champs `callsign`, `origine` et `destination` dans la structure du dictionnaire `vols_detectes_du_jour`.
- **Table de correspondance des compagnies (IATA ↔ OACI)** : Implémentation du dictionnaire `CIE_MAP` (`U2` ↔ `EJU/EZY`, `V7` ↔ `VOE`, `TO` ↔ `TVF`, `AF` ↔ `AFR`, `KL` ↔ `KLM`...) pour l'association des indicatifs radio ATC avec le planning commercial.
- **Fenêtre temporelle stricte** : Association autorisée uniquement si l'écart de temps est compris entre **-30 min** (avance) et **+3 heures** (retard) par rapport à l'horaire prévu (`dt_prevue`).
- **Correction Timezone** : Normalisation de la conversion des timestamps BDD en heure locale `Europe/Paris` sans passage parasite par UTC (suppression du décalage de +2h).
- **Matching multi-critères** : Croisement du numéro de vol, code compagnie, sens de mouvement et ville de provenance/destination avec système d'éligibilité et scoring.

### 2. Statistiques de Pistes & Logique Croisée QFU (`get_stats_historique`)
- **Règle physique de détection des pistes** :
  - *Atterrissage* : Piste attribuée selon le tronçon du **premier contact des roues au sol** (touchdown).
  - *Décollage* : Piste attribuée selon le tronçon du **dernier contact des roues au sol** avant l'envol (rotation/liftoff).
- **Logique croisée des portails radar (`portail_nom`)** :
  - **Portail 05** + Atterrissage → **Piste 05** | Portail 05 + Décollage → **Piste 23**
  - **Portail 23** + Atterrissage → **Piste 23** | Portail 23 + Décollage → **Piste 05**
  - **Portail 11** + Atterrissage → **Piste 11** | Portail 11 + Décollage → **Piste 29**
  - **Portail 29** + Atterrissage → **Piste 29** | Portail 29 + Décollage → **Piste 11**
- **Calcul des pourcentages par axe** : Normalisation des pourcentages de chaque piste relativement à la somme globale de son propre axe (05/23 ou 11/29).
