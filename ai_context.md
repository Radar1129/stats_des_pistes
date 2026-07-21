# CONTEXTE TECHNIQUE ET RÉFÉRENTIEL DU PROJET RADAR LFBD (BORDEAUX)
Ce fichier sert de mémoire permanente pour l'IA. Il doit être lu intégralement au début de chaque session pour éviter les hallucinations et garantir la cohérence des modifications.

---

## BLOC 1 : ALERTE MOUVEMENT LIVE (Le "Chef d'Orchestre" du Dashboard)

### 1. Rôle et Objectif
Ce bloc isole et affiche en temps réel l'avion le plus pertinent en phase de décollage, atterrissage ou roulage sur l'aéroport de Bordeaux-Mérignac (LFBD). Il dicte également le comportement visuel des autres blocs (Carte et Liste).

### 2. Sources Brutes des Données (Backend & Frontend)
- **Flux ADS-B Live (Le Réel) :** Le backend (`api.py`) interroge simultanément deux API publiques non filtrées (`adsb.lol` et `opendata.adsb.fi`) pour assurer une redondance.
- **Filtre Géographique Strict :** Les requêtes ciblent le point de référence de LFBD (`lat/44.8283/lon/-0.7156`) avec un rayon d'action de **15 kilomètres** (`dist/15`).
- **Programme des vols (Le Prévu) :** Le frontend a accès à `volsPrevus`, une liste générée par un scraper backend qui aspire le site officiel de l'aéroport de Bordeaux toutes les 30 minutes.

### 3. Logique Métier Cœur : La fonction `isBordeauxMovement`
C'est le filtre de sélection. Pour qu'un avion soit considéré comme un "Mouvement Live", il doit passer cette logique adaptative (mise à jour pour combler la faille des décollages) :
- **Pré-requis :** L'aéroport est à ~50m d'altitude. L'altitude (`altM`) et le taux vertical (`txVert`) sont extraits des trames ADS-B.
- **Vérification croisée (Programme) :** Le système nettoie les espaces et met en minuscules le `callsign` (avion) et le `vol` (programme). Il y a correspondance si A inclut B, si B inclut A, ou si les 3 premières lettres correspondent. Le système déduit ainsi si le vol est de type `arrivée` ou `départ`.
- **Règle 1 : Phase Active (Plafond 1500m).** Si l'avion monte, descend (`txVert !== 0`), ou est identifié comme une arrivée ou un départ programmé, le plafond d'inclusion est élargi à **1500 mètres** pour capter tout le cône d'approche et de décollage.
- **Règle 2 : Phase Stable / Sol (Plafond 500m).** Si l'avion est en palier (taux vertical nul) et n'est pas dans le programme, le plafond est bridé à **500 mètres**. Cela permet de capter le trafic de roulage au sol (ex: jets privés Airlec) tout en excluant l'aviation légère (VFR) en transit plus haut.

### 4. Déduction de la Piste (QFU) via `getPisteFromCap`
Le système détermine la piste physique utilisée en analysant le cap (cap magnétique/boussole) de l'avion :
- Cap **35° à 95°** = PISTE 05 (Axe principal, face Nord-Est)
- Cap **215° à 275°** = PISTE 23 (Axe principal, face Sud-Ouest)
- Cap **>95° à <155°** = PISTE 11 (Axe secondaire, face Sud-Est)
- Cap **>275° à <335°** = PISTE 29 (Axe secondaire, face Nord-Ouest)

### 5. Enrichissement Visuel et Badges Dynamiques
Lorsqu'un vol est sélectionné (devenant `volLivePrincipal`), le frontend génère des badges analytiques :
- **Identification :** Affiche la Compagnie, la Ville et l'Heure prévue si une correspondance `matchedProg` est trouvée.
- **Phase de Vol :** 
  - `tx > 0` => `🛫 DÉCOLLAGE`
  - `tx < 0` => `🛬 EN APPROCHE`
  - `alt < 300` => `🚕 ROULAGE / SOL`
  - Sinon => `✈️ EN TRANSIT`
- **Distance précise :** Calculée via la formule de Haversine entre l'avion et le centre de LFBD (affichée en `km`).
- **Type d'appareil :** Affiche le type d'avion (ex: A320) via les champs `t` ou `desc` de l'API ADS-B.
- **Détection d'Urgence (Squawk) :** Affiche des bannières critiques si le transpondeur émet : `7700` (Urgence), `7600` (Panne Radio) ou `7500` (Détournement).

### 6. Interactions avec les autres blocs du Dashboard (Synchronisation)
La fonction `isBordeauxMovement` est exportée pour synchroniser visuellement le reste du tableau de bord :
- **Bloc Carte Radar :** L'icône de l'avion sur la carte Leaflet passe en **ROUGE** si la fonction retourne `true`. Sinon, elle est bleue.
- **Bloc Trafic Régional :** Dans la barre latérale, la ligne textuelle de l'avion affiche un **fond rose et texte rouge** si la fonction retourne `true`.

## BLOC 2 : PROGRAMME DU JOUR & PERFORMANCE (La réconciliation Réel/Prévu)

### 1. Rôle et Objectif
Afficher le programme officiel des vols de la journée et indiquer visuellement ("✓ Détecté") lesquels ont été réellement captés par le réseau radar communautaire. Cela permet de calculer un score de couverture et de fiabilité (Performance).

### 2. Nature des Données (Le Réseau vs L'Antenne)
Le projet n'utilise pas une antenne locale unique, mais interroge les agrégateurs communautaires (`adsb.lol`, `opendata.adsb.fi`). La détection dépend de la couverture globale des passionnés autour de LFBD. Une non-détection est donc liée à une "zone d'ombre" physique du réseau à un instant T, et non à une faille du code.

### 3. Logique de validation ("✓ Détecté") - Backend
Le backend (via FastAPI) gère l'association entre théorie et réalité :
- **Matching Intelligent (IATA / OACI) :** Le code compare les chiffres du vol et applique un dictionnaire de traduction pour les lettres (ex: U2 -> EJU, FR -> RYR) afin de ne pas perdre les vols low-cost à cause de la différence de nomenclature entre le programme et les transpondeurs.
- **Tolérance temporelle :** L'écart entre l'heure prévue et la détection radar doit être `<= 9000` secondes (2h30).
- Le meilleur candidat est flagué `utilise = True` (anti-doublon) et `detecte = True`.

### 4. Indicateur de Performance
- **Calcul journalier :** `(detectes_du_jour / attendus_du_jour) * 100` (en excluant les annulations).
- **Persistance :** Le score affiché sur le frontend n'est pas journalier mais **cumulatif historique**. Le backend fait un `SUM()` de tous les vols attendus et détectés stockés dans `performance_journaliere` depuis le lancement du projet.

### 5. Mécanique d'Interface (Auto-scroll)
- Le frontend identifie le prochain vol pertinent par rapport à l'heure et lui attribue dynamiquement l'ID HTML `ligne-vol-scroll-cible`.
- Au montage (`useEffect`), la fonction `scrollIntoView` centre automatiquement la vue sur ce vol pour l'utilisateur.

### 5. Mécanique d'Interface Avancée (Surbrillance & Synchronisation Live)
- **Le défi des Callsigns Low-Cost :** Les compagnies (Volotea, EasyJet, Ryanair) utilisent des codes radar (ex: VOE8NN) qui n'ont souvent aucun chiffre en commun avec le programme commercial (ex: V72626).
- **Algorithme Frontend (Alerte Live) :** Pour lier l'avion en vol et surligner la bonne ligne du programme, le frontend utilise une logique à 3 étages :
  1. *Sécurité Trajectoire :* Un avion qui descend (`txVert < -64`) ne peut jamais être croisé avec un "Départ", et inversement.
  2. *Matching Strict :* Traduction du dictionnaire IATA/OACI + correspondance d'au moins 2 chiffres.
  3. *Fallback Temporel (Le "Tour de Magie") :* Si les chiffres ne matchent pas, mais que la compagnie et la direction sont bonnes, le système sélectionne le vol dont l'heure prévue est la plus proche de l'heure actuelle (fenêtre max de 2h30).

## BLOC 3 : CARTE RADAR & TRAFIC RÉGIONAL (La visualisation spatiale)

### 1. Rôle et Objectif
Offrir une vue spatiale en temps réel des avions détectés dans un rayon de 15 km autour de l'aéroport (LFBD), et différencier visuellement le trafic "en transit" du trafic "local" (atterrissages/décollages).

### 2. Mécanique Cartographique (Leaflet)
- **Fonds de carte :** Utilisation de `react-leaflet` et OpenStreetMap. Le centre est verrouillé sur LFBD (`[44.8283, -0.7156]`).
- **Axes des pistes :** Deux `<Polyline>` tracent virtuellement les axes d'approche : Bleu pour l'axe principal (05/23) et Rouge pour le secondaire (11/29).
- **Placement & Rotation :** Les avions sont placés via leurs coordonnées (Lat/Long). L'icône subit une rotation CSS dynamique calculée grâce à la variable `cap` (Heading) envoyée par le réseau ADS-B.

### 3. Filtre Visuel (Le Trafic Local)
La fonction `isBordeauxMovement(avion)` agit comme un filtre de mise en évidence. Si l'avion répond aux critères d'un mouvement local (distance < 15km ET variation d'altitude significative), il est mis en évidence en rouge sur la carte (via `getPlaneIcon`) et dans la liste "Trafic Régional" (fond rosé).

### 4. Focus Liste Textuelle (Trafic Régional)
- **Mécanique :** Boucle sur le tableau global des vols reçus dans le rayon de 15 km.
- **Style Conditionnel :** Exécute la fonction . Si le retour est positif (mouvement local), applique un fond rose () et un texte rouge (). Si le retour est négatif (simple transit), applique un fond blanc () et un texte bleu ().

---
### Session du 19 juillet 2026 : Correction des inversions et Mode Kiosque

#### 1. Inversion Systémique Arrivée/Départ (Backend)
* **Problème :** Le tableau "Programme du jour" affichait des départs à la place des arrivées.
* **Cause :** À la ligne 185 de `backend/api.py`, la règle d'attribution était inversée : `"type": "départ" if sens == "in" else "arrivée"`.
* **Correction :** Rétablissement de la logique nominale : `"type": "arrivée" if sens == "in" else "départ"`. Nettoyage du fichier `scraped_cache.json` et redémarrage du processus.

#### 2. Moteur de Vérité Physique (Frontend)
* **Problème :** Les avions en approche en retard s'associaient à des lignes de "Départ" car la ligne d'arrivée théorique avait été purgée du tableau avec le temps qui passe.
* **Correction :** Réécriture de la logique de matching dans `setAvionClique` (`App.jsx`) :
    * **Priorité absolue à la physique :** Interdiction stricte (malus de -1000 points) de lier un avion qui descend physiquement (`txVert < 0`) à une ligne de décollage théorique.
    * **Tolérance aux retards :** Extension de la recherche à 3 heures dans le passé pour récupérer les lignes masquées.
    * **Auto-Correction :** Le système réécrit le type de vol en direct à l'écran si l'aéroport envoie une donnée erronée, avec la mention `"Corrigé via Radar Live"`.

#### 3. Automatisation du Mode Kiosque (Frontend)
* **Problème :** Le dashboard devait cibler, afficher et scroller automatiquement sur l'avion en alerte mouvement sans intervention manuelle.
* **Correction :** Injection d'un hook `useEffect` basé sur `vols.find(isBordeauxMovement)` :
    * Déclenchement automatique de `setAvionClique` sur l'avion en mouvement dès que l'alerte s'active.
    * **Effets visuels synchronisés :** Icône de la carte en orange vif, ligne sélectionnée dans "Trafic Régional", et centrage persistant au milieu du tableau "Programme du jour".
    * **Persistance :** Les auto-scrolls génériques liés au rafraîchissement des données sont gelés tant que l'alerte pilote l'affichage. Le système se met en pause si l'utilisateur clique manuellement ailleurs.

#### 4. Résolution des Erreurs de Build (Frontend)
* **React is not defined :** Résolu en injectant explicitement `import React from 'react';` au sommet de `App.jsx`.
* **tousLesVols is not defined :** Correction du hook pour cibler la variable d'état réelle de l'application (`vols`).

#### 5. Finalité et Objectif Stratégique du Projet
* **But ultime :** Obtenir des données 100% indépendantes, souveraines et d'une fiabilité technique indiscutable (issues directement de la télémétrie transpondeur brute).
* **Cas d'usage :** Disposer d'un historique physique inattaquable pour confronter les communications officielles de l'aéroport (LFBD). Servir de base factuelle et chiffrée pour argumenter lors des débats concernant l'utilisation des axes de pistes (QFU) et la gestion des nuisances environnementales et sonores (notamment les vols de nuit ou en retard).

### Procédures de maintenance établies
- **Gestion des processus API** : Ne jamais chercher le script python en cas de port occupé, mais cibler le serveur asynchrone (`pkill -9 -f uvicorn`).
- **Gestion du cache** : Le fichier `backend/scraped_cache.json` doit être supprimé avant tout redémarrage pour forcer un re-scraping propre du site de l'aéroport.
- **Couplage vols/radar** : La tolérance de retard a été fixée à 6 heures (21600 secondes) pour éviter les décrochages d'affichage de destination sur le front-end pour les vols du soir.
- **Erreurs de scope Python** : Toujours veiller à importer les modules standards (`datetime`, `timedelta`) au niveau global ou juste avant l'appel conditionnel pour éviter les `UnboundLocalError` lors d'un accès par un autre endpoint. 

### Règles Métier Spécifiques - Pistes et Mouvements (Juillet 2026)
- **Comptage des Décollages/Atterrissages** : Il est strictement INTERDIT d'appliquer la nomenclature officielle de l'aviation pour les statistiques de sens d'utilisation de ce projet. 
- **Règle Physique ("Règle des roues") à appliquer** : 
  - L'atterrissage est enregistré sur la piste où les roues touchent le sol en premier.
  - Le décollage est inversé et enregistré sur la piste opposée de l'axe (là où les roues quittent le sol en dernier).
  - *Exemple* : Sur l'axe 05/23, un atterrissage en 05 implique obligatoirement d'enregistrer le décollage en 23.
- **Dépannage Python rapide** : En cas de `SyntaxError` (notamment lors de l'utilisation de scripts d'injection), toujours cibler les lignes fautives avec `cat -n` et les purger directement avec `sed -i '<debut>,<fin>d' <fichier>` avant de relancer Uvicorn.

### Bloc UI : Répartition globale par axe
- **Définition** : Ce bloc affiche la ventilation du trafic total entre les deux seules infrastructures physiques de l'aéroport : l'axe principal (la bande de bitume 05/23) et l'axe secondaire (la bande de bitume 11/29).
- **Règle de calcul** : Il cumule TOUS les mouvements (atterrissages + décollages) ayant eu lieu sur un axe donné, indépendamment du sens dans lequel les avions ont roulé.
- **Objectif utilisateur** : Permet de comprendre d'un seul coup d'œil quelle piste physique (quel ruban de goudron) est la plus sollicitée sur une période donnée, avant de rentrer dans le détail opérationnel (le "Sens d'utilisation").

### Bloc UI : Sens d'utilisation (QFU)
- **Définition** : Ce bloc détaille la direction (le cap magnétique) prise par les avions sur un axe donné face au vent.
- **Règle de calcul** : Il ventile les sous-compteurs (Décollages/Atterrissages) en appliquant STRICTEMENT la "règle physique" du toucher des roues (atterrissage = piste touchée en premier ; décollage = piste quittée en dernier à l'opposé).
- **Objectif utilisateur** : Savoir précisément comment s'oriente le trafic sur une bande de bitume et vérifier la répartition exacte des départs et des arrivées pour chaque extrémité de piste.

### Architecture et Planification (CRON) - Gestion de minuit
- **Mise à jour du programme** : Le script `check_aerovision.py` s'exécute toutes les 5 minutes pour actualiser les prévisions de vols.
- **Vols "à cheval" sur minuit** : Gérés nativement et sans risque. Si un vol retardé disparaît du programme après minuit, le radar (`detector.py` qui tourne en boucle) l'intercepte physiquement et le classe en "Vol Hors-Planning". Les statistiques ne sont jamais impactées car elles se basent sur l'heure de la détection radar réelle.
- **Maintenance et Reset (03h00)** : Le redémarrage quotidien du backend (`redemarrer_backend.sh`) est volontairement fixé à **03h00 du matin** (heure creuse à l'aéroport LFBD). Cela permet de purger la mémoire sans couper les processus de suivi des vols retardés de la veille.

### Règle de déduplication des mouvements statistiques
- **Problématique** : Un même vol génère plusieurs pings radar durant sa phase d'atterrissage ou de décollage. Un regroupement par minute simple gonfle artificiellement les chiffres de trafic.
- **Règle de correction** : Les statistiques globales et par axe doivent regrouper les données par `callsign` (identifiant unique du vol) et par tranche de 15 minutes (`strftime('%Y-%m-%d %H', horaire_passage)` combiné au callsign) afin de garantir qu'un vol réel ne soit comptabilisé qu'une seule fois.

### 🚨 RÈGLE D'OR ABSOLUE : INTERDICTION DU CONCEPT DE "MOUVEMENT"
- **Objectif** : Le projet ne doit JAMAIS comptabiliser des "mouvements" (pings, minutes, impulsions). Il doit UNIQUEMENT comptabiliser et afficher des **VOLS D'AVIONS UNIQUES**.
- **Logique SQL** : Interdiction d'utiliser des `GROUP BY` temporels lâches pour les statistiques. Utilisation systématique du mot-clé `DISTINCT callsign` par date pour qu'un avion physique avec un indicatif donné ne pèse que pour une seule unité (1 vol) sur le dashboard.

### Règle d'unicité des données (Vols vs Mouvements)
- **Définition stricte** : Le projet a banni la notion de "mouvement" (compter des pings ou des minutes). Il comptabilise et affiche exclusivement des **Vols Uniques**.
- **Logique Backend** : La requête SQL utilise `COUNT(DISTINCT callsign)` pour s'assurer qu'un avion physique n'est compté qu'une seule fois par axe et par période, éliminant les doublons dus au maintien du signal radar sur la piste.
- **Logique Frontend** : Toutes les mentions textuelles de l'interface ont été purgées ("VOL LIVE", "vols", "vols analysés") pour refléter cette exactitude sémantique.

### Règle Métier : Sécurité de Trajectoire (Frontend)
- **Le Malus Physique (-2000)** : Il est formellement interdit d'associer un avion en phase de décollage physique à une ligne d'arrivée du programme (et inversement). Un malus de -2000 points empêche ces faux positifs. La décision s'appuie à la fois sur le taux vertical (`txVert`) et sur la qualification textuelle du radar (`radarDumpLive`) pour gérer les cas d'avions au sol (txVert = 0).

### Règle Métier : Filtre Spatio-Temporel des Pistes (Backend - detector.py)
- **Le problème des pistes croisées** : L'aéroport LFBD possède des pistes sécantes (05/23 et 11/29). Un avion atterrissant sur la 05 roule souvent sur la 11/29 pour rejoindre le terminal, générant de graves faux positifs si l'on se base uniquement sur la géométrie GPS.
- **La Machine à États (Fenêtre de 5 minutes)** : Le système n'enregistre un mouvement sur une piste QUE SI l'avion a été vu "en l'air" (altitude > 200 pieds) dans une fenêtre stricte de 5 minutes (300 secondes) autour de son passage sur la piste. Un avion détecté sur une piste sans historique de vol dans cette fenêtre est définitivement classé comme "roulage au sol", rejeté et purgé.
