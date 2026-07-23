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
    import re

    try:
        try:
            import pytz
            tz = pytz.timezone('Europe/Paris')
            now_tz = datetime.now(tz)
        except ImportError:
            now_tz = datetime.utcnow() + timedelta(hours=2)

        today_iso = now_tz.date().isoformat()
        yesterday_iso = (now_tz - timedelta(days=1)).date().isoformat()
        is_night_mode = now_tz.hour < 5

        db_path = "/home/ubuntu/stats_des_pistes/lfbd_schedule.db"
        stats_db_path = "/home/ubuntu/stats_des_pistes/backend/bordeaux_stats.db"

        start_search = (now_tz - timedelta(days=2)).strftime("%Y-%m-%d 20:00:00")
        end_search = (now_tz + timedelta(days=1)).strftime("%Y-%m-%d 10:00:00")

        detectes_raw = []
        try:
            conn_stats = sqlite3.connect(stats_db_path)
            c_stats = conn_stats.cursor()
            # On récupère ici le portail_nom pour la piste !
            c_stats.execute("SELECT callsign, horaire_passage, action, portail_nom FROM vols_detectes WHERE horaire_passage >= ? AND horaire_passage <= ?", (start_search, end_search))
            for r in c_stats.fetchall():
                if r[0] and r[1]:
                    try:
                        dt_det = datetime.strptime(r[1][:19], "%Y-%m-%d %H:%M:%S")
                        detectes_raw.append({"callsign": r[0].strip().upper(), "dt": dt_det, "action": r[2], "portail": r[3]})
                    except Exception:
                        pass
            conn_stats.close()
        except Exception:
            pass

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if is_night_mode:
            cursor.execute("""
                SELECT scheduled_date, direction, scheduled_time, origin_dest, callsign, airline, status
                FROM flights
                WHERE (scheduled_date = ? AND scheduled_time >= '17:00') OR (scheduled_date = ?)
                ORDER BY scheduled_date ASC, scheduled_time ASC
            """, (yesterday_iso, today_iso))
        else:
            cursor.execute("""
                SELECT scheduled_date, direction, scheduled_time, origin_dest, callsign, airline, status
                FROM flights
                WHERE scheduled_date = ?
                ORDER BY scheduled_time ASC
            """, (today_iso,))
        rows = cursor.fetchall()
        conn.close()

        CIE_MAP = {
            "U2": ["EJU", "EZY", "EAI"], "V7": ["VOE"], "TO": ["TVF"], "FR": ["RYR"],
            "AF": ["AFR"], "KL": ["KLM"], "BA": ["BAW", "SHT"], "SN": ["BEL"],
            "LH": ["DLH"], "LX": ["SWR"], "AT": ["RAM"], "A5": ["HOP"], "WQ": ["SWT"]
        }

        def get_prefix(cs):
            m = re.match(r"^([A-Z]{3}|[A-Z0-9]{2})", cs)
            return m.group(1) if m else cs

        def get_piste(portail, action):
            if not portail: return ""
            p = portail.replace("Portail ", "").strip()
            if action and "decollage" in action.lower():
                opposites = {"05": "23", "23": "05", "11": "29", "29": "11"}
                return opposites.get(p, p)
            return p

        formatted_vols = []
        for r in rows:
            prog_callsign = (r["callsign"] or "").strip().upper()
            prog_time_str = r["scheduled_time"]
            prog_date_str = r["scheduled_date"] if "scheduled_date" in r.keys() else today_iso
            expected_action = "atterrissage" if r["direction"] == "in" else "decollage"

            dt_prog = None
            if prog_time_str:
                try:
                    dt_prog = datetime.strptime(f"{prog_date_str} {prog_time_str}", "%Y-%m-%d %H:%M")
                except Exception:
                    pass

            is_detecte = False
            piste_detectee = ""
            prog_nums = "".join(filter(str.isdigit, prog_callsign))
            prog_prefix = get_prefix(prog_callsign)
            expected_icaos = CIE_MAP.get(prog_prefix, [prog_prefix])

            if dt_prog:
                window_start = dt_prog - timedelta(hours=3)
                window_end = dt_prog + timedelta(hours=3)
                best_score = 0
                best_piste = ""
                
                for det in detectes_raw:
                    if window_start <= det["dt"] <= window_end:
                        det_cs = det["callsign"]
                        det_action = det["action"]
                        
                        if expected_action != det_action:
                            continue

                        score = 0
                        if prog_callsign == det_cs:
                            score += 200
                        else:
                            det_prefix = get_prefix(det_cs)
                            if det_prefix in expected_icaos or prog_prefix == det_prefix:
                                score += 100
                                det_nums = "".join(filter(str.isdigit, det_cs))
                                
                                if prog_nums and det_nums and prog_nums == det_nums:
                                    score += 100
                                elif score == 100:
                                    time_diff = abs((det["dt"] - dt_prog).total_seconds())
                                    score += max(0, 50 - (time_diff / 3600) * 10)
                        
                        if score > best_score:
                            best_score = score
                            best_piste = get_piste(det.get("portail", ""), det_action)
                            
                if best_score >= 100:
                    is_detecte = True
                    piste_detectee = best_piste
            else:
                for det in detectes_raw:
                    if prog_callsign == det["callsign"]:
                        is_detecte = True
                        piste_detectee = get_piste(det.get("portail", ""), det["action"])
                        break

            formatted_vols.append({
                "type": "Arrivée" if r["direction"] == "in" else "Départ",
                "heure": r["scheduled_time"],
                "ville": r["origin_dest"],
                "vol": r["callsign"],
                "compagnie": r["airline"],
                "statut": r["status"],
                "detecte": is_detecte,
                "piste": piste_detectee,
                "is_hier": (prog_date_str == yesterday_iso)
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



@app.get('/api/vols/hors-programme')
def get_vols_hors_programme():
    try:
        from datetime import datetime, timedelta
        import sqlite3
        import re

        conn_sched = sqlite3.connect('/home/ubuntu/stats_des_pistes/lfbd_schedule.db')
        conn_sched.row_factory = sqlite3.Row
        c_sched = conn_sched.cursor()
        date_today = datetime.now().strftime('%Y-%m-%d')
        # On lit aussi le sens pour ne pas confondre
        c_sched.execute("SELECT callsign, scheduled_time, direction FROM flights WHERE scheduled_date = ?", (date_today,))
        vols_prevus = c_sched.fetchall()
        conn_sched.close()

        CIE_MAP = {
            "U2": ["EJU", "EZY", "EAI"], "V7": ["VOE"], "TO": ["TVF"], "FR": ["RYR"],
            "AF": ["AFR"], "KL": ["KLM"], "BA": ["BAW", "SHT"], "SN": ["BEL"],
            "LH": ["DLH"], "LX": ["SWR"], "AT": ["RAM"], "A5": ["HOP"], "WQ": ["SWT"]
        }

        def get_prefix(cs):
            m = re.match(r"^([A-Z]{3}|[A-Z0-9]{2})", cs)
            return m.group(1) if m else cs

        conn_radar = sqlite3.connect('/home/ubuntu/stats_des_pistes/backend/bordeaux_stats.db')
        c_radar = conn_radar.cursor()
        date_24h_ago = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')

        c_radar.execute("""
            SELECT callsign, action, horaire_passage, altitude_metres, origine, destination, portail_nom
            FROM vols_detectes 
            WHERE horaire_passage >= ?
            ORDER BY horaire_passage DESC
        """, (date_24h_ago,))
        lignes = c_radar.fetchall()
        conn_radar.close()

        hors_prog = []
        vus = set()
        
        for callsign, action, horaire, alt, orig, dest, portail in lignes:
            def get_piste(portail, action):
                if not portail: return ""
                p = portail.replace("Portail ", "").strip()
                if action and "decollage" in action.lower():
                    opposites = {"05": "23", "23": "05", "11": "29", "29": "11"}
                    return opposites.get(p, p)
                return p
            
            piste_reelle = get_piste(portail, action)
            cs = callsign.strip().upper() if callsign else ''
            if not cs or cs in vus:
                continue
                
            est_prevu = False
            det_prefix = get_prefix(cs)
            det_nums = "".join(filter(str.isdigit, cs))
            
            try:
                dt_det = datetime.strptime(horaire[:19], "%Y-%m-%d %H:%M:%S")
            except:
                dt_det = datetime.now()

            # Croisement avec le programme via la logique intelligente
            for r in vols_prevus:
                prog_cs = (r["callsign"] or "").strip().upper()
                expected_action = "atterrissage" if r["direction"] == "in" else "decollage"
                
                if action != expected_action:
                    continue
                    
                if cs == prog_cs:
                    est_prevu = True
                    break
                    
                prog_prefix = get_prefix(prog_cs)
                expected_icaos = CIE_MAP.get(prog_prefix, [prog_prefix])
                
                if det_prefix in expected_icaos or prog_prefix == det_prefix:
                    prog_nums = "".join(filter(str.isdigit, prog_cs))
                    if prog_nums and det_nums and prog_nums == det_nums:
                        est_prevu = True
                        break
                    
                    if r["scheduled_time"]:
                        try:
                            dt_prog = datetime.strptime(f"{date_today} {r['scheduled_time']}", "%Y-%m-%d %H:%M")
                            time_diff = abs((dt_det - dt_prog).total_seconds())
                            if time_diff <= 10800: # 3 heures max
                                est_prevu = True
                                break
                        except:
                            pass

            if not est_prevu:
                vus.add(cs)
                hors_prog.append({
                    'callsign': cs,
                    'action': action,
                    'horaire': horaire,
                    'altitude': alt,
                    'origine': orig or 'Inconnu',
                    'destination': dest or 'Inconnu',
                    'piste': piste_reelle
                })
                
        return {'status': 'success', 'data': hors_prog}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

