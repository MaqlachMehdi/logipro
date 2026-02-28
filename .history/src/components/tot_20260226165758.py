# ========================================
# VRP CONCERTS - OPTIMISATION COMPLÈTE
# Avec gestion multi-solutions et visualisations
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
            print(f"⚠️ Solution non optimale ignorée (status: {pulp.LpStatus[model.status]})")
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
            print(f"🏆 Nouvelle meilleure solution ! (Objectif: {objectif:.2f})")
        
        print(f"✅ Solution #{solution['id']} enregistrée")
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
            summary += f"  • Temps total: {sol['temps_total_min']} min ({sol['temps_total_min']/60:.1f}h)\n"
            summary += f"  • Distance totale: {sol['distance_totale_km']} km\n"
            summary += f"  • Objectif: {sol['objectif']:.2f}\n"
            summary += f"  • Poids: véh={sol['weights']['vehicule']}, "
            summary += f"temps={sol['weights']['temps']}, dist={sol['weights']['distance']}\n"
            
            if sol == self.best_solution:
                summary += "  🏆 MEILLEURE SOLUTION\n"
            summary += "\n"
        
        return summary
    
    def compare_table(self):
        """Affiche un tableau comparatif"""
        if not self.solutions:
            print("Aucune solution à comparer")
            return
        
        print("\n" + "="*100)
        print("📊 TABLEAU COMPARATIF DES SOLUTIONS")
        print("="*100)
        print(f"{'ID':<5} {'Label':<20} {'Véh.':<6} {'Temps (min)':<12} {'Distance (km)':<15} {'Objectif':<12} {'Best':<5}")
        print("-"*100)
        
        for sol in self.solutions:
            is_best = "🏆" if sol == self.best_solution else ""
            print(f"{sol['id']:<5} {sol['label']:<20} {sol['nb_vehicules']:<6} "
                  f"{sol['temps_total_min']:<12.1f} {sol['distance_totale_km']:<15.2f} "
                  f"{sol['objectif']:<12.2f} {is_best:<5}")
        
        print("="*100 + "\n")
    
    def plot_temps_vs_vehicules(self):
        """Graphique Temps Total vs Nombre de Véhicules"""
        if not self.solutions:
            print("Aucune solution à visualiser")
            return
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        nb_veh = [sol['nb_vehicules'] for sol in self.solutions]
        temps = [sol['temps_total_min'] for sol in self.solutions]
        labels = [sol['label'] for sol in self.solutions]
        
        colors = ['gold' if sol == self.best_solution else 'steelblue' 
                  for sol in self.solutions]
        
        scatter = ax.scatter(nb_veh, temps, s=200, c=colors, alpha=0.7, edgecolors='black', linewidth=2)
        
        for i, (x, y, label) in enumerate(zip(nb_veh, temps, labels)):
            ax.annotate(label, (x, y), textcoords="offset points", 
                       xytext=(0,10), ha='center', fontsize=9, fontweight='bold')
        
        ax.set_xlabel('Nombre de Véhicules', fontsize=12, fontweight='bold')
        ax.set_ylabel('Temps Total (minutes)', fontsize=12, fontweight='bold')
        ax.set_title('⏱️ Temps Total vs Nombre de Véhicules', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        
        best_patch = plt.Line2D([0], [0], marker='o', color='w', 
                               markerfacecolor='gold', markersize=10, label='Meilleure solution')
        other_patch = plt.Line2D([0], [0], marker='o', color='w', 
                                markerfacecolor='steelblue', markersize=10, label='Autres solutions')
        ax.legend(handles=[best_patch, other_patch])
        
        plt.tight_layout()
        plt.savefig('/mnt/user-data/outputs/temps_vs_vehicules.png', dpi=300, bbox_inches='tight')
        print("📊 Graphique sauvegardé: temps_vs_vehicules.png")
        plt.show()
    
    def plot_radar_chart(self):
        """Radar Chart Multi-Critères"""
        if not self.solutions:
            print("Aucune solution à visualiser")
            return
        
        max_veh = max(sol['nb_vehicules'] for sol in self.solutions)
        max_temps = max(sol['temps_total_min'] for sol in self.solutions)
        max_dist = max(sol['distance_totale_km'] for sol in self.solutions)
        
        categories = ['Économie\nVéhicules', 'Rapidité', 'Distance\nMinimale']
        N = len(categories)
        
        fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))
        
        angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
        angles += angles[:1]
        
        colors = plt.cm.tab10(np.linspace(0, 1, len(self.solutions)))
        
        for idx, sol in enumerate(self.solutions):
            score_veh = 1 - (sol['nb_vehicules'] / max_veh) if max_veh > 0 else 1
            score_temps = 1 - (sol['temps_total_min'] / max_temps) if max_temps > 0 else 1
            score_dist = 1 - (sol['distance_totale_km'] / max_dist) if max_dist > 0 else 1
            
            values = [score_veh, score_temps, score_dist]
            values += values[:1]
            
            linestyle = '-' if sol == self.best_solution else '--'
            linewidth = 3 if sol == self.best_solution else 1.5
            
            ax.plot(angles, values, 'o-', linewidth=linewidth, 
                   label=sol['label'], color=colors[idx], linestyle=linestyle)
            ax.fill(angles, values, alpha=0.15, color=colors[idx])
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, fontsize=11, fontweight='bold')
        ax.set_ylim(0, 1)
        ax.set_yticks([0.25, 0.5, 0.75, 1])
        ax.set_yticklabels(['25%', '50%', '75%', '100%'])
        ax.set_title('🎯 Radar Chart Multi-Critères\n(Plus grand = meilleur)', 
                    fontsize=14, fontweight='bold', pad=20)
        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
        ax.grid(True)
        
        plt.tight_layout()
        plt.savefig('/mnt/user-data/outputs/radar_chart.png', dpi=300, bbox_inches='tight')
        print("📊 Graphique sauvegardé: radar_chart.png")
        plt.show()
    
    def save_to_json(self, filepath):
        """Sauvegarde toutes les solutions en JSON"""
        data = {
            'solutions': self.solutions,
            'best_solution_id': self.best_solution['id'] if self.best_solution else None,
            'export_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Solutions sauvegardées dans {filepath}")

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
        return t
    if hasattr(t, 'hour') and hasattr(t, 'minute'):
        return t.hour * 60 + t.minute
    return None

def geocode(address, retries=3):
    """Géocode une adresse avec retry"""
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

def osrm_time_distance(lat1, lon1, lat2, lon2):
    """Calcule temps et distance via OSRM"""
    url = (
        f"http://router.project-osrm.org/route/v1/driving/"
        f"{lon1},{lat1};{lon2},{lat2}?overview=false"
    )
    r = requests.get(url).json()
    route = r["routes"][0]
    distance_km = route["distance"] / 1000
    duration_min = route["duration"] / 60
    return distance_km, duration_min

def print_solution_details(routes):
    """Affiche les détails d'une solution"""
    for v, info in routes.items():
        print("\n" + "=" * 80)
        print(f"🚚 VÉHICULE : {info['vehicule']}")
        print("=" * 80)
        
        print(f"\n📍 Itinéraire : Dépôt → {' → '.join(info['destinations'])} → Dépôt")
        
        print(f"\n🛣️  DÉTAILS DES TRAJETS :")
        print("-" * 80)
        for seg in info["segments"]:
            print(
                f"  {seg['from']:20s} → {seg['to']:20s} | "
                f"{seg['distance_km']:6.2f} km | {seg['time_min']:6.1f} min"
            )
        
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
        print(f"  • Temps : {info['total_time_min']} min ({info['total_time_min']/60:.1f}h)")

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
# FONCTION POUR DONNÉES JSON
# ========================================

def main_with_json_input(json_data):
    """Reçoit les données en JSON au lieu d'Excel"""
    
    # Convertir JSON en DataFrames
    df_Lieux = pd.DataFrame(json_data['lieux'])
    df_Instruments = pd.DataFrame(json_data['instruments'])
    df_Vehicules = pd.DataFrame(json_data['vehicules'])
    
    df_Lieux = dfs[last_3_sheets[0]]
    df_Instruments = dfs[last_3_sheets[1]]
    df_Vehicules = dfs[last_3_sheets[2]]
    
    print(f"✅ {len(df_Lieux)} lieux chargés")
    print(f"✅ {len(df_Instruments)} instruments chargés")
    print(f"✅ {len(df_Vehicules)} véhicules chargés")
    
    # 2. CALCUL DES VOLUMES
    print("\n📦 Calcul des volumes...")
    volume_map = df_Instruments.set_index("Nom")["Volume"].to_dict()
    
    def calcul_volume(instruments):
        if pd.isna(instruments):
            return 0
        return sum(volume_map.get(instr.strip(), 0) for instr in instruments.split(","))
    
    df_Lieux["Volume_total_instruments"] = df_Lieux["Instruments"].apply(calcul_volume)
    
    # 3. PRÉPARATION DES DONNÉES
    nodes = df_Lieux["Id_Lieux"].tolist()
    demand = dict(zip(df_Lieux["Id_Lieux"], df_Lieux["Volume_total_instruments"]))
    vehicules = df_Vehicules["Id_vehicules"].tolist()
    capacity = dict(zip(df_Vehicules["Id_vehicules"], df_Vehicules["Volume_dispo"]))
    
    # 4. GÉOCODAGE
    print("\n📍 Géocodage des adresses...")
    if 'lat' not in df_Lieux.columns or df_Lieux['lat'].isna().any():
        df_Lieux[["lat", "lon"]] = df_Lieux["Adresse"].apply(
            lambda x: pd.Series(geocode(x)) if pd.notna(x) else pd.Series([None, None])
        )
        print("✅ Géocodage terminé")
    else:
        print("✅ Coordonnées déjà présentes")
    
    # 5. CALCUL DES TEMPS ET DISTANCES
    print("\n⏱️ Calcul des matrices temps/distance...")
    time_dict = {}
    distance_dict = {}
    
    for _, row_i in df_Lieux.iterrows():
        for _, row_j in df_Lieux.iterrows():
            i, j = row_i["Id_Lieux"], row_j["Id_Lieux"]
            if i != j:
                d_km, t_min = osrm_time_distance(
                    row_i["lat"], row_i["lon"],
                    row_j["lat"], row_j["lon"]
                )
                time_dict[(i, j)] = t_min
                distance_dict[(i, j)] = d_km
    
    print(f"✅ {len(time_dict)} trajets calculés")
    
    # 6. PARAMÈTRES TEMPORELS
    print("\n⏰ Configuration temporelle...")
    time_window_early = {}
    time_window_late = {}
    concert_time = {}
    
    for _, row in df_Lieux.iterrows():
        lieu_id = row["Id_Lieux"]
        time_window_early[lieu_id] = time_to_minutes(row.get("HeureTot", None))
        time_window_late[lieu_id] = time_to_minutes(row.get("HeureTard", None))
        concert_time[lieu_id] = time_to_minutes(row.get("HeureConcert", None))
    
    depot_opening = 8 * 60
    time_window_early[0] = depot_opening
    time_window_late[0] = 22 * 60
    concert_time[0] = 24 * 60
    
    # 7. INITIALISATION DU GESTIONNAIRE
    manager = SolutionManager()
    
    # 8. CONFIGURATIONS À TESTER
    configurations = [
        {
            'label': 'Sol #1: Équilibré',
            'weights': {'vehicule': 1000, 'temps': 10, 'distance': 5}
        },
        {
            'label': 'Sol #2: Économie Véhicules',
            'weights': {'vehicule': 5000, 'temps': 5, 'distance': 2}
        },
        {
            'label': 'Sol #3: Rapidité',
            'weights': {'vehicule': 500, 'temps': 50, 'distance': 5}
        },
        {
            'label': 'Sol #4: Distance Min',
            'weights': {'vehicule': 500, 'temps': 5, 'distance': 50}
        }
    ]
    
    # 9. RÉSOLUTION DES DIFFÉRENTES CONFIGURATIONS
    print("\n" + "=" * 80)
    print("🚀 RÉSOLUTION DES CONFIGURATIONS")
    print("=" * 80)
    
    for config in configurations:
        print(f"\n{'='*80}")
        print(f"🎯 {config['label']}")
        print(f"{'='*80}")
        print(f"Poids: véhicule={config['weights']['vehicule']}, "
              f"temps={config['weights']['temps']}, "
              f"distance={config['weights']['distance']}")
        
        model, x, y, arrival_time = create_and_solve_model(
            nodes, vehicules, demand, capacity, time_dict, distance_dict,
            time_window_early, time_window_late, concert_time,
            config['weights']
        )
        
        status = model.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=300))
        
        print(f"\nStatut: {pulp.LpStatus[status]}")
        
        if status == pulp.LpStatusOptimal:
            print(f"✅ Solution optimale trouvée ! (Objectif: {pulp.value(model.objective):.2f})")
            
            routes = extract_routes_full(x, y, nodes, vehicules, df_Lieux, df_Vehicules, 
                                        time_dict, distance_dict)
            
            manager.add_solution(model, routes, config['weights'], config['label'])
            
            # Afficher bref résumé
            print(f"\n📊 Résumé:")
            print(f"  • Véhicules utilisés: {len(routes)}")
            for v, info in routes.items():
                print(f"  • {info['vehicule']}: {len(info['destinations'])} arrêts")
        else:
            print(f"❌ Échec: {pulp.LpStatus[status]}")
    
    # 10. AFFICHAGE DES RÉSULTATS
    if manager.solutions:
        print("\n" + "=" * 80)
        print("📊 ANALYSE COMPARATIVE")
        print("=" * 80)
        
        print(manager.get_summary())
        manager.compare_table()
        
        # Afficher détails de la meilleure solution
        if manager.best_solution:
            print("\n" + "=" * 80)
            print("🏆 DÉTAILS DE LA MEILLEURE SOLUTION")
            print("=" * 80)
            print_solution_details(manager.best_solution['routes'])
        
        # 11. VISUALISATIONS
        print("\n📊 Génération des visualisations...")
        try:
            manager.plot_temps_vs_vehicules()
            manager.plot_radar_chart()
        except Exception as e:
            print(f"⚠️ Erreur lors de la génération des graphiques: {e}")
        
        # 12. SAUVEGARDE
        print("\n💾 Sauvegarde des résultats...")
        manager.save_to_json('/mnt/user-data/outputs/solutions_vrp.json')
        
        print("\n" + "=" * 80)
        print("✅ OPTIMISATION TERMINÉE !")
        print("=" * 80)
        print(f"\n🏆 Meilleure solution: {manager.best_solution['label']}")
        print(f"   • Véhicules: {manager.best_solution['nb_vehicules']}")
        print(f"   • Temps total: {manager.best_solution['temps_total_min']} min")
        print(f"   • Distance totale: {manager.best_solution['distance_totale_km']} km")
        print(f"   • Objectif: {manager.best_solution['objectif']:.2f}")
    
    else:
        print("\n❌ Aucune solution optimale trouvée")
        print("\n💡 Suggestions:")
        print("  1. Vérifiez la capacité des véhicules vs demande totale")
        print("  2. Relâchez les contraintes temporelles")
        print("  3. Ajoutez plus de véhicules")

# ========================================
# POINT D'ENTRÉE
# ========================================

if __name__ == "__main__":
    main()
    