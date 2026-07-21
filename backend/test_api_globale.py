import requests

# Coordonnées de Bordeaux-Mérignac
LAT = 44.8283
LON = -0.7156
RADIUS = 50  # Rayon de recherche en milles nautiques (max 250 NM)

# API globale ouverte et gratuite (format identique à ADS-B Exchange)
url = f"https://api.adsb.lol/v2/lat/{LAT}/lon/{LON}/dist/{RADIUS}"

try:
    print(f"📡 Interrogation de l'API globale pour la zone de Bordeaux ({RADIUS} NM)...")
    response = requests.get(url, timeout=10)
    
    if response.status_code == 200:
        data = response.json()
        avions = data.get("ac", [])  # 'ac' contient la liste des avions détectés
        
        print(f"✈️  {len(avions)} avions trouvés actuellement dans la zone :\n")
        
        # On affiche les 10 premiers pour l'exemple
        for avion in avions[:10]:
            callsign = avion.get("flight", "ANONYME").strip()
            altitude = avion.get("alt_baro", "Inconnue")
            vitesse = avion.get("gs", "Inconnue")
            type_avion = avion.get("t", "Inconnu")
            
            # Conversion de l'altitude si c'est un nombre (Pieds -> Mètres)
            if isinstance(altitude, (int, float)):
                altitude = f"{int(altitude * 0.3048)}m"
            elif altitude == "ground":
                altitude = "Au sol"
                
            print(f"- Vol {callsign} ({type_avion}) | Alt: {altitude} | Vitesse: {vitesse} kts")
            
    else:
        print(f"❌ Erreur API : Code {response.status_code}")

except Exception as e:
    print(f"❌ Impossible de contacter l'API : {e}")