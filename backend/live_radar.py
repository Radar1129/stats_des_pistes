import sqlite3
import time
import requests
from datetime import datetime

DB_FILE = "bordeaux_stats.db"

LAMIN, LAMAX = 44.65, 45.00
LOMIN, LOMAX = -0.95, -0.45

tracked_flights = {}

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
            action TEXT,
            origine TEXT DEFAULT 'Inconnu',
            destination TEXT DEFAULT 'Inconnu'
        )
    """)
    try:
        cursor.execute("ALTER TABLE vols_detectes ADD COLUMN origine TEXT DEFAULT 'Inconnu'")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE vols_detectes ADD COLUMN destination TEXT DEFAULT 'Inconnu'")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    return conn

def get_route_info(callsign):
    if not callsign or callsign == "ANONYME":
        return "Inconnu", "Inconnu"
    
    callsign_clean = callsign.strip().upper()
    try:
        res = requests.get(f"https://api.adsb.lol/v2/route-icao/{callsign_clean}", timeout=3)
        if res.status_code == 200:
            data = res.json()
            route = data.get("route", {}) if "route" in data else data
            origine = route.get("from") or route.get("origin") or "Inconnu"
            destination = route.get("to") or route.get("destination") or "Inconnu"
            return origine, destination
    except Exception:
        pass
    return "Inconnu", "Inconnu"

def get_runway_from_heading(heading):
    if heading is None: return "23"
    # Marges resserrées pour éviter les faux positifs lors des virages
    if 190 <= heading <= 250: return "23"
    elif 10 <= heading <= 70: return "05"
    elif 90 <= heading <= 130: return "11"
    elif 270 <= heading <= 310: return "29"
    
    # Par défaut, on le rabat sur l'axe principal s'il est un peu de travers
    if heading > 130 and heading < 310: return "23"
    return "05"

def log_event(conn, icao24, callsign, piste, altitude, action):
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    portail = f"Piste {piste}"
    
    cursor.execute(
        "SELECT 1 FROM vols_detectes WHERE icao24 = ? AND action = ? AND horaire_passage > datetime('now', '-1 hour')",
        (icao24, action)
    )
    if cursor.fetchone() is None:
        origine, destination = get_route_info(callsign)
        
        cursor.execute(
            """INSERT INTO vols_detectes 
               (icao24, callsign, portail_nom, horaire_passage, altitude_metres, action, origine, destination) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (icao24, callsign, portail, now_str, altitude, action, origine, destination)
        )
        conn.commit()
        print(f"🎉 [SUCCÈS] Vol {callsign} ({origine} ➔ {destination}) enregistré ! (Piste {piste} - {action} à {int(altitude)}m)")

def main():
    conn = init_db()
    url = "https://api.adsb.lol/v2/lat/44.8283/lon/-0.7156/dist/50"

    print("🛰️  Démarrage de la surveillance via le flux global... En attente d'avions...")

    while True:
        try:
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                data = res.json()
                aircraft = data.get("ac") or []
                now = time.time()
                
                for s in aircraft:
                    lat = s.get("lat")
                    lon = s.get("lon")
                    if lat is None or lon is None:
                        continue
                        
                    if not (LAMIN <= lat <= LAMAX and LOMIN <= lon <= LOMAX):
                        continue
                        
                    icao24 = s.get("hex", "").upper()
                    callsign = s.get("flight", "ANONYME").strip()
                    heading = s.get("track")
                    
                    alt_baro = s.get("alt_baro")
                    on_ground = (alt_baro == "ground")
                    
                    if on_ground:
                        altitude = 0
                    elif isinstance(alt_baro, (int, float)):
                        altitude = alt_baro * 0.3048
                    else:
                        continue
                        
                    # On abaisse le déclencheur à 600m (env. 2000 pieds) 
                    # À cette altitude, l'avion est obligatoirement aligné sur l'axe final de la piste.
                    if altitude < 600:
                        piste = get_runway_from_heading(heading)
                        
                        if icao24 not in tracked_flights:
                            tracked_flights[icao24] = {
                                "last_alt": altitude, 
                                "logged": False, 
                                "hits": 1, 
                                "last_seen": now
                            }
                        else:
                            tracked_flights[icao24]["hits"] += 1
                            tracked_flights[icao24]["last_seen"] = now
                            old_alt = tracked_flights[icao24]["last_alt"]
                            
                            if not tracked_flights[icao24]["logged"]:
                                if altitude < old_alt:
                                    log_event(conn, icao24, callsign, piste, altitude, "atterrissage")
                                    tracked_flights[icao24]["logged"] = True
                                elif altitude > old_alt:
                                    log_event(conn, icao24, callsign, piste, altitude, "decollage")
                                    tracked_flights[icao24]["logged"] = True
                            
                            tracked_flights[icao24]["last_alt"] = altitude

                for icao, flight_info in list(tracked_flights.items()):
                    if now - flight_info["last_seen"] > 60:
                        del tracked_flights[icao]
                        
        except Exception as e:
            pass
            
        time.sleep(10)

if __name__ == "__main__":
    main()