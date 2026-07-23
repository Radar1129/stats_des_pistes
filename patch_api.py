import re

filepath = "/home/ubuntu/stats_des_pistes/backend/api.py"

with open(filepath, "r", encoding="utf-8") as f:
    code = f.read()

new_code_block = """@app.get("/api/vols/expected")
def get_vols_expected():
    from datetime import date
    import sqlite3

    try:
        today_iso = date.today().isoformat()
        db_path = "/home/ubuntu/stats_des_pistes/lfbd_schedule.db"

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
            formatted_vols.append({
                "type": "Arrivée" if r["direction"] == "in" else "Départ",
                "heure": r["scheduled_time"],
                "ville": r["origin_dest"],
                "vol": r["callsign"],
                "compagnie": r["airline"],
                "statut": r["status"]
            })

        return {"data": formatted_vols}
    except Exception as e:
        print("Erreur lecture BDD flights:", e)
        return {"data": []}

"""

# Emplacement de la route dans api.py
pattern = r'@app\.get\("/api/vols/expected"\)[\s\S]*?(?=@app\.get\("/api/score"\))'

if re.search(pattern, code):
    updated_code = re.sub(pattern, new_code_block, code)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(updated_code)
    print("✅ Le fichier api.py a été mis à jour avec succès !")
else:
    print("⚠️ Impossible de trouver la route exacte dans api.py.")
