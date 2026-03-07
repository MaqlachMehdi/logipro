import pandas as pd
import pulp
from geopy.geocoders import Nominatim
import time as time_module
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import requests
from collections import Counter
from tqdm import tqdm




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


DEBUG = 1
def osrm_time_distance(lat1, lon1, lat2, lon2)->tuple[float,int]:
    if DEBUG : 
        return 0,0
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

# Marges de sécurité (en minutes)
MARGE_AVANT_CONCERT  = 15   # marge tampon avant le début du concert
MARGE_APRES_CONCERT  = 20   # marge de retard possible du concert
MARGE_FERMETURE      = 30   # on ne peut pas arriver trop près de la fermeture

from dataclasses import dataclass
@dataclass
class LossParams:
  alpha_time      :float
  alpha_distance  :float

# Volume physique de chaque venue
def volume_venue(id_lieu):
    lieu = next(l for l in data_test["lieux"] if l["Id_Lieux"] == id_lieu)
    items = [s.strip() for s in lieu["Instruments"].split(",") if s.strip()]
    return sum(vol_lookup.get(item, 0.0) for item in items)

@dataclass
class OrientedEdges:
    distances_km       :dict[tuple[int,int] , float]
    travel_times_min    :dict[tuple[int,int] , float]

    def __str__(self):
        return_str = ("===  DISTANCE\n")
        for (i,j),d in self.distances_km.items():
            return_str += (f"({i} --> {j}) : {d:.2f}km\n")
        return_str += ("===  DURÉE\n")
        for (i,j),d in self.travel_times_min.items():
            return_str += (f"({i} --> {j}) : {d:.0f}min\n")
        return return_str

@dataclass
class TimeWindow:
  start_minutes: int
  end_minutes: int

  def __post_init__(self):
      if self.start_minutes < 0 or self.end_minutes < self.start_minutes:
          raise ValueError(f"Invalid time window from : {self.start_minutes} to {self.end_minutes}")
  def __str__(self):
      return f"TimeWindow : {self.start_minutes}min - {self.end_minutes}min"

@dataclass
class Vehicule:
    id:str
    max_volume:float
    def __post_init__(self):
        if self.max_volume <= 0:
            raise ValueError(f"Vehicule {self.id} with volume <= 0 ? ({self.max_volume})m3")
    def __str__(self):
        return f"Véhicule : {self.id} (max. volume {self.max_volume}m³)"

@dataclass
class Node:
    id: int
    required_volume: float  | None = None
    time_window: TimeWindow | None = None
    gps_coordinates: tuple[float,float] | None = None



class DepositNode(Node):
    def __init__(self, id):
        super().__init__(id)

    def __str__(self):
        return f"Deposit node n°{self.id} required volume : {self.required_volume}"


class DeliveryNode(Node):
    def __init__(self, id):
        super().__init__(id)

    def __str__(self):
        return f"Delivery node n°{self.id} required volume : {self.required_volume}"
    

    def health_check(self):
      if self.required_volume < 0 and self.required_volume is not(None): 
        raise ValueError("Invalid volume sign.")
      
      if self.gps_coordinates is not None : 
          if len(self.gps_coordinates) != 2 :
              raise ValueError(f"Coordinates of length {len(self.gps_coordinates)}, should be of length 2 !!!")

    


class RecoveryNode(Node):
    def __init__(self, id):
        super().__init__(id)
    def __str__(self):
          return f"Recovery node n°{self.id} required volume : {self.required_volume}"
    def health_check(self):
      if self.required_volume > 0 and self.required_volume is not(None): 
        raise ValueError("Invalid volume sign.")


@dataclass 
class Problem:
    # META DATA
    name:str
    # GRAPH
    deposit_node    :DepositNode
    delivery_nodes  :list[DeliveryNode]
    recovery_node   :list[RecoveryNode]
    oriented_edges  :OrientedEdges
    # Vehicules 
    vehicules_dict  :dict[Vehicule] # key = imattriculation

    # Solver params
    loss_params         :LossParams

    def health_check(self):
        
        for (deli_node,recov_node) in zip(self.delivery_nodes,self.recovery_node):
            if not(isinstance(deli_node,DeliveryNode)):
                raise TypeError(f"Found a delivery node that is actually a {type(deli_node)}")
            if not(isinstance(recov_node,RecoveryNode)):
                raise TypeError(f"Found a recovery node that is actually a {type(deli_node)}")
        if len(self.delivery_nodes) != len(self.recovery_node):
            raise ValueError("More recovery nodes than delivery nodes")
        
    def __post_init__(self):
        self.number_of_locations = len(self.delivery_nodes)
        self.health_check()
        
    @property
    def n_of_nodes(self)->int:
        return 2*self.number_of_locations + 1
    
    @property
    def all_nodes(self)->list[Node]:
      return [self.deposit_node] + self.delivery_nodes + self.recovery_node


nodes_ids =[lieu["Id_Lieux"] for lieu in data_test["lieux"] if lieu["Id_Lieux"] != 0]  # on retire dépôt

deposit_node = DepositNode(0)
nodes_livraison = [DeliveryNode(node_id) for node_id in nodes_ids]
nodes_ramasse   = [RecoveryNode(node_id) for node_id in nodes_ids]


all_nodes = [deposit_node] + [nodes_livraison] + [nodes_ramasse]
target_nodes = [nodes_livraison] + [nodes_ramasse]

# Lookup volume par instrument
vol_lookup = {inst["Nom"]: inst["Volume"] for inst in data_test["instruments"]}


lieux = data_test["lieux"]

# === INITIALISATIONS ===
# initialize deposit 
deposit_data = lieux[deposit_node.id]
deposit_node.gps_coordinates = (deposit_data["lat"], deposit_data["lon"])
deposit_node.time_window = TimeWindow(start_minutes=deposit_data["HeureTot"], end_minutes=deposit_data["HeureTard"])
# initialize other nodes 
for (delivery_node,recovery_node) in zip(nodes_livraison,nodes_ramasse):
    node_id = delivery_node.id
    assert delivery_node.id == recovery_node.id
    # VOLUMES 
    delivery_node.required_volume = +volume_venue(delivery_node.id)
    recovery_node.required_volume = -volume_venue(recovery_node.id)

    # TIME WINDOWS
    node_data = lieux[node_id]
    concert_start_time = node_data["HeureConcert"]
    location_oppening  = node_data["HeureTot"]
    location_closing  = node_data["HeureTard"]
    time_to_install = node_data["TempsInstallation"]
    time_to_uninstall = node_data["TempsDesinstallation"]
    concert_duration = node_data["DureeConcert"]

    delivery_time_window = TimeWindow(start_minutes=location_oppening,end_minutes=concert_start_time - time_to_install - MARGE_AVANT_CONCERT)
    recovery_time_window = TimeWindow(start_minutes=concert_start_time + concert_duration + MARGE_APRES_CONCERT,end_minutes= location_closing - time_to_uninstall - MARGE_FERMETURE)

    delivery_node.time_window = delivery_time_window
    recovery_node.time_window = recovery_time_window

    # COORDINATES
    coordinate = (node_data["lat"],node_data["lon"]) 
    delivery_node.gps_coordinates=coordinate
    recovery_node.gps_coordinates=coordinate

    # HEALTH CHECKS
    delivery_node.health_check()
    recovery_node.health_check()


from time import time_ns
def make_oriented_edges(recovery_nodes:list[RecoveryNode],delivery_nodes:list[DepositNode],deposit_node:DepositNode)->OrientedEdges:
    distances = dict()
    travel_times = dict()

    distances[(deposit_node.id, deposit_node.id)] = 0
    travel_times[(deposit_node.id, deposit_node.id)] = 0
    print("Getting GeoData...")
    total_geo_time_ns = 0
    total_edges = 0
    for node_1 in tqdm(recovery_nodes):
        dist_to_depot,time_to_depot = osrm_time_distance(
          node_1.gps_coordinates[0],node_1.gps_coordinates[1],
          deposit_node.gps_coordinates[0],deposit_node.gps_coordinates[1])

        dist_from_depot,time_from_depot = osrm_time_distance(
          deposit_node.gps_coordinates[0],deposit_node.gps_coordinates[1],
          node_1.gps_coordinates[0],node_1.gps_coordinates[1])

        distances[(node_1.id, deposit_node.id)] = dist_to_depot
        travel_times[(node_1.id, deposit_node.id)] = time_to_depot

        distances[(deposit_node.id,node_1.id)] = dist_from_depot
        travel_times[(deposit_node.id,node_1.id)] = time_from_depot
        total_edges+=2
        for node_2 in delivery_nodes:
            total_edges+=1
            t0 = time_ns()
            dist,time = osrm_time_distance(
                node_1.gps_coordinates[0],node_1.gps_coordinates[1],
                node_2.gps_coordinates[0],node_2.gps_coordinates[1])
            total_geo_time_ns += time_ns() - t0

            # update
            distances[(node_1.id, node_2.id)] = dist
            travel_times[(node_1.id, node_2.id)] = time

    print(f"GeoData time per request: {total_geo_time_ns / total_edges / 1_000_000:.1f} ms")
    return OrientedEdges(distances_km=distances, travel_times_min=travel_times)

oriented_edges = make_oriented_edges(nodes_ramasse, nodes_livraison, deposit_node)

vehicules_dict: dict[str,Vehicule] = dict()
for vehicule in data_test["vehicules"]:
    vehicules_dict[vehicule["Nom"]] = Vehicule(id=vehicule["Nom"], max_volume=vehicule["Volume_dispo"])



loss_params = LossParams(alpha_time=0.01, alpha_distance=1.0)
problem = Problem(
    "VRPPD Concerts",
    deposit_node,
    nodes_livraison,
    nodes_ramasse,
    vehicules_dict=vehicules_dict,
    oriented_edges=oriented_edges,
    loss_params=loss_params
)


########## VARIABLES ###########


def add_loss(
        pulp_problem:pulp.LpProblem,
        problem:Problem,
        choose_edges:dict[tuple[int,int,str],pulp.LpVariable]
        )->pulp.LpProblem:
  
  pulp_problem += (
      loss_params.alpha_distance * pulp.lpSum(
          problem.oriented_edges.distances_km[(node_start.id, node_end.id)] * choose_edges[node_start.id, node_end.id, vehicule.id]
          for node_start in problem.all_nodes for node_end in problem.all_nodes for vehicule in problem.vehicules_dict.values() if node_start != node_end))

  return pulp_problem

# x[v,w,k] = 1 si le véhicule v va de w à k, 0 sinon
def build_pulp_problem(problem:Problem)->pulp.LpProblem:
  choose_edges = pulp.LpVariable.dicts(
      "e",
      cat='Binary',
      indices=[
          (start_node.id,end_node.id,vehicule.id) 
            for start_node in problem.all_nodes for end_node in problem.all_nodes for vehicule in problem.vehicules_dict.values() if start_node != end_node])

  times_arrival = pulp.LpVariable.dicts(
      "time_arrival",
      [(node.id,vehicule.id) for node in problem.all_nodes for vehicule in problem.vehicules_dict.values()],
      lowBound=0,
      cat = "Continuous")
  
  loads_at_arrival = pulp.LpVariable.dicts(
      "load_at_arrival",
      [(node.id,vehicule.id) for node in problem.all_nodes for vehicule in problem.vehicules_dict.values()],
      lowBound=0, cat="Continuous")

  pulp_problem =  pulp.LpProblem(problem.name , pulp.LpMinimize)

  pulp_problem = add_loss(pulp_problem, problem, choose_edges)

  return pulp_problem



pulp_problem = build_pulp_problem(problem)
pulp_problem.solve()

# OSEF POUR L'INSTANT MAIS ON POURRAIT AVOIR BESOIN DE VARIABLES D'ATTENTE POUR MODÉLISER LES PÉNALITÉS D'ARRIVÉE TROP TÔT
# """# W_d[v,k] : temps d'attente sur place avant de pouvoir décharger
# #             = max(0,  a[(v,"d")] - T[(v,"d"),k])   ← arrivée avant l'ouverture
# W_d = pulp.LpVariable.dicts("W_d",
#     [(v,k) for v in nodes for k in vehicles], lowBound=0, cat="Continuous")

# # W_r[v,k] : temps d'attente sur place avant de pouvoir charger
# #             = max(0,  a[(v,"r")] - T[(v,"r"),k])   ← arrivée avant fin de concert
# W_r = pulp.LpVariable.dicts("W_r",
#     [(v,k) for v in nodes for k in vehicles], lowBound=0, cat="Continuous")

# """
# ########## Fonction Loss ##########

# #crea du PB 


# alpha_dist   = 1.0    # poids distance
# alpha_temps  = 0.01   # poids temps d'arrivée cumulé
# beta_attente = 5.0    # poids attente avant concert  (livraison)
# gamma_ramasse = 5.0   # poids attente avant ramasse  (pickup)

# prob += (
#     alpha_dist * pulp.lpSum(
#         get_dist(v, w) * x[v, w, k]
#         for v in all_nodes for w in all_nodes for k in vehicles if v != w
#     ))
    
# """    )
#     + beta_attente  * pulp.lpSum(W_d[(v,k)] for v in nodes for k in vehicles)
#     + gamma_ramasse * pulp.lpSum(W_r[(v,k)] for v in nodes for k in vehicles)
# )"""



# ########## Contraintes ##########

# ########## Contraintres de flux ##########

# # Chaque lieu doit être livré exactement une fois (par un véhicule quelconque)
# for v in nodes_livraison:
#     prob += pulp.lpSum(x[v, w, k] for w in all_nodes for k in vehicles if w != v) == 1

# # Chaque lieu doit être ramassé exactement une fois (par un véhicule quelconque)
# for v in nodes_ramasse:
#     prob += pulp.lpSum(x[v, w, k] for w in all_nodes for k in vehicles if w != v) == 1

# # Pour chaque noeud intermédiaire (hors dépôt) et chaque véhicule :
# # nb d'arcs entrants == nb d'arcs sortants
# for v in nodes_livraison + nodes_ramasse:
#     for k in vehicles:
#         prob += (
#             pulp.lpSum(x[u, v, k] for u in all_nodes if u != v)   # arcs entrants
#             ==
#             pulp.lpSum(x[v, w, k] for w in all_nodes if w != v)   # arcs sortants
#         )
  
# id_depot = 0 

# # Chaque véhicule part au plus une fois du dépôt
# for k in vehicles:
#     prob += pulp.lpSum(x[id_depot, w, k] for w in all_nodes if w != id_depot) <= 1

# # Chaque véhicule revient au plus une fois au dépôt
# for k in vehicles:
#     prob += pulp.lpSum(x[v, id_depot, k] for v in all_nodes if v != id_depot) <= 1

# # Cohérence : nb de départs = nb de retours (si part, revient)
# for k in vehicles:
#     prob += (
#         pulp.lpSum(x[id_depot, w, k] for w in all_nodes if w != id_depot)
#         ==
#         pulp.lpSum(x[v, id_depot, k] for v in all_nodes if v != id_depot)
#     )

# ########## Contraintes temporels ##########

# # Borne inférieure sur T pour tous les noeuds
# for v in nodes_livraison + nodes_ramasse:
#     for k in vehicles:
#         prob += T[v, k] >= a[v]

# # Borne supérieure sur T pour tous les noeuds
# for v in nodes_livraison + nodes_ramasse:
#     for k in vehicles:
#         prob += T[v, k] <= b[v]

# # Le véhicule ne part pas avant l'ouverture du dépôt
# for k in vehicles:
#     prob += T[id_depot, k] >= a[id_depot]   # a[0] = 480 min = 8h00
#     prob += T[id_depot, k] <= b[id_depot]   # b[0] = 1380 min = 23h00

# M = 1600  # grand nombre > durée max possible de la journée (en minutes)

# # Temps de service par noeud (durée de déchargement ou chargement)
# s = {}
# for v in nodes:
#     s[(v, "d")] = lieu_data[v]["TempsInstallation"]     # déchargement avant concert
#     s[(v, "r")] = lieu_data[v]["TempsDesinstallation"]  # chargement après concert
# s[id_depot] = 0  # pas de service au dépôt

# # Propagation du temps entre deux noeuds consécutifs
# for v in all_nodes:
#     for w in all_nodes:
#         if v != w:
#             for k in vehicles:
#                 prob += (
#                     T[w, k] >= T[v, k] + s[v] + get_time(v, w) - M * (1 - x[v, w, k])
#                 )


# ########## Contraintes de capacité ##########

# # L[v, k] = charge (volume) à bord du véhicule k à l'ARRIVÉE au nœud v

# # Borne supérieure : la charge ne dépasse jamais la capacité du véhicule
# for v in all_nodes:
#     for k in vehicles:
#         prob += L[v, k] <= Q[k]

# # Borne inférieure déjà assurée par lowBound=0 dans la déclaration de L

# # Propagation de la charge entre deux nœuds consécutifs :
# #    Si x[v,w,k] = 1  →  L[w,k] = L[v,k] + demand[w] force l'égalité
# #    Linéarisé avec big-M :
# #      L[w,k] >= L[v,k] + demand[w] - Q[k] * (1 - x[v,w,k])
# #      L[w,k] <= L[v,k] + demand[w] + Q[k] * (1 - x[v,w,k])

# for v in all_nodes:
#     for w in all_nodes:
#         if v != w:
#             for k in vehicles:
#                 prob += (
#                     L[w, k] >= L[v, k] + demand[w] - Q[k] * (1 - x[v, w, k])
#                 )
#                 prob += (
#                     L[w, k] <= L[v, k] + demand[w] + Q[k] * (1 - x[v, w, k])
#                 )

# # Note : on ne fixe PAS L[depot, k] explicitement.
# # L[depot, k] représente la charge à l'ARRIVÉE au dépôt (fin de tournée).
# # En fin de tournée : tout a été livré (charge -) ET tout a été ramassé (charge +)
# # → la charge de retour n'est PAS nécessairement égale au volume de départ.
# # La propagation big-M ci-dessus suffit à garantir la cohérence sur toute la route.
# # La seule contrainte naturelle est L[depot, k] >= 0 (déjà via lowBound) et <= Q[k].


# ############### Solution du problème et affichage des résultats ###############

# prob.solve(pulp.PULP_CBC_CMD(msg=1))
# print("Statut :", pulp.LpStatus[prob.status])


# """
# # ── Contraintes qui définissent W ─────────────────────────────────────────
# for v in nodes:
#     for k in vehicles:
#         # attente livraison : on ne peut pas décharger avant a[(v,"d")]
#         prob += W_d[(v,k)] >= a[(v,"d")] - T[(v,"d"),k]

#         # attente ramasse : on ne peut pas charger avant a[(v,"r")]
#         prob += W_r[(v,k)] >= a[(v,"r")] - T[(v,"r"),k]

# # ── Contraintes de fenêtres (obligatoires pour éviter le "tricher") ───────
# for v in nodes:
#     for k in vehicles:
#         prob += T[(v,"d"),k] >= a[(v,"d")]   # pas avant l'ouverture
#         prob += T[(v,"d"),k] <= b[(v,"d")]   # pas après la deadline livraison
#         prob += T[(v,"r"),k] >= a[(v,"r")]   # pas avant fin concert
#         prob += T[(v,"r"),k] <= b[(v,"r")]   # pas après fermeture ramasse

#         """