
import math
import sys
import requests

# ──────────────────────────────────────────────────────────────────────────────
# Haversine fallback (used when OSRM is unreachable)
# ──────────────────────────────────────────────────────────────────────────────

_ROAD_FACTOR   = 1.3   # straight-line → estimated road distance
_AVG_SPEED_KMH = 50.0  # average urban driving speed

def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi   = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def _haversine_time_distance(lat1, lon1, lat2, lon2) -> tuple:
    dist_km = _haversine_km(lat1, lon1, lat2, lon2) * _ROAD_FACTOR
    time_min = dist_km / _AVG_SPEED_KMH * 60
    return dist_km, time_min


# ──────────────────────────────────────────────────────────────────────────────
# OSRM with automatic Haversine fallback
# ──────────────────────────────────────────────────────────────────────────────

def osrm_time_distance(lat1, lon1, lat2, lon2) -> tuple:
    # Guard: reject obviously ungeocoded coordinates
    if lat1 == 0 and lon1 == 0:
        raise RuntimeError("Coordonnées (0,0) invalides pour le point de départ — adresse non géocodée")
    if lat2 == 0 and lon2 == 0:
        raise RuntimeError("Coordonnées (0,0) invalides pour le point d'arrivée — adresse non géocodée")

    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{lon1},{lat1};{lon2},{lat2}?overview=false"
    )
    try:
        resp = requests.get(url, timeout=10)
        r = resp.json()
    except requests.exceptions.Timeout:
        print(f"[geo_api] OSRM timeout, fallback Haversine ({lat1},{lon1}) -> ({lat2},{lon2})", file=sys.stderr)
        return _haversine_time_distance(lat1, lon1, lat2, lon2)
    except Exception:
        print(f"[geo_api] OSRM inaccessible, fallback Haversine ({lat1},{lon1}) -> ({lat2},{lon2})", file=sys.stderr)
        return _haversine_time_distance(lat1, lon1, lat2, lon2)

    if 'routes' not in r or not r['routes']:
        code = r.get('code', 'Unknown')
        msg  = r.get('message', 'no message')
        raise RuntimeError(f"OSRM sans route ({code}): {msg} | ({lat1},{lon1}) -> ({lat2},{lon2})")

    route = r["routes"][0]
    distance_km  = route["distance"] / 1000
    duration_min = route["duration"] / 60
    return distance_km, duration_min
