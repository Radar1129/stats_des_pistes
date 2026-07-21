#!/usr/bin/env python3
import sqlite3
from datetime import datetime, timedelta

DB_PATH = "/home/ubuntu/stats_des_pistes/backend/bordeaux_stats.db"

def calculate_daily_score():
    # Par défaut, calcule le score pour hier
    yesterday_str = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Récupération des vols uniques vus par Aérovision
    cursor.execute(
        "SELECT DISTINCT flight_id FROM shadow_aerovision WHERE captured_at = ?", 
        (yesterday_str,)
    )
    aerovision_flights = [row[0] for row in cursor.fetchall()]
    total_aerovision = len(aerovision_flights)
    
    if total_aerovision == 0:
        print(f"[-] Pas de données Aérovision pour le {yesterday_str}.")
        conn.close()
        return

    # 2. Comptage des correspondances dans ton radar
    matches = 0
    for flight_id in aerovision_flights:
        cursor.execute(
            "SELECT COUNT(*) FROM vols_detectes WHERE callsign = ? AND horaire_passage LIKE ?", 
            (flight_id, f"{yesterday_str}%")
        )
        if cursor.fetchone()[0] > 0:
            matches += 1
            
    # 3. Calcul du score
    score_percentage = round((matches / total_aerovision) * 100, 1)
    
    # 4. Sauvegarde du résultat dans notre nouvelle table
    cursor.execute(
        """
        INSERT OR REPLACE INTO scores_verification (date_calcul, total_aerovision, total_radar, score_percentage)
        VALUES (?, ?, ?, ?)
        """,
        (yesterday_str, total_aerovision, matches, score_percentage)
    )
    
    conn.commit()
    print(f"[+] Score du {yesterday_str} enregistré avec succès : {score_percentage}%")
    conn.close()

if __name__ == "__main__":
    calculate_daily_score()
