import sqlite3
import json
import os
import urllib.request
from datetime import datetime, timedelta
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "/home/ubuntu/stats_des_pistes/backend/bordeaux_stats.db"

class LoginData(BaseModel):
    username: str
    password: str

@app.post("/api/login")
def login(data: LoginData):
    if data.username in ["radar2026", "avion33", "famille", "bordeaux"] and data.password in ["radar2026", "avion33", "famille", "bordeaux"]:
        return {"status": "success", "token": "token_valide_12345"}
    raise HTTPException(status_code=401, detail="Identifiants incorrects")

@app.get("/api/vols/direct")
def get_vols_direct():
    try:
        url = "https://api.adsb.lol/v2/lat/44.8283/lon/-0.7156/dist/15"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            ac_list = data.get("ac", [])
            vols = []
            for ac in ac_list:
                vols.append({
                    "callsign": ac.get("flight", "ANONYME").strip(),
                    "latitude": ac.get("lat"),
                    "longitude": ac.get("lon"),
                    "altitude": ac.get("alt_baro", ac.get("alt_geom", 0)),
                    "vitesse": ac.get("gs", 0),
                    "cap": ac.get("track", 0),
                    "taux_vertical": ac.get("baro_rate", 0)
                })
            return vols
    except Exception:
        return []

@app.get("/api/vols/expected")
def get_vols_expected():
    cache_file = "/home/ubuntu/stats_des_pistes/backend/scraped_cache.json"
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                return {"data": json.load(f)}
        except Exception:
            pass
            
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM shadow_aerovision")
        rows = cursor.fetchall()
        conn.close()
        return {"data": [dict(r) for r in rows]}
    except Exception:
        return {"data": []}

@app.get("/api/score")
def get_score():
    return {"score": 100}

@app.get("/api/stats/pistes")
def get_stats_pistes(periode: str = "jour"):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    maintenant = datetime.now()
    if periode in ["jour", "1"]:
        date_limite = maintenant - timedelta(days=1)
    elif periode in ["semaine", "7"]:
        date_limite = maintenant - timedelta(days=7)
    elif periode in ["mois", "30"]:
        date_limite = maintenant - timedelta(days=30)
    elif periode in ["annee", "365"]:
        date_limite = maintenant - timedelta(days=365)
    else:
        date_limite = maintenant - timedelta(days=1)

    date_limite_str = date_limite.strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        SELECT portail_nom, action, callsign, horaire_passage, altitude_metres, origine, destination 
        FROM vols_detectes 
        WHERE horaire_passage >= ?
        ORDER BY horaire_passage DESC
    """, (date_limite_str,))
    lignes = cursor.fetchall()
    conn.close()

    pistes = ["Piste 05", "Piste 23", "Piste 11", "Piste 29"]
    res = {
        p: {
            "atterrissage": {"total": 0, "vols": []},
            "décollage": {"total": 0, "vols": []}
        }
        for p in pistes
    }

    for portail_nom, action, callsign, horaire_passage, altitude_metres, origine, destination in lignes:
        if portail_nom in res:
            act_raw = (action or "").lower()
            act_key = "décollage" if ("decollage" in act_raw or "décollage" in act_raw) else "atterrissage"
            
            res[portail_nom][act_key]["total"] += 1
            if len(res[portail_nom][act_key]["vols"]) < 5:
                res[portail_nom][act_key]["vols"].append({
                    "callsign": callsign,
                    "horaire_passage": horaire_passage,
                    "altitude_metres": altitude_metres,
                    "origine": origine,
                    "destination": destination
                })

    return res

@app.get("/api/stats/historique")
def get_stats_historique(periode: str = "jour"):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    maintenant = datetime.now()
    if periode in ["jour", "1"]:
        date_limite = maintenant - timedelta(days=1)
    elif periode in ["semaine", "7"]:
        date_limite = maintenant - timedelta(days=7)
    elif periode in ["mois", "30"]:
        date_limite = maintenant - timedelta(days=30)
    elif periode in ["annee", "365"]:
        date_limite = maintenant - timedelta(days=365)
    else:
        try:
            jours = int(periode)
            date_limite = maintenant - timedelta(days=jours)
        except ValueError:
            date_limite = maintenant - timedelta(days=1)

    date_limite_str = date_limite.strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("SELECT COUNT(*) FROM vols_detectes WHERE horaire_passage >= ?", (date_limite_str,))
    total = cursor.fetchone()[0]

    if total == 0:
        conn.close()
        return {
            "total": 0,
            "axes": {"Axe 05/23 (Principal)": 0, "Axe 11/29 (Secondaire)": 0},
            "pistes": {"Piste 05": 0, "Piste 23": 0, "Piste 11": 0, "Piste 29": 0}
        }

    cursor.execute("""
        SELECT portail_nom, COUNT(*) 
        FROM vols_detectes 
        WHERE horaire_passage >= ? 
        GROUP BY portail_nom
    """, (date_limite_str,))
    lignes = cursor.fetchall()
    conn.close()

    pistes_stats = {"Piste 05": 0, "Piste 23": 0, "Piste 11": 0, "Piste 29": 0}
    total_axe_05_23 = 0
    total_axe_11_29 = 0

    for nom_piste, count in lignes:
        if nom_piste not in pistes_stats:
            continue
        pistes_stats[nom_piste] = round((count / total) * 100, 1)
        if nom_piste in ("Piste 05", "Piste 23"):
            total_axe_05_23 += count
        elif nom_piste in ("Piste 11", "Piste 29"):
            total_axe_11_29 += count

    stats_axes = {
        "Axe 05/23 (Principal)": round((total_axe_05_23 / total) * 100, 1) if total > 0 else 0,
        "Axe 11/29 (Secondaire)": round((total_axe_11_29 / total) * 100, 1) if total > 0 else 0
    }

    return {
        "total": total,
        "axes": stats_axes,
        "pistes": pistes_stats
    }
