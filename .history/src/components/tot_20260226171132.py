# ========================================
# VRP CONCERTS - OPTIMISATION COMPLÈTE
# Avec gestion multi-solutions et visualisations
# Adaptée pour recevoir les données en JSON via stdin
# ========================================

import pandas as pd
import pulp
import time as time_module
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
import requests
from collections import Counter
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import json
import sys

# ========================================
# CLASSE DE GESTION DES SOLUTIONS
# ========================================

class SolutionManager:
    """Gestionnaire pour stocker et comparer plusieurs solutions VRP"""
    
    def __init__(self):
        self.solutions = []
        self.best_solution = None
    
    def add_solution(self, model, routes, weights, label=None):
        """Ajoute une solution à l'historique"""
        if model.status != pulp.LpStatusOptimal:
            return None
        
        # Calculer les métriques
        nb_vehicules = len(routes)
        temps_total = sum(info['total_time_min'] for info in routes.values())
        distance_totale = sum(info['total_distance_km'] for info in routes.values())
        objectif = pulp.value(model.objective)
        
        solution = {
            'id': len(self.solutions) + 1,
            'label': label or f"Solution #{len(self.solutions) + 1}",
            'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'nb_vehicules': nb_vehicules,
            'temps_total_min': round(temps_total, 1),
            'distance_totale_km': round(distance_totale, 2),
            'objectif': round(objectif, 2),
            'weights': weights.copy(),
            'routes': routes,
            'details_vehicules': [
                {
                    'nom': info['vehicule'],
                    'destinations': info['destinations'],
                    'temps_min': info['total_time_min'],
                    'distance_km': info['total_distance_km']
                }
                for info in routes.values()
            ]
        }
        
        self.solutions.append(solution)
        
        # Mettre à jour la meilleure solution
        if self.best_solution is None or objectif < self.best_solution['objectif']:
            self.best_solution = solution
        
        return solution
    
    def get_summary(self):
        """Retourne un résumé de toutes les solutions"""
        if not self.solutions:
            return "Aucune solution enregistrée"
        
        summary = "\n" + "="*80 + "\n"
        summary += "📊 RÉSUMÉ DES SOLUTIONS\n"
        summary += "="*80 + "\n\n"
        
        for sol in self.solutions:
            summary += f"Solution {sol['id']}: {sol['label']}\n"
            summary += f"  • Véhicules: {sol['nb_vehicules']}\n"
            summary += f"  • Temps total: {sol['temps_total_min']} min\n"
            summary += f"  • Distance totale: {sol['distance_totale_km']} km\n"
            summary += f"  • Objectif: {sol['objectif']:.2f}\n\n"
        
        return summary

# ========================================
# FONCTION D'EXTRACTION DES ROUTES
# ========================================

def extract_routes_full(x, y, nodes, vehicules, df_Lieux, df_Vehicules, time_dict, distance_dict):
    """Retourne les routes par véhicule avec tous les détails"""
    
    lieu_name = dict(zip(df_Lieux["Id_Lieux"], df_Lieux["Nom"]))
    lieu_instr = dict(zip(df_Lieux["Id_Lieux"], df_Lieux["Instruments"]))
    vehicule_name = dict(zip(df_Vehicules["Id_vehicules"], df_Vehicules["Nom"]))
    
    routes = {}
    
    for v in vehicules:
        if y[v].value() == 1:
            arcs = [(i, j) for (i, j, vv) in x if vv == v and x[i, j, v].value() == 1]
            
            route = [0]
            current = 0
            while True:
                next_nodes = [j for (i, j) in arcs if i == current]
                if not next_nodes:
                    break
                current = next_nodes[0]
                route.append(current)
                if current == 0:
                    break
            
            destinations = [lieu_name[i] for i in route if i != 0]
            
            instruments_par_lieu = {}
            for i in route:
                if i != 0 and pd.notna(lieu_instr[i]):
                    lieu_counter = Counter(
                        instr.strip()
                        for instr in lieu_instr[i].split(",")
                    )
                    instruments_par_lieu[lieu_name[i]] = dict(lieu_counter)
            
            instrument_counter = Counter()
            for i in route:
                if i != 0 and pd.notna(lieu_instr[i]):
                    instrument_counter.update(
                        instr.strip()
                        for instr in lieu_instr[i].split(",")
                    )
            
            segments = []
            total_time = 0
            total_distance = 0
            
            for k in range(len(route) - 1):
                i, j = route[k], route[k + 1]
                t = time_dict.get((i, j), 0)
                d = distance_dict.get((i, j), 0)
                
                segments.append({
                    "from": lieu_name[i],
                    "to": lieu_name[j],
                    "time_min": round(t, 1),
                    "distance_km": round(d, 2)
                })
                
                total_time += t
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
# FONCTIONS UTILITAIRES
# ========================================

def time_to_minutes(t):
    """Convertit un temps en minutes depuis minuit"""
    if pd.isna(t):
        return None
    if isinstance(t, (int, float)):
        return int(t)
    if hasattr(t, 'hour') and hasattr(t, 'minute'):
        return t.hour * 60 + t.minute
    return None

def osrm_time_distance(lat1, lon1, lat2, lon2):
    """Calcule temps et distance via OSRM"""
    try:
        url = (
            f"http://router.project-osrm.org/route/v1/driving/"
            f"{lon1},{lat1};{lon2},{lat2}?overview=false"
        )
        r = requests.get(url, timeout=5).json()
        route = r["routes"][0]
        distance_km = route["distance"] / 1000
        duration_min = route["duration"] / 60
        return distance_km, duration_min
    except Exception as e:
        # Calcul approximatif en cas d'erreur
        return 50, 50

def create_and_solve_model(nodes, vehicules, demand, capacity, time_dict, distance_dict,
                           time_window_early, time_window_late, concert_time,
                           weights, depot_opening=480, service_time=60, M=1600):
    """Crée et résout un modèle VRP avec les poids donnés"""
    
    # Créer les variables
    x = pulp.LpVariable.dicts(
        "x",
        ((i, j, v) for i in nodes for j in nodes for v in vehicules if i != j),
        cat="Binary"
    )
    
    y = pulp.LpVariable.dicts(
        "y",
        vehicules,
        cat="Binary"
    )
    
    arrival_time = pulp.LpVariable.dicts(
        "arrival_time",
        ((j, v) for j in nodes for v in vehicules),
        lowBound=0,
        cat="Continuous"
    )
    
    # Créer le modèle
    model = pulp.LpProblem("VRP_Concerts", pulp.LpMinimize)
    
    # Fonction objectif
    model += (
        weights['vehicule'] * pulp.lpSum(y[v] for v in vehicules)
        + weights['temps'] * pulp.lpSum(
            time_dict[i, j] * x[i, j, v]
            for (i, j) in time_dict
            for v in vehicules
        )
        + weights['distance'] * pulp.lpSum(
            distance_dict[i, j] * x[i, j, v]
            for (i, j) in distance_dict
            for v in vehicules
        )
    )
    
    # Contraintes: chaque lieu desservi une fois
    for j in nodes:
        if j != 0:
            model += pulp.lpSum(
                x[i,j,v]
                for i in nodes if i != j
                for v in vehicules
            ) == 1, f"Desserte_{j}"
    
    # Contraintes: capacité des véhicules
    for v in vehicules:
        model += pulp.lpSum(
            demand[j] * pulp.lpSum(x[i,j,v] for i in nodes if i != j)
            for j in nodes
        ) <= capacity[v], f"Capacite_{v}"
    
    # Contraintes: départ et retour au dépôt
    for v in vehicules:
        model += pulp.lpSum(x[0,j,v] for j in nodes if j != 0) == y[v], f"Depart_depot_{v}"
        model += pulp.lpSum(x[i,0,v] for i in nodes if i != 0) == y[v], f"Retour_depot_{v}"
    
    # Contraintes: continuité de la tournée
    for v in vehicules:
        for j in nodes:
            if j != 0:
                model += (
                    pulp.lpSum(x[i,j,v] for i in nodes if i != j) ==
                    pulp.lpSum(x[j,k,v] for k in nodes if k != j)
                ), f"Continuite_{j}_{v}"
    
    # Contraintes: activation du véhicule
    for v in vehicules:
        for i in nodes:
            for j in nodes:
                if i != j:
                    model += x[i,j,v] <= y[v], f"Activation_{i}_{j}_{v}"
    
    # Contraintes temporelles
    for v in vehicules:
        model += arrival_time[0, v] >= depot_opening * y[v], f"Depart_temps_{v}"
    
    # Fenêtre horaire - arrivée trop tôt
    for j in nodes:
        if j != 0 and time_window_early[j] is not None:
            for v in vehicules:
                visit = pulp.lpSum(x[i, j, v] for i in nodes if i != j)
                model += (
                    arrival_time[j, v] >= time_window_early[j] - M * (1 - visit)
                ), f"Fenetre_early_{j}_{v}"
    
    # Arriver avant le concert
    for j in nodes:
        if j != 0 and concert_time[j] is not None:
            for v in vehicules:
                visit = pulp.lpSum(x[i, j, v] for i in nodes if i != j)
                model += (
                    arrival_time[j, v] + service_time <= concert_time[j] + M * (1 - visit)
                ), f"Avant_concert_{j}_{v}"
    
    # Cohérence temporelle
    for i in nodes:
        for j in nodes:
            if i != j and (i, j) in time_dict:
                travel_time = time_dict[(i, j)]
                for v in vehicules:
                    service = service_time if i != 0 else 0
                    model += arrival_time[j, v] >= (
                        arrival_time[i, v] + service + travel_time - M * (1 - x[i, j, v])
                    ), f"Coherence_{i}_{j}_{v}"
    
    return model, x, y, arrival_time

# ========================================
# PROGRAMME PRINCIPAL AVEC JSON
# ========================================

def main_json():
    """Reçoit les données en JSON via stdin"""
    
    try:
        # Lire les données JSON depuis stdin
        json_input = sys.stdin.read()
        data = json.loads(json_input)
        
        # Convertir JSON en DataFrames
        df_Lieux = pd.DataFrame(data['lieux'])
        df_Instruments = pd.DataFrame(data['instruments'])
        df_Vehicules = pd.DataFrame(data['vehicules'])
        
        # Récupérer la configuration demandée
        selected_config = data.get('config', 'equilibre')
        
        # 1. CALCUL DES VOLUMES
        volume_map = df_Instruments.set_index("Nom")["Volume"].to_dict()
        
        def calcul_volume(instruments):
            if pd.isna(instruments) or instruments == "":
                return 0
            return sum(volume_map.get(instr.strip(), 0) for instr in str(instruments).split(","))
        
        df_Lieux["Volume_total_instruments"] = df_Lieux["Instruments"].apply(calcul_volume)
        
        # 2. PRÉPARATION DES DONNÉES
        nodes = df_Lieux["Id_Lieux"].tolist()
        demand = dict(zip(df_Lieux["Id_Lieux"], df_Lieux["Volume_total_instruments"]))
        vehicules = df_Vehicules["Id_vehicules"].tolist()
        capacity = dict(zip(df_Vehicules["Id_vehicules"], df_Vehicules["Volume_dispo"]))
        
        # 3. CALCUL DES TEMPS ET DISTANCES
        time_dict = {}
        distance_dict = {}
        
        for _, row_i in df_Lieux.iterrows():
            for _, row_j in df_Lieux.iterrows():
                i, j = row_i["Id_Lieux"], row_j["Id_Lieux"]
                if i != j:
                    try:
                        d_km, t_min = osrm_time_distance(
                            row_i["lat"], row_i["lon"],
                            row_j["lat"], row_j["lon"]
                        )
                        time_dict[(i, j)] = t_min
                        distance_dict[(i, j)] = d_km
                    except:
                        time_dict[(i, j)] = 30
                        distance_dict[(i, j)] = 30
        
        # 4. PARAMÈTRES TEMPORELS
        time_window_early = {}
        time_window_late = {}
        concert_time = {}
        
        for _, row in df_Lieux.iterrows():
            lieu_id = row["Id_Lieux"]
            time_window_early[lieu_id] = time_to_minutes(row.get("HeureTot"))
            time_window_late[lieu_id] = time_to_minutes(row.get("HeureTard"))
            concert_time[lieu_id] = time_to_minutes(row.get("HeureConcert"))
        
        depot_opening = 8 * 60
        time_window_early[0] = depot_opening
        time_window_late[0] = 22 * 60
        concert_time[0] = 24 * 60
        
        # 5. CONFIGURATIONS DISPONIBLES
        configurations = {
            'equilibre': {
                'label': 'Équilibré',
                'weights': {'vehicule': 1000, 'temps': 10, 'distance': 5}
            },
            'economie': {
                'label': 'Économie Véhicules',
                'weights': {'vehicule': 5000, 'temps': 5, 'distance': 2}
            },
            'rapidite': {
                'label': 'Rapidité',
                'weights': {'vehicule': 500, 'temps': 50, 'distance': 5}
            },
            'distance': {
                'label': 'Distance Min',
                'weights': {'vehicule': 500, 'temps': 5, 'distance': 50}
            }
        }
        
        # 6. RÉSOUDRE LA CONFIGURATION SÉLECTIONNÉE
        if selected_config not in configurations:
            selected_config = 'equilibre'
        
        config = configurations[selected_config]
        
        model, x, y, arrival_time = create_and_solve_model(
            nodes, vehicules, demand, capacity, time_dict, distance_dict,
            time_window_early, time_window_late, concert_time,
            config['weights']
        )
        
        status = model.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=300))
        
        # 7. TRAITER LE RÉSULTAT
        if status == pulp.LpStatusOptimal:
            routes = extract_routes_full(x, y, nodes, vehicules, df_Lieux, df_Vehicules, 
                                        time_dict, distance_dict)
            
            # Construire la solution
            nb_vehicules = len(routes)
            temps_total = sum(info['total_time_min'] for info in routes.values())
            distance_totale = sum(info['total_distance_km'] for info in routes.values())
            objectif = pulp.value(model.objective)
            
            solution = {
                'id': 1,
                'label': config['label'],
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'nb_vehicules': nb_vehicules,
                'temps_total_min': round(temps_total, 1),
                'distance_totale_km': round(distance_totale, 2),
                'objectif': round(objectif, 2),
                'weights': config['weights'].copy(),
                'routes': routes,
                'details_vehicules': [
                    {
                        'nom': info['vehicule'],
                        'destinations': info['destinations'],
                        'temps_min': info['total_time_min'],
                        'distance_km': info['total_distance_km']
                    }
                    for info in routes.values()
                ]
            }
            
            result = {
                'success': True,
                'solution': solution
            }
        else:
            result = {
                'success': False,
                'error': f'Impossible de trouver une solution optimale (statut: {pulp.LpStatus[status]})'
            }
        
        # 8. RETOURNER LE RÉSULTAT EN JSON
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    except Exception as e:
        result = {
            'success': False,
            'error': str(e)
        }
        print(json.dumps(result, indent=2))
        sys.exit(1)

# ========================================
# POINT D'ENTRÉE
# ========================================

if __name__ == "__main__":
    main_json()
