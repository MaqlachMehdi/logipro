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
      "Instruments": "",
      "TempsInstallation": 60,
      "TempsDesinstallation": 60,
      "DureeConcert": 120
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
      "Instruments": "Ampli Guitare, Ampli Guitare, Ampli Guitare, Ampli Guitare, Ampli Guitare, Ampli Basse, Ampli Basse, Ampli Basse, Ampli Basse, Ampli Basse, Basse, Basse, Basse, Basse, Basse, Guitare Acoustique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Drum Kit Complete, Drum Kit Complete",
      "TempsInstallation": 70,
      "TempsDesinstallation": 50,
      "DureeConcert": 100
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
      "Instruments": "Drum Kit Complete, Drum Kit Complete, Drum Kit Complete",
      "TempsInstallation": 40,
      "TempsDesinstallation": 30,
      "DureeConcert": 60
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
      "Instruments": "Guitare Électrique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Guitare Électrique, Basse, Basse, Basse, Basse, Basse, Basse, Basse, Guitare Acoustique, Guitare Acoustique, Guitare Acoustique, Guitare Acoustique, Guitare Acoustique, Guitare Acoustique, Ampli Guitare, Ampli Guitare, Ampli Guitare, Ampli Guitare, Ampli Guitare, Ampli Guitare, Ampli Basse, Pedalboard, Pedalboard, Pedalboard, Pedalboard, Pedalboard, Pedalboard",
      "TempsInstallation": 50,
      "TempsDesinstallation": 40,
      "DureeConcert": 80
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

def get_id(node):
    """Extrait l'id physique d'un noeud."""
    return node if isinstance(node, int) else node[0]

def get_dist(i, j):
    pi, pj = get_id(i), get_id(j)
    if pi == pj:
        return 0.0
    return D[(pi, pj)]

def get_time(i, j):
    pi, pj = get_id(i), get_id(j)
    if pi == pj:
        return 0.0
    return travel_time[(pi, pj)]

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


#################### Modèle VRP en opti lin sans contraintes avec time windows diff et delivery et picking découplé ####################

########## Paramètres ##########

###### Noeuds dédoublés pour différencier livraison et ramasse

# On crée 2 noeuds avec la même position mais une demande opposé 
# et des créneaux horaires différents pour différencier la livraison avant le concert 
# et la ramasse après le concert sauf pour dépôt qui n'a pas de demande ni de créneau horaire de concert

# Convention : (id_lieu, "d") pour livraison, (id_lieu, "r") pour ramasse

nodes    = [lieu["Id_Lieux"]   for lieu in data_test["lieux"] if lieu["Id_Lieux"] != 0]  # on retire dépôt
nodes_and_dep = nodes + [lieu["Id_Lieux"] for lieu in data_test["lieux"] if lieu["Id_Lieux"] == 0]

from dataclasses import dataclass

NODES_TYPE = {"delivery","recollect"}

@dataclass
class Node:
    id:int
    type:int

nodes_livraison = [(v, "d") for v in nodes]  # ex: (1,"d"), (2,"d"), (3,"d")
nodes_ramasse   = [(v, "r") for v in nodes]  # ex: (1,"r"), (2,"r"), (3,"r")

all_nodes = [lieu["Id_Lieux"] for lieu in data_test["lieux"] if lieu["Id_Lieux"] == 0] + nodes_livraison + nodes_ramasse

#print(all_nodes)

# Lookup volume par instrument
vol_lookup = {inst["Nom"]: inst["Volume"] for inst in data_test["instruments"]}

# Volume physique de chaque venue
def volume_venue(id_lieu):
    lieu = next(l for l in data_test["lieux"] if l["Id_Lieux"] == id_lieu)
    items = [s.strip() for s in lieu["Instruments"].split(",") if s.strip()]
    return sum(vol_lookup.get(item, 0.0) for item in items)

# Demande de chaque noeud :
#   (v, "d")  → négatif  : on DÉPOSE des instruments (charge diminue)
#   (v, "r")  → positif  : on CHARGE des instruments (charge augmente)
#   dépôt (0) → 0
demand = {}
demand[0] = 0
for v in nodes:
    demand[(v, "d")] = -volume_venue(v)   # livraison : on vide le camion
    demand[(v, "r")] = +volume_venue(v)   # ramasse   : on remplit le camion

print("demand : dict demand at each node", demand)

# Marges de sécurité (en minutes)
MARGE_AVANT_CONCERT  = 15   # marge tampon avant le début du concert
MARGE_APRES_CONCERT  = 20   # marge de retard possible du concert
MARGE_FERMETURE      = 30   # on ne peut pas arriver trop près de la fermeture

# Lookup des données par id_lieu
lieu_data = {lieu["Id_Lieux"]: lieu for lieu in data_test["lieux"]}

a = {}   # borne inférieure d'arrivée (earliest)
b = {}   # borne supérieure d'arrivée (latest)

# Dépôt : toute la journée
a[0] = lieu_data[0]["HeureTot"]
b[0] = lieu_data[0]["HeureTard"]

for v in nodes:
    d = lieu_data[v]
    hc    = d["HeureConcert"]
    ouv   = d["HeureTot"]
    ferm  = d["HeureTard"]
    t_ins = d["TempsInstallation"]
    t_des = d["TempsDesinstallation"]
    duree = d["DureeConcert"]

    # Noeud de LIVRAISON (v, "d")
    # → arriver entre l'ouverture et (concert - installation - marge)
    a[(v, "d")] = ouv
    b[(v, "d")] = hc - t_ins - MARGE_AVANT_CONCERT

    # Noeud de RAMASSE (v, "r")
    # → arriver entre (concert + durée + marge retard) et (fermeture - marge)
    a[(v, "r")] = hc + duree + MARGE_APRES_CONCERT
    b[(v, "r")] = ferm - t_des - MARGE_FERMETURE

print("a : ", a)
print("b : ", b)


vehicles = [v["Id_vehicules"] for v in data_test["vehicules"]]

# Coordonnées de chaque node : {Id_Lieux: (lat, lon)}
coords = {lieu["Id_Lieux"]: (lieu["lat"], lieu["lon"]) for lieu in data_test["lieux"]}

# Matrices distances (km) et temps (min) entre chaque paire de nodes
D            = {}  # D[(i, j)]  = distance en km
travel_time  = {}  # travel_time[(i, j)] = durée en minutes

for i in nodes_and_dep:
    for j in nodes_and_dep:
        if i != j:
            lat1, lon1 = coords[i]
            lat2, lon2 = coords[j]
            d_km, t_min = osrm_time_distance(lat1, lon1, lat2, lon2) #ce qui ralentit le code car api politesse 
            D[(get_id(i), get_id(j))]= d_km
            travel_time[(i, j)] = t_min

print("D : dict dist between nodes", D)
print("travel_time : dict travel_time between nodes", travel_time)


#### Pour les véhicules k
#Capacité : Q_k
#Horaire de travail : [a_k , b_k] ( départ/ retour max au dépôt par véhicules) rajoute de la compléxité jsp si je vais l'implémenter
Q = {k["Id_vehicules"]: k["Volume_dispo"] for k in data_test["vehicules"]}

########## VARIABLES ###########

#x[v,w,k] = 1 si le véhicule v va de w à k, 0 sinon
x = pulp.LpVariable.dicts("x" , [(v,w,k) for v in all_nodes for w in all_nodes for k in vehicles if v!=w], cat = 'Binary')

#T[v,k] >= 0 temps d'arrivée au node V pour le véhicules K
T = pulp.LpVariable.dicts("T", [(v,k) for v in all_nodes for k in vehicles], lowBound = 0 , cat = "Continuous" )

#L[v,k] >= 0 charge (volume d'instrument) à bord du véhicule k à l'arrivée au noeud v
L = pulp.LpVariable.dicts("L" , [(v,k) for v in all_nodes for k in vehicles], lowBound = 0 , cat = "Continuous")

"""# W_d[v,k] : temps d'attente sur place avant de pouvoir décharger
#             = max(0,  a[(v,"d")] - T[(v,"d"),k])   ← arrivée avant l'ouverture
W_d = pulp.LpVariable.dicts("W_d",
    [(v,k) for v in nodes for k in vehicles], lowBound=0, cat="Continuous")

# W_r[v,k] : temps d'attente sur place avant de pouvoir charger
#             = max(0,  a[(v,"r")] - T[(v,"r"),k])   ← arrivée avant fin de concert
W_r = pulp.LpVariable.dicts("W_r",
    [(v,k) for v in nodes for k in vehicles], lowBound=0, cat="Continuous")

"""
########## Fonction Loss ##########

#crea du PB 
prob =  pulp.LpProblem("VRPPPD" , pulp.LpMinimize)

alpha_dist   = 1.0    # poids distance
alpha_temps  = 0.01   # poids temps d'arrivée cumulé
beta_attente = 5.0    # poids attente avant concert  (livraison)
gamma_ramasse = 5.0   # poids attente avant ramasse  (pickup)

prob += (
    alpha_dist * pulp.lpSum(
        get_dist(v, w) * x[v, w, k]
        for v in all_nodes for w in all_nodes for k in vehicles if v != w
    ))
    
"""    )
    + beta_attente  * pulp.lpSum(W_d[(v,k)] for v in nodes for k in vehicles)
    + gamma_ramasse * pulp.lpSum(W_r[(v,k)] for v in nodes for k in vehicles)
)"""



########## Contraintes ##########

########## Contraintres de flux ##########

# Chaque lieu doit être livré exactement une fois (par un véhicule quelconque)
for v in nodes_livraison:
    prob += pulp.lpSum(x[v, w, k] for w in all_nodes for k in vehicles if w != v) == 1

# Chaque lieu doit être ramassé exactement une fois (par un véhicule quelconque)
for v in nodes_ramasse:
    prob += pulp.lpSum(x[v, w, k] for w in all_nodes for k in vehicles if w != v) == 1

# Pour chaque noeud intermédiaire (hors dépôt) et chaque véhicule :
# nb d'arcs entrants == nb d'arcs sortants
for v in nodes_livraison + nodes_ramasse:
    for k in vehicles:
        prob += (
            pulp.lpSum(x[u, v, k] for u in all_nodes if u != v)   # arcs entrants
            ==
            pulp.lpSum(x[v, w, k] for w in all_nodes if w != v)   # arcs sortants
        )
  
id_depot = 0 

# Chaque véhicule part au plus une fois du dépôt
for k in vehicles:
    prob += pulp.lpSum(x[id_depot, w, k] for w in all_nodes if w != id_depot) <= 1

# Chaque véhicule revient au plus une fois au dépôt
for k in vehicles:
    prob += pulp.lpSum(x[v, id_depot, k] for v in all_nodes if v != id_depot) <= 1

# Cohérence : nb de départs = nb de retours (si part, revient)
for k in vehicles:
    prob += (
        pulp.lpSum(x[id_depot, w, k] for w in all_nodes if w != id_depot)
        ==
        pulp.lpSum(x[v, id_depot, k] for v in all_nodes if v != id_depot)
    )

########## Contraintes temporels ##########

# Borne inférieure sur T pour tous les noeuds
for v in nodes_livraison + nodes_ramasse:
    for k in vehicles:
        prob += T[v, k] >= a[v]

# Borne supérieure sur T pour tous les noeuds
for v in nodes_livraison + nodes_ramasse:
    for k in vehicles:
        prob += T[v, k] <= b[v]

# Le véhicule ne part pas avant l'ouverture du dépôt
for k in vehicles:
    prob += T[id_depot, k] >= a[id_depot]   # a[0] = 480 min = 8h00
    prob += T[id_depot, k] <= b[id_depot]   # b[0] = 1380 min = 23h00

M = 1600  # grand nombre > durée max possible de la journée (en minutes)

# Temps de service par noeud (durée de déchargement ou chargement)
s = {}
for v in nodes:
    s[(v, "d")] = lieu_data[v]["TempsInstallation"]     # déchargement avant concert
    s[(v, "r")] = lieu_data[v]["TempsDesinstallation"]  # chargement après concert
s[id_depot] = 0  # pas de service au dépôt

# Propagation du temps entre deux noeuds consécutifs
for v in all_nodes:
    for w in all_nodes:
        if v != w:
            for k in vehicles:
                prob += (
                    T[w, k] >= T[v, k] + s[v] + get_time(v, w) - M * (1 - x[v, w, k])
                )


########## Contraintes de capacité ##########

# L[v, k] = charge (volume) à bord du véhicule k à l'ARRIVÉE au nœud v

# Borne supérieure : la charge ne dépasse jamais la capacité du véhicule
for v in all_nodes:
    for k in vehicles:
        prob += L[v, k] <= Q[k]

# Borne inférieure déjà assurée par lowBound=0 dans la déclaration de L

# Propagation de la charge entre deux nœuds consécutifs :
#    Si x[v,w,k] = 1  →  L[w,k] = L[v,k] + demand[w] force l'égalité
#    Linéarisé avec big-M :
#      L[w,k] >= L[v,k] + demand[w] - Q[k] * (1 - x[v,w,k])
#      L[w,k] <= L[v,k] + demand[w] + Q[k] * (1 - x[v,w,k])

for v in all_nodes:
    for w in all_nodes:
        if v != w:
            for k in vehicles:
                prob += (
                    L[w, k] >= L[v, k] + demand[w] - Q[k] * (1 - x[v, w, k])
                )
                prob += (
                    L[w, k] <= L[v, k] + demand[w] + Q[k] * (1 - x[v, w, k])
                )

# Note : on ne fixe PAS L[depot, k] explicitement.
# L[depot, k] représente la charge à l'ARRIVÉE au dépôt (fin de tournée).
# En fin de tournée : tout a été livré (charge -) ET tout a été ramassé (charge +)
# → la charge de retour n'est PAS nécessairement égale au volume de départ.
# La propagation big-M ci-dessus suffit à garantir la cohérence sur toute la route.
# La seule contrainte naturelle est L[depot, k] >= 0 (déjà via lowBound) et <= Q[k].


############### Solution du problème et affichage des résultats ###############

prob.solve(pulp.PULP_CBC_CMD(msg=1))
print("Statut :", pulp.LpStatus[prob.status])


"""
# ── Contraintes qui définissent W ─────────────────────────────────────────
for v in nodes:
    for k in vehicles:
        # attente livraison : on ne peut pas décharger avant a[(v,"d")]
        prob += W_d[(v,k)] >= a[(v,"d")] - T[(v,"d"),k]

        # attente ramasse : on ne peut pas charger avant a[(v,"r")]
        prob += W_r[(v,k)] >= a[(v,"r")] - T[(v,"r"),k]

# ── Contraintes de fenêtres (obligatoires pour éviter le "tricher") ───────
for v in nodes:
    for k in vehicles:
        prob += T[(v,"d"),k] >= a[(v,"d")]   # pas avant l'ouverture
        prob += T[(v,"d"),k] <= b[(v,"d")]   # pas après la deadline livraison
        prob += T[(v,"r"),k] >= a[(v,"r")]   # pas avant fin concert
        prob += T[(v,"r"),k] <= b[(v,"r")]   # pas après fermeture ramasse

        """