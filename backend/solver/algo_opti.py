import pandas as pd
import pulp
from geopy.geocoders import Nominatim
import time as time_module
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import requests
from collections import Counter

data_test = {
  "lieux": [
    {
      "Id_Lieux": 0,
      "Nom": "Dépôt",
      "Adresse": "Av. Gustave Eiffel, 75007 Paris",
      "lat": 48.8581265,
      "lon": 2.2956641,
      "HeureTot": 480,
      "HeureTard": 1380,
      "HeureConcert": "null",
      "Instruments": ""
    },
    {
      "Id_Lieux": 1,
      "Nom": "Cirque",
      "Adresse": "110 Rue Amelot, 75011 Paris",
      "lat": 48.8113,
      "lon": 2.2616,
      "HeureTot": 480,
      "HeureTard": 1380,
      "HeureConcert": 1080,
      "Instruments": "Ampli Guitare, Ampli Guitare, Ampli Guitare, Ampli Guitare, Ampli Guitare, Ampli Basse, Ampli Basse, Ampli Basse, Ampli Basse, Ampli Basse, Basse, Basse, Basse, Basse, Basse, Guitare Acoustique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Drum Kit Complete, Drum Kit Complete"
    },
    {
      "Id_Lieux": 2,
      "Nom": "Hotel",
      "Adresse": "Pl. Gérard Willaume, 77600 Chanteloup-en-Brie",
      "lat": 48.8685,
      "lon": 2.376,
      "HeureTot": 480,
      "HeureTard": 1380,
      "HeureConcert": 1080,
      "Instruments": "Drum Kit Complete, Drum Kit Complete, Drum Kit Complete"
    },
    {
      "Id_Lieux": 3,
      "Nom": "Casa",
      "Adresse": "32 allée du hêtre, pontault-combault 77340",
      "lat": 48.8010,
      "lon": 2.2316,
      "HeureTot": 480,
      "HeureTard": 1380,
      "HeureConcert": 1080,
      "Instruments": "Guitare Électrique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Basse, Basse, Basse, Basse, Basse, Basse, Basse, Guitare Acoustique, Guitare Acoustique, Guitare Acoustique, Guitare Acoustique, Guitare Acoustique, Guitare Acoustique, Ampli Guitare, Ampli Guitare, Ampli Guitare, Ampli Guitare, Ampli Guitare, Ampli Guitare, Ampli Basse, Pedalboard, Pedalboard, Pedalboard, Pedalboard, Pedalboard, Pedalboard"
    }
  ],
  "instruments": [
    {
      "Nom": "Drum Kit Complete",
      "Volume": 1.2
    },
    {
      "Nom": "Caisse Claire",
      "Volume": 0.15
    },
    {
      "Nom": "Cymbales Pack",
      "Volume": 0.3
    },
    {
      "Nom": "Guitare Électrique",
      "Volume": 0.1
    },
    {
      "Nom": "Basse",
      "Volume": 0.12
    },
    {
      "Nom": "Guitare Acoustique",
      "Volume": 0.15
    },
    {
      "Nom": "Ampli Guitare",
      "Volume": 0.3
    },
    {
      "Nom": "Ampli Basse",
      "Volume": 0.4
    },
    {
      "Nom": "Pedalboard",
      "Volume": 0.08
    },
    {
      "Nom": "Piano",
      "Volume": 2.5
    },
    {
      "Nom": "Synthétiseur",
      "Volume": 0.25
    },
    {
      "Nom": "Stand Clavier",
      "Volume": 0.15
    },
    {
      "Nom": "Orgue",
      "Volume": 1.8
    },
    {
      "Nom": "Enceinte PA",
      "Volume": 0.4
    },
    {
      "Nom": "Caisson de Bas",
      "Volume": 0.6
    },
    {
      "Nom": "Table de Mixage",
      "Volume": 0.5
    },
    {
      "Nom": "Pack Micros",
      "Volume": 0.2
    },
    {
      "Nom": "Moniteur Scène",
      "Volume": 0.15
    },
    {
      "Nom": "Moving Head",
      "Volume": 0.3
    },
    {
      "Nom": "Barre LED",
      "Volume": 0.4
    },
    {
      "Nom": "Gradateur",
      "Volume": 0.5
    },
    {
      "Nom": "Truss Section",
      "Volume": 0.8
    },
    {
      "Nom": "Flight Case",
      "Volume": 0.2
    },
    {
      "Nom": "Câbles Box",
      "Volume": 0.15
    },
    {
      "Nom": "Stand Rack",
      "Volume": 0.25
    },
    {
      "Nom": "Riser Backline",
      "Volume": 0.6
    },
    {
      "Nom": "Percu",
      "Volume": 12
    }
  ],
  "vehicules": [
    {
      "Id_vehicules": 1,
      "Nom": "AA-123-BB",
      "Volume_dispo": 4
    },
    {
      "Id_vehicules": 2,
      "Nom": "CC-456-DD",
      "Volume_dispo": 12
    },
    {
      "Id_vehicules": 3,
      "Nom": "TR-789-XX",
      "Volume_dispo": 28
    },
    {
      "Id_vehicules": 4,
      "Nom": "PL-321-KK",
      "Volume_dispo": 18
    }
  ],
  "config": "equilibre"
}

def osrm_time_distance(lat1, lon1, lat2, lon2):
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{lon1},{lat1};{lon2},{lat2}?overview=false"
    )
    r = requests.get(url).json()
    route = r["routes"][0]
    distance_km = route["distance"] / 1000
    duration_min = route["duration"] / 60
    return distance_km, duration_min

def geocode(address, retries=3):
    geolocator = Nominatim(user_agent="vrp_concerts")
    for attempt in range(retries):
        try:
            time_module.sleep(1)
            location = geolocator.geocode(address)
            if location:
                return location.latitude, location.longitude
            return None, None
        except (GeocoderTimedOut, GeocoderUnavailable):
            if attempt == retries - 1:
                return None, None
            time_module.sleep(2)

def time_to_minutes(t):
    """Convertit un temps en minutes depuis minuit (0h00)"""
    if t is None or t == "null":
        return None
    if pd.isna(t) if not isinstance(t, str) else False:
        return None
    if isinstance(t, (int, float)):
        return t
    # cas datetime.time ou datetime.datetime
    if hasattr(t, 'hour') and hasattr(t, 'minute'):
        return t.hour * 60 + t.minute
    return None


# ========================================
# Chargement des données depuis data_test
# ========================================

df_Lieux        = pd.DataFrame(data_test["lieux"])
df_Instruments  = pd.DataFrame(data_test["instruments"])
df_Vehicules    = pd.DataFrame(data_test["vehicules"])

# Dictionnaire {instrument: volume}
volume_map = df_Instruments.set_index("Nom")["Volume"].to_dict()

# Fonction de calcul du volume total
def calcul_volume(instruments):
    if pd.isna(instruments):
        return 0
    return sum(
        volume_map.get(instr.strip(), 0)
        for instr in instruments.split(",")
    )

# Ajout de la colonne dans df_Lieux
df_Lieux["Volume_total_instruments"] = df_Lieux["Instruments"].apply(calcul_volume)

# Nodes = identifiants des lieux
nodes = df_Lieux["Id_Lieux"].tolist()



# Demande (volume à livrer par lieu)
demand = dict(
    zip(df_Lieux["Id_Lieux"], df_Lieux["Volume_total_instruments"])
)


vehicules = df_Vehicules["Id_vehicules"].tolist()

capacity = dict(
    zip(df_Vehicules["Id_vehicules"], df_Vehicules["Volume_dispo"])
)

# Geocodage : utilise les coordonnées existantes si valides (lat != 0 et lon != 0),
# sinon appelle le geocodeur
def resolve_coords(row):
    lat, lon = row.get("lat", 0), row.get("lon", 0)
    if lat and lon and (lat != 0 or lon != 0):
        return pd.Series([lat, lon])
    return pd.Series(geocode(row["Adresse"]))

df_Lieux[["lat", "lon"]] = df_Lieux.apply(resolve_coords, axis=1)

travel_time = {}
distance = {}

for _, row_i in df_Lieux.iterrows():
    for _, row_j in df_Lieux.iterrows():
        i, j = row_i["Id_Lieux"], row_j["Id_Lieux"]
        if i != j:
            d_km, t_min = osrm_time_distance(
                row_i["lat"], row_i["lon"],
                row_j["lat"], row_j["lon"]
            )
            travel_time[(i, j)] = t_min
            distance[(i, j)] = d_km

# ========================================
# Modèle d'optimisation
# ========================================

x = pulp.LpVariable.dicts(
    "x",
    ((i, j, v) for i in nodes for j in nodes for v in vehicules if i != j),
    cat="Binary"
)


y = pulp.LpVariable.dicts("y", vehicules, cat="Binary")

arrival_time = pulp.LpVariable.dicts(
    "arrival_time",
    ((j, v) for j in nodes for v in vehicules),
    lowBound=0,
    cat="Continuous"
)


model = pulp.LpProblem("VRP_Concerts", pulp.LpMinimize)

model += (
    1000 * pulp.lpSum(y[v] for v in vehicules)
    + 10 * pulp.lpSum(
        travel_time[i, j] * x[i, j, v]
        for (i, j) in travel_time
        for v in vehicules
    )
)

# Chaque lieu desservi exactement une fois
for j in nodes:
    if j != 0:
        model += pulp.lpSum(
            x[i, j, v] for i in nodes if i != j for v in vehicules
        ) == 1

# Capacité des véhicules
for v in vehicules:
    model += pulp.lpSum(
        demand[j] * pulp.lpSum(x[i, j, v] for i in nodes if i != j)
        for j in nodes
    ) <= capacity[v]

# Départ et retour au dépôt
for v in vehicules:
    model += pulp.lpSum(x[0, j, v] for j in nodes if j != 0) == y[v]
    model += pulp.lpSum(x[i, 0, v] for i in nodes if i != 0) == y[v]

# Continuité de la tournée
for v in vehicules:
    for j in nodes:
        if j != 0:
            model += (
                pulp.lpSum(x[i, j, v] for i in nodes if i != j) ==
                pulp.lpSum(x[j, k, v] for k in nodes if k != j)
            )

# Activation du véhicule si utilisé
for v in vehicules:
    for i in nodes:
        for j in nodes:
            if i != j:
                model += x[i, j, v] <= y[v]

# Fenêtres horaires et heures de concert
time_window_early = {}
concert_time      = {}

for _, row in df_Lieux.iterrows():
    lieu_id = row["Id_Lieux"]
    time_window_early[lieu_id] = time_to_minutes(row.get("HeureTot", None))
    concert_time[lieu_id]      = time_to_minutes(row.get("HeureConcert", None))

depot_opening = 8 * 60  # 8h00
time_window_early[0] = depot_opening
concert_time[0]      = 24 * 60

service_time = 60  # minutes de déchargement
M            = 1600

# Départ au plus tôt depuis le dépôt
for v in vehicules:
    model += arrival_time[0, v] >= depot_opening * y[v], f"Depart_depot_inf_{v}"

# Départ du dépôt
for v in vehicules:
    model += pulp.lpSum(x[0, j, v] for j in nodes if j != 0) == y[v], f"Depart_depot_{v}"

# Retour au dépôt
for v in vehicules:
    model += pulp.lpSum(x[i, 0, v] for i in nodes if i != 0) == y[v], f"Retour_depot_{v}"

# Arriver avant le concert (déchargement service_time inclus)
for j in nodes:
    if j != 0 and concert_time[j] is not None:
        for v in vehicules:
            visit = pulp.lpSum(x[i, j, v] for i in nodes if i != j)
            model += (
                arrival_time[j, v] + service_time <= concert_time[j] + M * (1 - visit)
            ), f"Avant_concert_{j}_{v}"

# Fenêtre horaire : arrivée pas trop tôt
for j in nodes:
    if j != 0 and time_window_early[j] is not None:
        for v in vehicules:
            visit = pulp.lpSum(x[i, j, v] for i in nodes if i != j)
            model += (
                arrival_time[j, v] >= time_window_early[j] - M * (1 - visit)
            ), f"Fenetre_early_{j}_{v}"

# Propagation du temps d'arrivée (MTZ)
for v in vehicules:
    for i in nodes:
        for j in nodes:
            if i != j and j != 0:
                model += (
                    arrival_time[j, v]
                    >= arrival_time[i, v] + service_time + travel_time[(i, j)]
                    - M * (1 - x[i, j, v])
                ), f"MTZ_{i}_{j}_{v}"


def extract_routes_full(x, y, nodes, vehicules, df_Lieux, df_Vehicules, travel_time, distance):
    """Retourne les routes par véhicule avec destinations, instruments, temps et distances."""

    lieu_name     = dict(zip(df_Lieux["Id_Lieux"], df_Lieux["Nom"]))
    lieu_instr    = dict(zip(df_Lieux["Id_Lieux"], df_Lieux["Instruments"]))
    vehicule_name = dict(zip(df_Vehicules["Id_vehicules"], df_Vehicules["Nom"]))

    routes = {}

    for v in vehicules:
        if y[v].value() != 1:
            continue

        arcs = [(i, j) for (i, j, vv) in x if vv == v and x[i, j, v].value() == 1]

        route, current = [0], 0
        while True:
            next_nodes = [j for (i, j) in arcs if i == current]
            if not next_nodes:
                break
            current = next_nodes[0]
            route.append(current)
            if current == 0:
                break

        destinations       = [lieu_name[i] for i in route if i != 0]
        instruments_par_lieu = {}
        instrument_counter   = Counter()

        for i in route:
            if i != 0 and pd.notna(lieu_instr[i]) and lieu_instr[i]:
                items = [instr.strip() for instr in lieu_instr[i].split(",")]
                instruments_par_lieu[lieu_name[i]] = dict(Counter(items))
                instrument_counter.update(items)

        segments       = []
        total_time     = 0
        total_distance = 0

        for k in range(len(route) - 1):
            i, j = route[k], route[k + 1]
            t = travel_time.get((i, j), 0)
            d = distance.get((i, j), 0)
            segments.append({
                "from": lieu_name[i],
                "to": lieu_name[j],
                "time_min": round(t, 1),
                "distance_km": round(d, 2)
            })
            total_time     += t
            total_distance += d

        routes[v] = {
            "vehicule": vehicule_name[v],
            "route_ids": route,
            "destinations": destinations,
            "segments": segments,
            "instruments_par_lieu": instruments_par_lieu,
            "instruments_quantites_total": dict(instrument_counter),
            "total_time_min": round(total_time, 1),
            "total_distance_km": round(total_distance, 2)
        }

    return routes


# ========================================
# RÉSOLUTION ET AFFICHAGE
# ========================================

status = model.solve(pulp.PULP_CBC_CMD(msg=True))

print("=" * 80)
print(f"📊 STATUT DE LA RÉSOLUTION : {pulp.LpStatus[model.status]}")
print("=" * 80)

if model.status == pulp.LpStatusOptimal:
    routes = extract_routes_full(
        x, y, nodes, vehicules, df_Lieux, df_Vehicules, travel_time, distance
    )

    for v, info in routes.items():
        print("\n" + "=" * 80)
        print(f"🚚 VÉHICULE : {info['vehicule']}")
        print("=" * 80)
        print(f"\n📍 Itinéraire : Dépôt → {' → '.join(info['destinations'])} → Dépôt")

        print(f"\n🛣️  DÉTAILS DES TRAJETS :")
        print("-" * 80)
        for seg in info["segments"]:
            print(f"  {seg['from']:20s} → {seg['to']:20s} | {seg['distance_km']:6.2f} km | {seg['time_min']:6.1f} min")

        print(f"\n🎸 INSTRUMENTS À DÉCHARGER PAR LIEU :")
        print("-" * 80)
        for lieu, instruments in info["instruments_par_lieu"].items():
            print(f"\n  📍 {lieu} :")
            for instr, qty in instruments.items():
                print(f"      • {instr} : {qty}")

        print(f"\n📦 RÉCAPITULATIF TOTAL DES INSTRUMENTS TRANSPORTÉS :")
        print("-" * 80)
        for instr, qty in sorted(info["instruments_quantites_total"].items()):
            print(f"  • {instr} : {qty}")

        print(f"\n⏱️  TEMPS & DISTANCE TOTAUX :")
        print(f"  • Distance : {info['total_distance_km']} km")
        print(f"  • Temps    : {info['total_time_min']} min ({info['total_time_min']/60:.1f}h)")

    print("\n" + "=" * 80)
    print(f"✅ RÉSOLUTION TERMINÉE - {len(routes)} véhicule(s) utilisé(s)")
    print("=" * 80)

else:
    print(f"\n❌ ÉCHEC : {pulp.LpStatus[model.status]}")
    print("  1. Vérifiez que la capacité totale ≥ demande totale")
    print("  2. Vérifiez les fenêtres horaires (trop strictes ?)")