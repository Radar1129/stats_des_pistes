import pytest
from flight_engine import normalize_callsign, is_noise, qualify_phase
from geometry_engine import is_aligned_on_runway, RUNWAYS

def test_normalize_callsign():
    # Tests de rapprochement IATA / ICAO
    assert normalize_callsign("AF7440") == "AFR7440"
    assert normalize_callsign("AFR7440") == "AFR7440"
    assert normalize_callsign("U22278") == "EZY2278"  # Cas EasyJet complexe
    assert normalize_callsign("EJU2278") == "EZY2278"
    assert normalize_callsign("BA2787") == "BAW2787"
    assert normalize_callsign("INCONNU99") == "INCONNU99" # Fallback sécurisé

def test_is_noise():
    # Tests du filtre anti-hélicoptères / secours
    assert is_noise("SAMU24", "") == True
    assert is_noise("DHWIR", "EC35") == True
    assert is_noise("DRAGON33", "EC45") == True
    assert is_noise("AFR7440", "A320") == False
    assert is_noise("EZY123", "B738") == False

def test_qualify_phase():
    # 1. Priorité Sol (Vitesse < 35 kts & Alt < 100 ft)
    assert qualify_phase(0, 50, 20, "ARRIVEE") == "ROULAGE / SOL"
    
    # 2. Priorité Programme Aérovision (écrase la télémétrie V/S)
    assert qualify_phase(-50, 2000, 140, "ARRIVEE") == "EN APPROCHE"
    assert qualify_phase(-50, 50, 130, "ARRIVEE") == "ATTERRISSAGE"
    assert qualify_phase(-1200, 1500, 150, "DEPART") == "DÉCOLLAGE" # Le programme prime
    
    # 3. Fallback Télémétrie stricte (quand vol inconnu du programme)
    assert qualify_phase(-800, 3000, 250, "") == "EN APPROCHE"
    assert qualify_phase(1500, 2000, 250, "") == "DÉCOLLAGE"
    assert qualify_phase(0, 30000, 450, "") == "EN VOL" # Statut neutre

def test_is_aligned_on_runway():
    # Données exactes du centre de la piste 05
    lat_05 = RUNWAYS["05"]["lat"]
    lon_05 = RUNWAYS["05"]["lon"]
    hdg_05 = RUNWAYS["05"]["heading"]
    
    # Cas 1 : Alignement parfait
    assert is_aligned_on_runway(lat_05, lon_05, hdg_05, "05") == True
    
    # Cas 2 : Rejet sur le cap (Tolérance dépassée, ex: avion qui croise l'axe)
    assert is_aligned_on_runway(lat_05, lon_05, hdg_05 + 50, "05") == False
    
    # Cas 3 : Rejet sur la distance globale (+ de 25km)
    assert is_aligned_on_runway(lat_05 + 1.0, lon_05, hdg_05, "05") == False
