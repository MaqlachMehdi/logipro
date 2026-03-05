import sys
import json
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

def geocode(address: str):
    geolocator = Nominatim(user_agent="regietour")
    try:
        location = geolocator.geocode(address, timeout=10)
        if location:
            return { "lat": location.latitude, "lon": location.longitude }
        else:
            return { "error": f"Adresse introuvable: {address}" }
    except (GeocoderTimedOut, GeocoderUnavailable) as e:
        return { "error": f"Géocodeur indisponible: {str(e)}" }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({ "error": "Adresse manquante" }))
        sys.exit(1)
    result = geocode(sys.argv[1])
    print(json.dumps(result))