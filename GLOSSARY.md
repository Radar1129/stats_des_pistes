# GLOSSAIRE ET RÈGLES DE TYPAGE STRICTES

## 1. NOMENCLATURE ABSOLUE
- **Vols vs Mouvements** : INTERDICTION d'utiliser le terme "mouvements" pour compter. On compte des `Vols Uniques` (via `DISTINCT callsign`).
- **Pistes (QFU)** : 
  - `05/23` = Axe principal.
  - `11/29` = Axe secondaire.
- **Règle des roues** : Atterrissage = première piste touchée. Décollage = piste opposée de l'axe (dernière quittée).

## 2. CLÉS DE DONNÉES (JSON / Python)
- `type` : "Arrivée" ou "Départ" (avec majuscule, jamais "in/out").
- `statut` : "Programmé", "Atterri", "Décollé", "Retardé" (jamais "status").
- `heure` : Format "HH:MM" (jamais "time").
- `ville` : Destination ou provenance (jamais "city").
- `compagnie` : Nom complet ou code (ex: AFR, EZY).

## 3. VARIABLES RADAR (ADS-B)
- `txVert` : Taux vertical (négatif = descente, positif = montée).
- `altM` : Altitude en mètres (convertie depuis les pieds).
- `cap` : Heading (orientation de l'avion, de 0 à 360).
