"""
detector.py
-----------
Script de détection en arrière-plan. Il surveille l'API ADS-B,
analyse le cap et la position des avions autour de Mérignac,
et enregistre les mouvements dans la base de données SQLite.
"""

import time
import sqlite3
import requests

DB_FILE = "bordeaux_stats.db"
API_URL = "https://api.adsb.lol/v2/lat/44.8283/lon/-0.7156/dist/15"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vols_detectes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            callsign TEXT,
            portail_nom TEXT,
            action TEXT,
            horaire_passage TEXT,
            altitude_metres REAL,
            origine TEXT,
            destination TEXT,
            UNIQUE(callsign, horaire_passage)
        )
    """)
    conn.commit()
    conn.close()

def determiner_piste_et_action(cap, alt_pieds, taux_vertical):
    """
    Détermine la piste exacte (05, 23, 11, 29) et l'action (atterrissage/décollage)
    en fonction du cap de l'avion et de sa trajectoire verticale.
    """
    if cap is None:
        return None, None

    # 1. Détermination de la piste selon le cap (marge de 30 degrés autour de l'axe)
    piste = None
    if 35 <= cap <= 95:
        piste = "Piste 05"
    elif 215 <= cap <= 275:
        piste = "Piste 23"
    elif 95 < cap < 155:
        piste = "Piste 11"
    elif 275 < cap < 335:
        piste = "Piste 29"
        
    if not piste:
        return None, None

    # 2. Détermination de l'action (Atterrissage vs Décollage)
    # On utilise le taux vertical (baro_rate). Si négatif = descente, si positif = montée.
    # En secours, si l'altitude est très basse (< 1000 pieds), on estime un atterrissage.
    if taux_vertical is not None:
        if taux_vertical < -100:
            action = "atterrissage"
        elif taux_vertical > 100:
            action = "décollage"
        else:
            action = "atterrissage" if alt_pieds < 1500 else "passage"
    else:
        action = "atterrissage" if alt_pieds < 1500 else "passage"

    # On ignore les avions qui ne font que survoler la zone à moyenne altitude
    if action == "passage":
        return None, None

    return piste, action

def surveiller_ciel():
    init_db()
    print("📡 Radar de détection LFBD activé (4 pistes distinctes)...")
    
    while True:
        try:
            response = requests.get(API_URL, timeout=5)
            if response.status_code == 200:
                data = response.json()
                avions = data.get("ac", [])
                
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                
                for avion in avions:
                    callsign = avion.get("flight", "").strip()
                    if not callsign or callsign == "ANONYME":
                        continue
                        
                    alt_pieds = avion.get("alt_baro", 0)
                    # On ne traite que les avions proches du sol (approche ou décollage < 4500 pieds)
                    if isinstance(alt_pieds, (int, float)) and alt_pieds < 4500:
                        cap = avion.get("track")
                        taux_vertical = avion.get("baro_rate") # Pieds par minute
                        
                        piste, action = determiner_piste_et_action(cap, alt_pieds, taux_vertical)
                        
                        if piste and action:
                            horaire = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
                            alt_metres = int(alt_pieds * 0.3048)
                            
                            try:
                                cursor.execute("""
                                    INSERT INTO vols_detectes 
                                    (callsign, portail_nom, action, horaire_passage, altitude_metres, origine, destination)
                                    VALUES (?, ?, ?, ?, ?, ?, ?)
                                """, (callsign, piste, action, horaire, alt_metres, "Inconnu", "Inconnu"))
                                conn.commit()
                                print(f"✨ [{horaire}] {callsign} détecté en {action} sur la {piste} ({alt_metres}m)")
                            except sqlite3.IntegrityError:
                                # Évite les doublons si l'avion est déjà enregistré à la même seconde
                                pass
                                
                conn.close()
        except Exception as e:
            print(f"⚠️ Erreur de liaison API: {e}")
            
        time.sleep(10)

if __name__ == "__main__":
    surveiller_ciel()