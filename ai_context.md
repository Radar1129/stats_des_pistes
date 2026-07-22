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

### 🚨 DIRECTIVES DE COMPORTEMENT OBLIGATOIRES POUR L'IA (MÉTHODOLOGIE) 🚨

1. **LECTURE PRÉALABLE :** Tu dois lire entièrement les fichiers `PROJECT_INDEX.md` et `GLOSSARY.md` du projet, ainsi que les fichiers liés au contexte (`ai-context`, `memory`, `documentation`) avant de commencer à travailler.
2. **ZÉRO SUPPOSITION SYNTAXIQUE :** Toute tentative de code nouveau doit impérativement éviter les erreurs d'accents, de typage ou de casse (ex: "décollage" vs "decollage"). Tu dois D'ABORD demander à lire les fichiers et le code du projet pour utiliser la nomenclature exacte avant de pondre le moindre code.
3. **VÉRIFICATION DE L'EXISTANT :** Tu ne dois jamais coder de choses nouvelles sans vérifier que la logique demandée n'est pas déjà présente. Ton réflexe systématique doit être de demander à voir le code existant avant d'en écrire un nouveau.
4. **NOMENCLATURE RÉELLE :** Tu dois demander à voir comment s'appellent les fichiers, les variables ou les tables de la base de données existantes avant de vouloir en créer de nouvelles ou d'inventer des noms au hasard.


--- 
## 🧠 Mémoire Projets & Notes Consolidées

### Content from project_memory.md:

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

## Mise à jour (Juillet 2026) : Résolution de bugs critiques et Automatisation
- **Bug du Port 8000 bloqué** : Un ancien processus Uvicorn tournait en tâche de fond (zombie) rendant la commande `pkill -f api.py` inefficace. Remplacé par `pkill -9 -f uvicorn` pour tuer les processus proprement.
- **Création du script d'autoréparation** : Création de `redemarrer_backend.sh` qui force la fermeture de l'API, supprime le cache de la veille (`scraped_cache.json`) et relance l'API.
- **Automatisation nocturne (Cron)** : Mise en place d'une tâche Cron `0 3 * * *` pour exécuter le script de redémarrage tous les jours à 03h00 du matin et repartir sur une base vierge sans intervention manuelle.
- **Décrochage d'affichage Radar (Vol sans destination)** : Le couplage radar-programme plantait pour les vols avec un fort retard. La limite `diff_sec` dans `api.py` a été augmentée de `9000` (2h30) à `21600` (6h) pour garder l'info de provenance/destination (ex: Marseille) même sur les gros retards de fin de journée.
- **Erreur 500 (UnboundLocalError)** : L'API plantait lors du rechargement à cause d'un import de `timedelta` mal scopé dans `get_vols_expected`. Corrigé en injectant `from datetime import timedelta` juste avant son utilisation à la ligne 317.

## Mise à jour (20 Juillet 2026 à 02:00) : Logique physique des pistes et correction API
- **Logique Métier des Pistes** : Changement du mode de comptage des mouvements. Abandon de la logique aéronautique officielle au profit d'une logique physique (basée sur la position du toucher/décollage des roues sur le bitume).
  - Règle appliquée : Si un avion atterrit sur une extrémité de piste (ex: 05), les décollages sur cet axe se font nécessairement vers l'autre extrémité (ex: 23).
  - Inversion codée dans `api.py` (`get_stats_historique`) : Pour tout décollage détecté, le numéro de piste est basculé vers son opposé sur l'axe (05 <-> 23, 11 <-> 29).
- **Résolution de Bug SyntaxError** : L'injection du code de bascule a généré un double `else:` (erreur 500 / "Unexpected token"). Corrigé via la suppression des lignes redondantes avec `sed -i '436,437d'` et redémarrage du backend.
- **Résultat** : Les sous-compteurs de pistes (Décollages/Atterrissages) fonctionnent désormais correctement et croisent parfaitement l'axe et le sens.

## Mise à jour (20 Juillet 2026, 02h25) : UI/UX et Audit de fiabilité
- **Frontend (React)** : Injection réussie des infobulles explicatives pour les blocs "Répartition globale par Axe" et "Sens d'utilisation (QFU)" directement dans le build minifié de production. (Solution technique : utilisation d'une Regex et de `chr(39)` dans le script Python pour contourner les conflits d'échappement Bash/Python sur les apostrophes).
- **Audit des tâches planifiées (CRON)** : Vérification de la fiabilité du système au basculement de minuit. Confirmation que l'architecture est robuste : les requêtes API redémarrent bien à 00:00:00 (Fuseau Paris) pour les statistiques, mais le reset du serveur est décalé à 03h00 du matin pour sécuriser le suivi live des atterrissages et décollages tardifs.

## Mise à jour (20 Juillet 2026, 02h42) : Passage au modèle de "Vol Unique"
- **Backend (api.py)** : Correction de la fonction `get_stats_historique`. Remplacement du regroupement par minute par un décompte de `DISTINCT callsign` pour éliminer la multiplication artificielle des chiffres. Réparation d'une erreur d'indentation et de syntaxe de la ligne 395.
- **Frontend (Assets JS)** : Script de nettoyage dynamique appliqué sur l'ensemble des fichiers `index-*.js` pour remplacer définitivement les termes "mouvements" par "vols" sur l'interface graphique (Titres, alertes et compteurs d'axes). Validation des modifications après purge du cache navigateur.

## Mise à jour (20 Juillet 2026, 10h00) : Fiabilisation absolue du moteur de vérité
- **Frontend (App.jsx) - Sécurité de matching croisé** : Correction d'une faille où des avions au sol ou en accélération (txVert = 0) étaient associés à des vols de sens opposé en raison d'une lecture naïve du tableau commercial. Implémentation d'un malus brutal de `-2000 points` forçant la stricte ségrégation Arrivée / Départ du radar.
- **Backend (detector.py) - Filtre Spatio-Temporel** : Abandon du simple filtre géométrique pour les pistes croisées (11/29 vs 05/23) responsable de nombreux faux positifs lors du roulage au sol des avions. Création d'une machine à états : tout mouvement sur piste est désormais mis en attente (`vols_en_attente`), et n'est validé (`INSERT INTO vols_detectes`) que s'il est corrélé à une détection confirmée en vol (`> 200 pieds`) dans une fenêtre de 5 minutes.


### Content from memory.md:
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


### Content from MEMORY.md:
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

## 5. Règle d'Or Absolue : Rigueur Chirurgicale
- Interdiction stricte des scripts `sed`/regex globaux aveugles (risque de corruption JS/SQL).
- Les modifications de code doivent être d'une précision absolue (cibler uniquement les lignes concernées).
- Analyse d'impact obligatoire sur toute la stack avant toute proposition de script.


### Content from ai-context.md:
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

## 5. Règle d'Or Absolue : Rigueur Chirurgicale
- **Interdiction formelle des remplacements en masse** : Ne JAMAIS utiliser de `sed` ou de regex globales aveugles pour modifier du texte ou des variables. Cela corrompt la logique interne (JS, SQL, JSON).
- **Chirurgie uniquement** : Toute modification de code doit cibler avec une précision absolue la ligne ou la fonction concernée. Si une modification purement visuelle (texte) est demandée, cibler exclusivement le code HTML/UI, jamais le backend ou les clés de données.
- **Analyse d'impact obligatoire** : L'IA doit systématiquement évaluer l'effet domino de ses propositions sur l'ensemble de la stack (FastAPI, Pydantic, SQLite, Vanilla JS) avant de soumettre un correctif. Tolérance zéro pour le code destructif.

5. **TRANSPARENCE DE LA MÉMOIRE (CONTEXT WINDOW) :** L'IA a l'obligation stricte d'avertir l'utilisateur si la longueur de la conversation lui fait perdre de vue les règles d'or du projet. En cas de moindre doute sur une logique métier (règles de pistes, nomenclatures, interdiction du mot "mouvement"), l'IA doit stopper toute proposition de code et demander à faire un grep ou relire le contexte pour éviter toute hallucination.

---
### 🚨 LEÇONS APPRISES & RÈGLES DE DÉVELOPPEMENT (Mise à jour Juillet 2026)

6. **MÉTHODOLOGIE "LENT ET SÛR" (ZÉRO BLIND-CODE) :** Toute modification de code doit suivre ce protocole strict :
   - **Lecture seule d'abord :** L'IA doit toujours demander un `grep` ou `sed` pour lire l'état exact du fichier avant d'écrire.
   - **Injection Python :** Utiliser des mini-scripts Python pour faire des remplacements de blocs de texte précis (avec vérification `if old_block in content`). Fini les `echo` ou `sed` qui cassent la syntaxe.

7. **LA RÈGLE DU BUILD (FRONTEND) :** Le projet est servi par un serveur web (IP publique). Toute modification dans `frontend/src/` n'aura **AUCUN EFFET VISUEL** tant que l'application n'est pas recompilée.
   - Action obligatoire après modification : `cd ~/stats_des_pistes/frontend && npm run build`
   - Toujours faire un vidage de cache (Ctrl + F5) sur le navigateur ensuite.

8. **PIÈGES TECHNIQUES CONNUS :**
   - **Forcer le rendu Leaflet (Le piège de la Key) :** React-Leaflet ne met pas toujours à jour une icône si le marqueur existe déjà. Pour forcer un changement visuel conditionnel, il faut altérer sa clé : `key={index + (isPrincipal ? "-live" : "")}`.
   - **Bypass CSS Leaflet :** Pour agrandir dynamiquement une icône `L.DivIcon`, il faut modifier `iconSize` et `iconAnchor`, MAIS AUSSI retirer ou changer le `className` pour éviter qu'une règle CSS globale ne bride la taille.
   - **Comparaison de vols (Le piège des espaces) :** Les données ADS-B contiennent souvent des espaces invisibles dans les numéros de vol (`"EZY34GB   "`). Pour comparer deux avions, toujours utiliser `.callsign.trim()` ou vérifier l'objet en mémoire (`avion1 === avion2`).

## 🔄 État de la Collecte & Backend (Mise à jour 2026-07-22)

- **Collecteur (`collector.py`)** :
  - Tourne en tâche de fond via `nohup` (`./venv/bin/python collector.py > collector.log 2>&1 &`).
  - Scrape l'API AJAX de l'aéroport de Bordeaux toutes les 5 min.
  - Fenêtre glissante de 3 jours ($J-1$, $J$, $J+1$) pour anticiper et garder l'historique sans rupture à minuit.

- **Base de données (`lfbd_schedule.db`)** :
  - Emplacement : `/home/ubuntu/stats_des_pistes/lfbd_schedule.db`
  - Table principale : `flights` (champs : `uid`, `direction`, `scheduled_date`, `scheduled_time`, `origin_dest`, `callsign`, `airline`, `status`, `updated_at`).

- **API Backend (`backend/api.py`)** :
  - Endpoint `/api/vols/expected` : Lit directement dans `lfbd_schedule.db` filtré sur `scheduled_date = date('now')`.
  - Processus Uvicorn sur port `8000`.

## 🔄 État du Radar en Direct (Mise à jour 2026-07-22)
- **Route `/api/vols/direct`** : Ne dépend plus d'une source unique. Interroge en parallèle (`ThreadPoolExecutor`) les API communautaires (`adsb.lol` et `opendata.adsb.fi`) avec un timeout strict de 3 secondes pour garantir la fluidité du frontend Leaflet et éviter tout point de défaillance unique.
- **Processus** : Les scripts isolés `live_radar.py` tournant en boucle (processus zombies) ont été purgés.

## 🔄 Architecture de Redémarrage (Mise à jour 2026-07-23)
- **Script global (`redemarrer_backend.sh`)** : Gère désormais de façon unifiée le frontend/API et les daemons de collecte. La commande `pkill -9` cible obligatoirement `uvicorn`, `api.py`, `live_radar.py` et `detector.py` avant de tout relancer via `nohup`.
- **Leçon apprise (Le paradoxe du Live vs Historique)** : Une alerte "Live" UI peut fonctionner parfaitement via les appels React directs, même si le backend d'enregistrement physique (`detector.py`) est mort. La présence des coches "✓ Détecté" dans le tableau dépend exclusivement de la survie du script `detector.py` et de ses écritures dans `bordeaux_stats.db`.

## 🌍 Gestion des Fuseaux Horaires (Leçon apprise)
- **Heure Serveur vs Heure Locale** : Le serveur Ubuntu opérant par défaut en UTC, toutes les comparaisons de dates dans l'API (notamment pour le programme du jour) doivent explicitement forcer le fuseau horaire `Europe/Paris` (via `pytz` ou un delta temporel sécurisé) pour éviter des incohérences d'affichage entre minuit et 02h00 du matin.
