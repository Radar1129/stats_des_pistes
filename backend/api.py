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
    import urllib.request, json
    from concurrent.futures import ThreadPoolExecutor

    urls = [
        "https://api.adsb.lol/v2/lat/44.8283/lon/-0.7156/dist/15",
        "https://api.opendata.adsb.fi/api/v2/lat/44.8283/lon/-0.7156/dist/15"
    ]
    
    def fetch_api(url):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as response:
                return json.loads(response.read().decode()).get("ac", [])
        except Exception as e:
            print(f"Erreur API Radar ({url}): {e}")
            return []

    ac_list = []
    # Interrogation simultanée des deux sources pour redondance (Bloc 1)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = executor.map(fetch_api, urls)
        for res in results:
            if res:
                ac_list = res
                break
    
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

@app.get("/api/vols/expected")
def get_vols_expected():
    from datetime import datetime, timedelta
    import sqlite3
    
    try:
        try:
            import pytz
            tz = pytz.timezone('Europe/Paris')
            now_tz = datetime.now(tz)
        except ImportError:
            now_tz = datetime.utcnow() + timedelta(hours=2)
            
        today_iso = now_tz.date().isoformat()
        
        db_path = "/home/ubuntu/stats_des_pistes/lfbd_schedule.db"
        stats_db_path = "/home/ubuntu/stats_des_pistes/backend/bordeaux_stats.db"
        
        # Plage de recherche élargie en BDD (de hier 20h00 à demain 04h00) pour couvrir les sauts de minuit
        start_search = (now_tz - timedelta(days=1)).strftime("%Y-%m-%d 20:00:00")
        end_search = (now_tz + timedelta(days=1)).strftime("%Y-%m-%d 04:00:00")
        
        detectes_raw = []
        try:
            conn_stats = sqlite3.connect(stats_db_path)
            c_stats = conn_stats.cursor()
            c_stats.execute("SELECT callsign, horaire_passage FROM vols_detectes WHERE horaire_passage >= ? AND horaire_passage <= ?", (start_search, end_search))
            rows_det = c_stats.fetchall()
            for r in rows_det:
                if r[0] and r[1]:
                    try:
                        dt_det = datetime.strptime(r[1][:19], "%Y-%m-%d %H:%M:%S")
                        detectes_raw.append({"callsign": r[0].strip().upper(), "dt": dt_det})
                    except Exception:
                        pass
            conn_stats.close()
        except Exception as e:
            print(f"Erreur lecture bordeaux_stats.db: {e}")
            
        # Programme théorique du jour
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('''
            SELECT direction, scheduled_time, origin_dest, callsign, airline, status
            FROM flights
            WHERE scheduled_date = ?
            ORDER BY scheduled_time ASC
        ''', (today_iso,))
        rows = cursor.fetchall()
        conn.close()

        formatted_vols = []
        for r in rows:
            prog_callsign = (r["callsign"] or "").strip().upper()
            prog_time_str = r["scheduled_time"]
            
            # Reconstruction de la date/heure théorique complète
            dt_prog = None
            if prog_time_str:
                try:
                    dt_prog = datetime.strptime(f"{today_iso} {prog_time_str}", "%Y-%m-%d %H:%M")
                except Exception:
                    pass
            
            is_detecte = False
            prog_nums = "".join(filter(str.isdigit, prog_callsign))
            
            if dt_prog:
                # Fenêtre de tolérance : +/- 3 heures autour de l'heure théorique
                window_start = dt_prog - timedelta(hours=3)
                window_end = dt_prog + timedelta(hours=3)
                
                for det in detectes_raw:
                    if window_start <= det["dt"] <= window_end:
                        det_cs = det["callsign"]
                        # Matching exact
                        if prog_callsign == det_cs:
                            is_detecte = True
                            break
                        # Matching numérique
                        det_nums = "".join(filter(str.isdigit, det_cs))
                        if prog_nums and det_nums and prog_nums == det_nums:
                            is_detecte = True
                            break
            else:
                # Fallback si l'heure du vol était invalide
                for det in detectes_raw:
                    if prog_callsign == det["callsign"]:
                        is_detecte = True
                        break

            formatted_vols.append({
                "type": "Arrivée" if r["direction"] == "in" else "Départ",
                "heure": r["scheduled_time"],
                "ville": r["origin_dest"],
                "vol": r["callsign"],
                "compagnie": r["airline"],
                "statut": r["status"],
                "detecte": is_detecte
            })
            
        return {"data": formatted_vols}
    except Exception as e:
        print(f"Erreur vols expected: {e}")
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
