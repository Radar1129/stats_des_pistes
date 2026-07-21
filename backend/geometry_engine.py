import math

# Centre de LFBD et caps véritables des pistes
RUNWAYS = {
    "05": {"lat": 44.8283, "lon": -0.7155, "heading": 48},
    "23": {"lat": 44.8283, "lon": -0.7155, "heading": 228},
    "11": {"lat": 44.8283, "lon": -0.7155, "heading": 108},
    "29": {"lat": 44.8283, "lon": -0.7155, "heading": 288}
}

def is_aligned_on_runway(lat, lon, heading, runway_key, max_cross_track_m=400, heading_tol=25, max_dist_m=25000):
    if not lat or not lon or heading is None:
        return False
        
    rw = RUNWAYS.get(runway_key)
    if not rw: 
        return False
    
    # 1. Heading Gate : L'avion vole-t-il dans la bonne direction ? (+/- 25 deg)
    heading_diff = abs((float(heading) - rw["heading"] + 180) % 360 - 180)
    if heading_diff > heading_tol:
        return False

    # 2. Mathématiques Haversine
    R = 6371000 # Rayon terrestre en mètres
    lat1, lon1 = math.radians(rw["lat"]), math.radians(rw["lon"])
    lat2, lon2 = math.radians(float(lat)), math.radians(float(lon))
    
    dphi = lat2 - lat1
    dlambda = lon2 - lon1
    a = math.sin(dphi/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlambda/2)**2
    d_meters = 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    # 3. Filtre de distance globale (Ignorer les avions à + de 25km)
    if d_meters > max_dist_m:
        return False
    
    # 4. Calcul du Cross-Track (Déviation exacte par rapport à la ligne d'axe)
    y = math.sin(dlambda) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlambda)
    bearing_to_ac = (math.degrees(math.atan2(y, x)) + 360) % 360
    
    angular_diff = math.radians(bearing_to_ac - rw["heading"])
    cross_track_dist = abs(math.asin(math.sin(d_meters / R) * math.sin(angular_diff)) * R)
    
    # Validation finale : L'avion est-il dans le corridor de 400m de large ?
    return cross_track_dist <= max_cross_track_m