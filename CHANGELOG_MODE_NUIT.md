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
