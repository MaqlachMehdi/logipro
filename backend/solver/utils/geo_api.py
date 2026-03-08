
import requests
# ──────────────────────────────────────────────────────────────────────────────
# API helpers
# ──────────────────────────────────────────────────────────────────────────────

def osrm_time_distance(lat1, lon1, lat2, lon2) -> tuple:
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{lon1},{lat1};{lon2},{lat2}?overview=false"
    )
    r = requests.get(url).json()
    route = r["routes"][0]
    distance_km   = route["distance"] / 1000
    duration_min  = route["duration"] / 60
    return distance_km, duration_min
