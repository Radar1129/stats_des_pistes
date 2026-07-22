# 🌙 Mise à jour : Refonte du Mode Nuit & Compteurs (23/07/2026)

## 🛠️ Backend (api.py)
* **Correction SQL :** Le filtre des vols de la veille ne charge plus toute la journée depuis 00h00, mais filtre strictement les vols prévus après 17h00.
* **Prévention du fuseau horaire :** La logique est désormais blindée pour renvoyer la fin de soirée d'hier et la journée d'aujourd'hui en un seul payload json propre.

## 🎨 Frontend (React - App.jsx)
* **Indicateurs du jour isolés :** Les compteurs (`totalPrevus`, `totalAnnules`, `totalDetectes`) filtrent désormais strictement la journée en cours (`!v.is_hier`). Le compteur affiche bien les 128 vols physiques du jour, sans inclure les 47 de la veille.
* **Correction fausse annulation :** La soustraction des vols annulés se base désormais sur `volsDuJour` et non plus sur le tableau complet `volsPrevus`.
* **Badge visuel :** Injection réussie du badge `🌙 Hier` devant l'heure (`v.heure`) pour distinguer visuellement la fin de soirée de la veille dans le tableau qui auto-scroll sur la journée en cours.

## 📊 Analyse des Données (Scraper)
* **Preuve de concept :** Validation que les 128 vols du scraper sont exacts (64 arrivées / 64 départs). L'écart avec les 156 vols du site officiel provient exclusivement du dédoublonnage des *code-shares* (partages de code commerciaux) pour ne conserver que les mouvements d'avions physiques réels.

---

## 🛡️ Spécification Technique : Filtre Anti-Hélicoptères & Bruit (Noise)

### 1. Objectif Métier
Exclure **100 % des hélicoptères** (secours, gendarmerie, privées, régulation médicale) afin qu'ils ne soient :
* **Ni affichés** sur la carte et dans les tableaux (invisibilité visuelle).
* **Ni comptabilisés** dans les métriques statistiques de la piste (valeur $= 0$).

### 2. Mécanisme de Filtrage (`flight_engine.py`, `live_radar.py`)
Le rejet s'effectue en amont de l'enregistrement en base de données SQLite via deux critères cumulatifs :

* **Mots-clés Callsign / Indicatif :**
  `["SAMU", "DRAGON", "HELI", "CHOPPER", "SMUR", "RESCUE", "SAF", "DHWIR"]`
* **Codes Types d'Appareil ICAO :**
  `["EC35", "EC45", "H135", "H145", "AS32", "AS50", "R22", "R44"]`

### 3. Couverture de Tests (`test_engines.py`)
Validation automatique par assertions unitaires :
* `assert is_noise("SAMU24", "") == True`
* `assert is_noise("DRAGON33", "EC45") == True`

## 🚀 Mise à jour : Détection Hors-Programme & Aviation Générale
- **Backend (`api.py`)** : Création de l'endpoint `/api/vols/hors-programme` avec double connexion SQLite (`lfbd_schedule.db` et `bordeaux_stats.db`). Filtrage automatique sur 24h glissantes comparant les détections radar aux vols commerciaux programmés.
- **Frontend (`App.jsx`)** : Ajout du composant visuel dédié "Aviation Générale & Hors-Programme" au-dessus du bloc statistique. Intégration de l'appel synchronisé au cycle de rafraîchissement global via `${API_BASE_URL}`.
