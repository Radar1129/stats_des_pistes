import sqlite3
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Configuration du CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "bordeaux_stats.db"

# --- NOUVEAU : STRUCTURE POUR LA CONNEXION ---
class LoginData(BaseModel):
    username: str
    password: str

# ---------------------------------------------
# ROUTES DU RADAR (Existantes)
# ---------------------------------------------

@app.get("/api/vols/direct")
def get_vols_direct():
    url = "https://api.adsb.lol/v2/lat/44.8283/lon/-0.7156/dist/15"
    try:
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            ac = response.json().get("ac", [])
            vols_formates = []
            for avion in ac:
                callsign = avion.get("flight", "").strip()
                if not callsign:
                    callsign = "ANONYME"
                
                vols_formates.append({
                    "callsign": callsign,
                    "type": avion.get("t", "UNKN"),
                    "latitude": avion.get("lat"),
                    "longitude": avion.get("lon"),
                    "altitude": f"{int(avion.get('alt_baro', 0) * 0.3048)}m" if avion.get("alt_baro") else "0m",
                    "vitesse": avion.get("gs", 0),
                    "cap": avion.get("track", 0)
                })
            return {"data": vols_formates}
    except Exception as e:
        print(f"⚠️ Erreur de liaison direct radar : {e}")
    return {"data": []}

@app.get("/api/stats/pistes")
def get_stats_pistes():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    limite = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute("""
        SELECT portail_nom, action, callsign, horaire_passage, altitude_metres, origine, destination 
        FROM vols_detectes 
        WHERE horaire_passage >= ?
        ORDER BY horaire_passage DESC
    """, (limite,))
    
    lignes = cursor.fetchall()
    conn.close()

    structure = {
        "Piste 05": {"atterrissage": {"total": 0, "vols": []}, "décollage": {"total": 0, "vols": []}},
        "Piste 23": {"atterrissage": {"total": 0, "vols": []}, "décollage": {"total": 0, "vols": []}},
        "Piste 11": {"atterrissage": {"total": 0, "vols": []}, "décollage": {"total": 0, "vols": []}},
        "Piste 29": {"atterrissage": {"total": 0, "vols": []}, "décollage": {"total": 0, "vols": []}}
    }

    for portail, action, callsign, horaire, alt, orig, dest in lignes:
        if portail in structure and action in structure[portail]:
            structure[portail][action]["total"] += 1
            if len(structure[portail][action]["vols"]) < 5:
                structure[portail][action]["vols"].append({
                    "callsign": callsign,
                    "horaire_passage": horaire,
                    "altitude_metres": alt,
                    "origine": orig,
                    "destination": dest
                })
    return structure

@app.get("/api/stats/historique")
def get_stats_historique(periode: str = Query("jour", enum=["jour", "semaine", "mois", "annee"])):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    maintenant = datetime.now()
    if periode == "jour": date_limite = maintenant - timedelta(days=1)
    elif periode == "semaine": date_limite = maintenant - timedelta(weeks=1)
    elif periode == "mois": date_limite = maintenant - timedelta(days=30)
    elif periode == "annee": date_limite = maintenant - timedelta(days=365)
        
    date_limite_str = date_limite.strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute("SELECT COUNT(*) FROM vols_detectes WHERE horaire_passage >= ?", (date_limite_str,))
    total = cursor.fetchone()[0]
    
    if total == 0:
        conn.close()
        return {"total": 0, "axes": {"Axe 05/23 (Principal)": 0, "Axe 11/29 (Secondaire)": 0}, "pistes": {"Piste 05": 0, "Piste 23": 0, "Piste 11": 0, "Piste 29": 0}}
        
    cursor.execute("SELECT portail_nom, COUNT(*) FROM vols_detectes WHERE horaire_passage >= ? GROUP BY portail_nom", (date_limite_str,))
    lignes = cursor.fetchall()
    conn.close()
    
    pistes_stats = {"Piste 05": 0, "Piste 23": 0, "Piste 11": 0, "Piste 29": 0}
    total_axe_05_23 = 0
    total_axe_11_29 = 0
    
    for nom_piste, count in lignes:
        if nom_piste in pistes_stats:
            pistes_stats[nom_piste] = round((count / total) * 100, 1)
            if nom_piste in ["Piste 05", "Piste 23"]: total_axe_05_23 += count
            elif nom_piste in ["Piste 11", "Piste 29"]: total_axe_11_29 += count
                
    stats_axes = {
        "Axe 05/23 (Principal)": round((total_axe_05_23 / total) * 100, 1) if total_axe_05_23 > 0 else 0,
        "Axe 11/29 (Secondaire)": round((total_axe_11_29 / total) * 100, 1) if total_axe_11_29 > 0 else 0
    }
    return {"total": total, "axes": stats_axes, "pistes": pistes_stats}

# ---------------------------------------------
# NOUVELLE ROUTE : AUTHENTIFICATION
# ---------------------------------------------
@app.post("/api/login")
def login(data: LoginData):
    """
    Vérifie les identifiants envoyés par le portail web.
    """
    # 💡 C'est ici que tu peux ajouter les comptes de tes amis !
    comptes_autorises = {
        "admin": "radar2026",      # Ton compte
        "pote1": "avion33",        # Compte de ton ami 1
        "famille": "bordeaux"      # Compte familial
    }
    
    # On vérifie si l'utilisateur existe ET si le mot de passe correspond
    if data.username in comptes_autorises and comptes_autorises[data.username] == data.password:
        return {"success": True, "token": f"token_valide_{data.username}"}
    
    # Si échec :
    return {"success": False, "message": "Identifiants incorrects"}