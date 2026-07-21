import re

_AIRLINE_MAP = {
    "AF": "AFR", "AFR": "AFR",
    "U2": "EZY", "EZY": "EZY", "EJU": "EZY", "EZS": "EZY",
    "BA": "BAW", "BAW": "BAW",
    "TO": "TVF", "TVF": "TVF",
    "KL": "KLM", "KLM": "KLM",
    "V7": "VOE", "VOE": "VOE",
    "FR": "RYR", "RYR": "RYR"
}

def normalize_callsign(callsign):
    if not callsign: return None
    c = str(callsign).strip().upper()
    
    # Sépare intelligemment le préfixe (3 lettres ICAO ou 2 caractères IATA) du numéro
    m = re.match(r"^([A-Z]{3}|[A-Z0-9]{2})(\d.*)$", c)
    if not m:
        return c
        
    prefix, number = m.groups()
    normalized_prefix = _AIRLINE_MAP.get(prefix, prefix)
    return f"{normalized_prefix}{number}"

def is_noise(callsign, aircraft_type=""):
    c = str(callsign or "").upper()
    t = str(aircraft_type or "").upper()
    keywords = ["SAMU", "DRAGON", "HELI", "SMUR", "RESCUE", "SAF", "DHWIR"]
    heli_types = ["EC35", "EC45", "H135", "H145", "AS32", "AS50", "R22", "R44"]
    return any(k in c for k in keywords) or any(ht in t for ht in heli_types)

def qualify_phase(vertical_rate, altitude, speed_kts, schedule_type=None):
    st = str(schedule_type or "").upper()
    try:
        vr = float(vertical_rate or 0)
        alt = float(altitude or 0)
        spd = float(speed_kts or 0)
    except (ValueError, TypeError):
        vr, alt, spd = 0, 0, 0

    if spd < 35 and alt < 100:
        return "ROULAGE / SOL"

    if "ARRIV" in st or "LANDING" in st:
        return "ATTERRISSAGE" if alt < 100 else "EN APPROCHE"
    if "DEP" in st or "TAKE" in st:
        return "DÉCOLLAGE"

    if vr < -150: return "EN APPROCHE"
    if vr > 150: return "DÉCOLLAGE"
    
    return "EN VOL"
