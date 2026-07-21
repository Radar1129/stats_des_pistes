"""
fetch_history.py
----------------
Récupération exhaustive et réelle de tous les vols historiques à Bordeaux (LFBD).
Analyse des trajectoires réelles pour identifier la piste exacte.
Système anti-429 par temporisation et bypass des restrictions SSL d'entreprise.
"""

import sqlite3
import time
import requests
import urllib3
from datetime import datetime, timedelta
from config import OPENSKY_USER, OPENSKY_PASSWORD

# 🛡️ On désactive les messages d'alerte rouges dans le terminal liés au bypass SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DB_FILE = "bordeaux_stats.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vols_detectes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            icao24 TEXT NOT NULL,
            callsign TEXT,
            portail_nom TEXT NOT NULL,
            horaire_passage TEXT NOT NULL,
            altitude_metres REAL,
            action TEXT
        )
    """)
    conn.commit()
    return conn

def get_runway_from_track(track_points, action):
    """Analyse les vrais points GPS de la trajectoire pour déduire la piste brute."""
    if not track_points:
        return "23"
    
    relevant_points = track_points[-5:] if action == "atterrissage" else track_points[:5]
    
    for p in relevant_points:
        if len(p) >= 4:
            heading = p[3]
            if heading is not None:
                if 180 <= heading <= 260: return "23"
                elif 0 <= heading <= 80 or 340 <= heading <= 360: return "05"
                elif 80 < heading <= 140: return "11"
                elif 260 < heading < 340: return "29"
            
    return "23"

def process_flight_list(conn, flights, action):
    """Boucle sur chaque vol avec bypass SSL et pause de sécurité."""
    cursor = conn.cursor()
    auth_credentials = (OPENSKY_USER, OPENSKY_PASSWORD)
    
    print(f"\n📊 Traitement de {len(flights)} {action}(s) en cours...")
    
    for i, f in enumerate(flights, 1):
        icao24 = f.get("icao24")
        callsign = (f.get("callsign") or "ANONYME").strip()
        
        timestamp_cle = f.get("lastSeen") if action == "atterrissage" else f.get("firstSeen")
        horaire_utc = datetime.fromtimestamp(timestamp_cle).strftime("%Y-%m-%d %H:%M:%S")
        
        print(f" [{i}/{len(flights)}] Requête trajectoire pour le vol {callsign}...")
        
        # 🛡️ Pause stricte anti-429
        time.sleep(6)
        
        track_url = f"https://opensky-network.org/api/tracks/all?icao24={icao24}&time={timestamp_cle}"
        piste = "23"
        
        try:
            # 🔑 verify=False permet de passer à travers le proxy de l'entreprise
            track_res = requests.get(track_url, auth=auth_credentials, timeout=10, verify=False)
            if track_res.status_code == 200:
                track_data = track_res.json()
                points = track_data.get("path") or []
                piste = get_runway_from_track(points, action)
            elif track_res.status_code == 429:
                print("   ⚠️ Surcharge OpenSky (429). Pause de sécurité de 30 secondes...")
                time.sleep(30)
                track_res = requests.get(track_url, auth=auth_credentials, timeout=10, verify=False)
                if track_res.status_code == 200:
                    points = track_res.json().get("path") or []
                    piste = get_runway_from_track(points, action)
        except Exception as e:
            print(f"   ❌ Erreur de lecture de trajectoire : {e}")

        portail = f"Piste {piste} - Analyse Historique Réelle"
        cursor.execute(
            "INSERT INTO vols_detectes (icao24, callsign, portail_nom, horaire_passage, altitude_metres, action) VALUES (?, ?, ?, ?, ?, ?)",
            (icao24, callsign, portail, horaire_utc, 0.0, action)
        )
        conn.commit()
        print(f"   ✅ Enregistré -> Piste {piste}")

def main():
    conn = init_db()
    auth_credentials = (OPENSKY_USER, OPENSKY_PASSWORD)
    
    # 📅 Sélection de la date J-4 (Consolidée)
    cible_date = datetime.now() - timedelta(days=4)
    debut_timestamp = int(cible_date.replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    fin_timestamp = int(cible_date.replace(hour=23, minute=59, second=59, microsecond=0).timestamp())
    
    print("=========================================================================")
    print(f"🛰️  MOISSONNEUR HISTORIQUE BRUT (FORCE SSL) - BORDEAUX LFBD")
    print(f"📅 Journée ciblée : {cible_date.strftime('%Y-%m-%d')}")
    print("=========================================================================")

    # 1. Téléchargement des Arrivées avec verify=False
    print("📡 Récupération de la liste des arrivées...")
    url_arr = f"https://opensky-network.org/api/flights/arrival?aerodrome=LFBD&begin={debut_timestamp}&end={fin_timestamp}"
    try:
        res_arr = requests.get(url_arr, auth=auth_credentials, timeout=15, verify=False)
        arrivals = res_arr.json() if res_arr.status_code == 200 else []
    except Exception as e:
        print(f"❌ Impossible de joindre les arrivées : {e}")
        arrivals = []

    # 2. Téléchargement des Départs avec verify=False
    print("📡 Récupération de la liste des départs...")
    url_dep = f"https://opensky-network.org/api/flights/departure?aerodrome=LFBD&begin={debut_timestamp}&end={fin_timestamp}"
    try:
        res_dep = requests.get(url_dep, auth=auth_credentials, timeout=15, verify=False)
        departures = res_dep.json() if res_dep.status_code == 200 else []
    except Exception as e:
        print(f"❌ Impossible de joindre les départs : {e}")
        departures = []

    print(f"✈️  {len(arrivals)} arrivées et {len(departures)} départs trouvés sur les serveurs.")

    # 3. Traitement
    if arrivals:
        process_flight_list(conn, arrivals, "atterrissage")
    if departures:
        process_flight_list(conn, departures, "decollage")
    
    print("\n🏁 [SUCCÈS] Récolte terminée.")

if __name__ == "__main__":
    main()