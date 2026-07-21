"""
test_portails.py
----------------
Radar de surveillance des portails d'approche de l'aéroport de
Bordeaux-Mérignac (LFBD) avec persistance SQLite.

Pour chaque seuil de piste (05, 23, 11, 29), deux portails sont définis :
    - un portail "lointain" à environ 5 km du seuil
    - un portail "proche" à environ 1 km du seuil

Le script tourne en boucle infinie, interroge l'API OpenSky toutes les
30 secondes, et enregistre les passages d'avions dans une base SQLite
(bordeaux_stats.db), en évitant les doublons sur une fenêtre de 5 min.
"""

import math
import sqlite3
import time
from datetime import datetime, timedelta

import requests

# Import des coordonnées globales de la zone de surveillance
# (LAT_MIN, LAT_MAX, LON_MIN, LON_MAX attendues dans config.py)
from config import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX


# ---------------------------------------------------------------------------
# CONSTANTES
# ---------------------------------------------------------------------------

OPENSKY_URL = "https://opensky-network.org/api/states/all"

# Intervalle entre deux scans (en secondes)
SCAN_INTERVAL = 30

# Fenêtre anti-doublons (en minutes)
DEDUP_WINDOW_MINUTES = 5

# Fichier de base de données SQLite
DB_FILE = "bordeaux_stats.db"

# Demi-côté d'un portail (en degrés). ~0.005° ≈ 550 m de côté total.
PORTAL_HALF_SIZE_DEG = 0.005

# Coordonnées approximatives des seuils de piste de LFBD
RUNWAY_THRESHOLDS = {
    "05": {"lat": 44.8128, "lon": -0.7361, "heading": 47},
    "23": {"lat": 44.8478, "lon": -0.6928, "heading": 227},
    "11": {"lat": 44.8389, "lon": -0.7256, "heading": 110},
    "29": {"lat": 44.8275, "lon": -0.7044, "heading": 290},
}

# Distances des deux portails par rapport au seuil (en km)
PORTAL_DISTANCES_KM = {"lointain": 5.0, "proche": 1.0}


# ---------------------------------------------------------------------------
# BASE DE DONNÉES
# ---------------------------------------------------------------------------

def init_database():
    """
    Crée le fichier SQLite et la table vols_detectes si nécessaires.
    Retourne la connexion ouverte.
    """
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS vols_detectes (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            icao24            TEXT    NOT NULL,
            callsign          TEXT,
            portail_nom       TEXT    NOT NULL,
            horaire_passage   TEXT    NOT NULL,
            altitude_metres   REAL,
            action            TEXT
        )
        """
    )
    # Index pour accélérer la recherche anti-doublons
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_vols_dedup
        ON vols_detectes (icao24, portail_nom, horaire_passage)
        """
    )
    conn.commit()
    return conn


def already_recorded_recently(conn, icao24, portail_nom):
    """
    Vérifie si l'avion identifié par icao24 a déjà été enregistré dans
    le portail portail_nom dans les DEDUP_WINDOW_MINUTES dernières minutes.
    """
    cutoff = (datetime.now() - timedelta(minutes=DEDUP_WINDOW_MINUTES)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 1 FROM vols_detectes
        WHERE icao24 = ?
          AND portail_nom = ?
          AND horaire_passage >= ?
        LIMIT 1
        """,
        (icao24, portail_nom, cutoff),
    )
    return cursor.fetchone() is not None


def insert_detection(conn, icao24, callsign, portail_nom, horaire, altitude, action):
    """Insère une nouvelle ligne de détection dans la base."""
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO vols_detectes
            (icao24, callsign, portail_nom, horaire_passage, altitude_metres, action)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (icao24, callsign, portail_nom, horaire, altitude, action),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# CALCUL DES PORTAILS
# ---------------------------------------------------------------------------

def offset_position(lat, lon, distance_km, bearing_deg):
    """
    Calcule une nouvelle position géographique à partir d'une position
    de départ, d'une distance (km) et d'un cap (degrés vrais).
    """
    R = 6371.0
    bearing = math.radians(bearing_deg)
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)

    lat2 = math.asin(
        math.sin(lat1) * math.cos(distance_km / R)
        + math.cos(lat1) * math.sin(distance_km / R) * math.cos(bearing)
    )
    lon2 = lon1 + math.atan2(
        math.sin(bearing) * math.sin(distance_km / R) * math.cos(lat1),
        math.cos(distance_km / R) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), math.degrees(lon2)


def build_portals():
    """
    Construit la liste des 8 portails (2 par seuil de piste).

    Retourne un dictionnaire :
        { "nom_portail": {
              "bbox": (lat_min, lat_max, lon_min, lon_max),
              "runway": "05",
              "type": "lointain" | "proche"
          }, ... }
    """
    portals = {}

    for runway, info in RUNWAY_THRESHOLDS.items():
        # L'axe d'approche est dans la direction opposée au cap de la piste
        approach_bearing = (info["heading"] + 180) % 360

        for label, dist_km in PORTAL_DISTANCES_KM.items():
            center_lat, center_lon = offset_position(
                info["lat"], info["lon"], dist_km, approach_bearing
            )
            bbox = (
                center_lat - PORTAL_HALF_SIZE_DEG,
                center_lat + PORTAL_HALF_SIZE_DEG,
                center_lon - PORTAL_HALF_SIZE_DEG,
                center_lon + PORTAL_HALF_SIZE_DEG,
            )
            portal_name = f"Piste {runway} - portail {label} ({int(dist_km)} km)"
            portals[portal_name] = {
                "bbox": bbox,
                "runway": runway,
                "type": label,
            }

    return portals


# ---------------------------------------------------------------------------
# DÉDUCTION DÉCOLLAGE / ATTERRISSAGE
# ---------------------------------------------------------------------------

def deduce_action(conn, icao24, runway, portal_type):
    """
    Déduit si l'avion est en train de décoller ou d'atterrir.
    
    Logique séquentielle :
        - Portail LOINTAIN puis PROCHE = ATTERRISSAGE.
        - Portail PROCHE puis LOINTAIN = DÉCOLLAGE.
    """
    cursor = conn.cursor()
    cutoff = (datetime.now() - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        """
        SELECT portail_nom, horaire_passage
        FROM vols_detectes
        WHERE icao24 = ?
          AND portail_nom LIKE ?
          AND horaire_passage >= ?
        ORDER BY horaire_passage DESC
        LIMIT 1
        """,
        (icao24, f"Piste {runway}%", cutoff),
    )
    previous = cursor.fetchone()

    if previous is not None:
        prev_name = previous[0]
        if "lointain" in prev_name and portal_type == "proche":
            return "atterrissage"
        if "proche" in prev_name and portal_type == "lointain":
            return "decollage"

    if portal_type == "proche":
        return "atterrissage_probable"
    return "indetermine"


# ---------------------------------------------------------------------------
# REQUÊTE OPENSKY
# ---------------------------------------------------------------------------

def fetch_aircraft_states():
    """Interroge l'API OpenSky et retourne (timestamp, [états])."""
    params = {
        "lamin": LAT_MIN,
        "lamax": LAT_MAX,
        "lomin": LON_MIN,
        "lomax": LON_MAX,
    }
    try:
        response = requests.get(OPENSKY_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        print(f"[ERREUR] Échec de la requête OpenSky : {exc}")
        return None, []
    except ValueError as exc:
        print(f"[ERREUR] Réponse JSON invalide : {exc}")
        return None, []

    if not data or "states" not in data or data["states"] is None:
        return data.get("time") if data else None, []
    return data.get("time"), data["states"]


# ---------------------------------------------------------------------------
# UTILITAIRES
# ---------------------------------------------------------------------------

def is_inside_bbox(lat, lon, bbox):
    """Vérifie si un point (lat, lon) est dans une bounding box."""
    lat_min, lat_max, lon_min, lon_max = bbox
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def format_timestamp_full(unix_ts):
    """Convertit un timestamp Unix en chaîne 'YYYY-MM-DD HH:MM:SS.mmm'."""
    if unix_ts is None:
        unix_ts = time.time()
    dt = datetime.fromtimestamp(unix_ts)
    ms = int((unix_ts - int(unix_ts)) * 1000)
    return dt.strftime("%Y-%m-%d %H:%M:%S") + f".{ms:03d}"


def current_time_short():
    """Retourne l'heure actuelle au format 'HH:MM:SS'."""
    return datetime.now().strftime("%H:%M:%S")


# ---------------------------------------------------------------------------
# DÉTECTION + ENREGISTREMENT
# ---------------------------------------------------------------------------

def process_aircraft(conn, states, portals, capture_time):
    """Vérifie la présence dans un portail et persiste en base SQLite."""
    horaire_str = format_timestamp_full(capture_time)
    new_records = 0

    for state in states:
        try:
            icao24 = state[0]
            callsign = (state[1] or "").strip() or None
            lon = state[5]
            lat = state[6]
            baro_alt = state[7]
            geo_alt = state[13]
        except (IndexError, TypeError):
            continue

        if lat is None or lon is None or icao24 is None:
            continue

        altitude = geo_alt if geo_alt is not None else baro_alt

        for portal_name, portal_info in portals.items():
            if not is_inside_bbox(lat, lon, portal_info["bbox"]):
                continue

            if already_recorded_recently(conn, icao24, portal_name):
                continue

            action = deduce_action(
                conn, icao24, portal_info["runway"], portal_info["type"]
            )

            insert_detection(
                conn,
                icao24=icao24,
                callsign=callsign,
                portail_nom=portal_name,
                horaire=horaire_str,
                altitude=altitude,
                action=action,
            )
            new_records += 1

            alt_str = f"{altitude:.0f} m" if altitude is not None else "inconnue"
            print(
                f"  [BDD ✓] {horaire_str} | "
                f"{callsign or 'N/A'} (ICAO24={icao24}) "
                f"→ « {portal_name} » | "
                f"Altitude : {alt_str} | Action : {action}"
            )

    return new_records


# ---------------------------------------------------------------------------
# PROGRAMME PRINCIPAL
# ---------------------------------------------------------------------------

def main():
    print("=== Radar LFBD avec persistance SQLite ===")
    print(f"Base de données   : {DB_FILE}")
    print(f"Intervalle scan   : {SCAN_INTERVAL} s")
    print(f"Fenêtre dédup.    : {DEDUP_WINDOW_MINUTES} min")
    print("Appuyez sur Ctrl+C pour arrêter.\n")

    conn = init_database()
    portals = build_portals()
    print(f"{len(portals)} portails actifs.\n")

    try:
        while True:
            try:
                print(f"[{current_time_short()}] Surveillance en cours...")

                capture_time, states = fetch_aircraft_states()

                if states:
                    new_records = process_aircraft(
                        conn, states, portals, capture_time
                    )
                    if new_records == 0:
                        print(
                            f"  → {len(states)} avion(s) dans la zone, "
                            "aucune nouvelle détection à enregistrer."
                        )
                else:
                    print("  → Aucun avion détecté dans la zone.")

                time.sleep(SCAN_INTERVAL)

            except KeyboardInterrupt:
                raise
            except Exception as exc:
                print(f"[ERREUR INATTENDUE] {exc}")
                print(f"Nouvelle tentative dans {SCAN_INTERVAL} s...")
                time.sleep(SCAN_INTERVAL)

    except KeyboardInterrupt:
        print("\n\n=== Surveillance interrompue par l'utilisateur ===")
    finally:
        conn.close()
        print("Connexion à la base de données fermée. À bientôt !")


if __name__ == "__main__":
    main()
    