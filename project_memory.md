
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
