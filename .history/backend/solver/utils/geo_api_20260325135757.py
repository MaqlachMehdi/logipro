
import requests
# ──────────────────────────────────────────────────────────────────────────────
# API helpers
# ──────────────────────────────────────────────────────────────────────────────

def osrm_time_distance(lat1, lon1, lat2, lon2) -> tuple:
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{lon1},{lat1};{lon2},{lat2}?overview=false"
    )
    try:
        resp = requests.get(url, timeout=10)
        r = resp.json()
    except requests.exceptions.Timeout:
        raise RuntimeError(f"OSRM API timeout pour ({lat1},{lon1}) → ({lat2},{lon2})")
    except Exception as e:
        raise RuntimeError(f"OSRM API inaccessible: {e}")

    if 'routes' not in r or not r['routes']:
        code = r.get('code', 'Unknown')
        msg  = r.get('message', 'no message')
        raise RuntimeError(f"OSRM sans route ({code}): {msg} | ({lat1},{lon1}) → ({lat2},{lon2})")

    route = r["routes"][0]
    distance_km   = route["distance"] / 1000
    duration_min  = route["duration"] / 60
    return distance_km, duration_min
