"""
Script de debug autonome pour tester les contraintes VRP une par une.
Utilise les mêmes données que tot.py mais sans passer par le serveur.
"""

import pulp
import json
import sys
import os
from datetime import datetime

# ========================================
# DONNÉES DE TEST (copiées depuis preview)
# ========================================

# ✅ Modifiez ces données pour correspondre à votre cas réel
DATA = {
  "lieux": [
    {
      "Id_Lieux": 0,
      "Nom": "Dépôt",
      "Adresse": "Av. Gustave Eiffel, 75007 Paris",
      "lat": 48.8581265,
      "lon": 2.2956641,
      "HeureTot": 480,
      "HeureTard": 1380,
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
    },
    {
      "Id_vehicules": 5,
      "Nom": "ZX-908-QM",
      "Volume_dispo": 45
    }
  ],
  "config": "equilibre"
}

# ========================================
# PARAMÈTRES GLOBAUX
# ========================================

M            = 3000
SERVICE_TIME = 60    # minutes de service par lieu
DEPOT_OPEN   = 480   # 08h00

# ========================================
# UTILITAIRES
# ========================================

def sep(titre=""):
    print("\n" + "=" * 70)
    if titre:
        print(f"  {titre}")
        print("=" * 70)

def ok_nok(status):
    return "✅ FAISABLE" if status == pulp.LpStatusOptimal else "❌ INFAISABLE"

def solve(model, label):
    status = model.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=60))
    print(f"  [{label:45s}] → {ok_nok(status)} ({pulp.LpStatus[status]})")
    return status == pulp.LpStatusOptimal

# ========================================
# PRÉPARATION DES DONNÉES
# ========================================

def prepare_data():
    """Construit nodes, demand, capacity, time_dict, fenêtres temporelles"""

    lieux     = DATA["lieux"]
    vehicules = DATA["vehicules"]
    instrs    = DATA["instruments"]

    volume_map = {i["Nom"]: i["Volume"] for i in instrs}

    nodes     = [l["Id_Lieux"] for l in lieux]
    vehicules_ids = [v["Id_vehicules"] for v in vehicules]
    capacity  = {v["Id_vehicules"]: v["Volume_dispo"] for v in vehicules}

    # Calcul de la demande par lieu
    demand = {}
    for l in lieux:
        instr_str = l.get("Instruments") or ""
        vol = sum(
            volume_map.get(i.strip(), 0)
            for i in instr_str.split(",") if i.strip()
        )
        demand[l["Id_Lieux"]] = vol

    # Distances/temps approximatifs (Haversine simple)
    import math
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) \
            * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        d = 2 * R * math.asin(math.sqrt(a))
        return d, d / 50 * 60  # km, minutes (vitesse 50 km/h)

    time_dict     = {}
    distance_dict = {}
    for li in lieux:
        for lj in lieux:
            i, j = li["Id_Lieux"], lj["Id_Lieux"]
            if i != j:
                d, t = haversine(li["lat"], li["lon"], lj["lat"], lj["lon"])
                time_dict[(i, j)]     = t
                distance_dict[(i, j)] = d

    # Fenêtres temporelles
    tw_early   = {l["Id_Lieux"]: l.get("HeureTot")    for l in lieux}
    tw_late    = {l["Id_Lieux"]: l.get("HeureTard")   for l in lieux}
    concert    = {l["Id_Lieux"]: l.get("HeureConcert") for l in lieux}

    return nodes, vehicules_ids, demand, capacity, time_dict, distance_dict, tw_early, tw_late, concert

# ========================================
# VARIABLES DE BASE
# ========================================

def make_vars(nodes, vehicules):
    x = pulp.LpVariable.dicts(
        "x",
        ((i, j, v) for i in nodes for j in nodes for v in vehicules if i != j),
        cat="Binary"
    )
    y = pulp.LpVariable.dicts("y", vehicules, cat="Binary")
    at = pulp.LpVariable.dicts(
        "at",
        ((j, v) for j in nodes for v in vehicules),
        lowBound=0, cat="Continuous"
    )
    return x, y, at

# ========================================
# TESTS PROGRESSIFS
# ========================================

def run_tests():
    sep("PRÉPARATION DES DONNÉES")
    nodes, vehicules, demand, capacity, time_dict, distance_dict, \
        tw_early, tw_late, concert = prepare_data()

    print(f"\n  Noeuds     : {nodes}")
    print(f"  Véhicules  : {vehicules}")
    print(f"  Demandes   : { {k: round(v,2) for k,v in demand.items()} }")
    print(f"  Capacités  : {capacity}")
    print(f"  Arcs       : {len(time_dict)}")
    print(f"  TW early   : {tw_early}")
    print(f"  TW late    : {tw_late}")
    print(f"  Concert    : {concert}")

    # Vérification préalable
    sep("VÉRIFICATION PRÉALABLE")
    for j in nodes:
        if j != 0:
            dem = demand[j]
            capables = [v for v in vehicules if capacity[v] >= dem]
            nom = next(l["Nom"] for l in DATA["lieux"] if l["Id_Lieux"] == j)
            print(f"  Lieu {j} ({nom}): demande={dem:.2f} m³")
            if capables:
                print(f"    ✅ Véhicules capables : {capables}")
            else:
                print(f"    ❌ AUCUN véhicule capable → infaisable garanti !")

    total_dem = sum(demand[j] for j in nodes if j != 0)
    total_cap = sum(capacity[v] for v in vehicules)
    print(f"\n  Demande totale  : {total_dem:.2f} m³")
    print(f"  Capacité totale : {total_cap:.2f} m³")
    print(f"  {'✅ OK' if total_cap >= total_dem else '❌ INSUFFISANT'}")

    sep("TESTS PROGRESSIFS DES CONTRAINTES")
    results = {}

    # ── ÉTAPE 1 : Desserte seule ────────────────────────────────────────────
    def test1():
        x, y, at = make_vars(nodes, vehicules)
        m = pulp.LpProblem("T1", pulp.LpMinimize)
        m += pulp.lpSum(y[v] for v in vehicules)
        for j in nodes:
            if j != 0:
                m += pulp.lpSum(
                    x[i, j, v] for i in nodes if i != j for v in vehicules
                ) >= 1, f"Desserte_{j}"
        return solve(m, "1. Desserte (>= 1 par lieu)")
    results[1] = test1()

    # ── ÉTAPE 2 : + Capacité ────────────────────────────────────────────────
    def test2():
        x, y, at = make_vars(nodes, vehicules)
        m = pulp.LpProblem("T2", pulp.LpMinimize)
        m += pulp.lpSum(y[v] for v in vehicules)
        for j in nodes:
            if j != 0:
                m += pulp.lpSum(
                    x[i, j, v] for i in nodes if i != j for v in vehicules
                ) >= 1, f"Desserte_{j}"
        for v in vehicules:
            m += pulp.lpSum(
                demand[j] * pulp.lpSum(x[i, j, v] for i in nodes if i != j)
                for j in nodes
            ) <= capacity[v], f"Cap_{v}"
        return solve(m, "2. + Capacité véhicules")
    results[2] = test2()

    # ── ÉTAPE 3 : + Départ/Retour dépôt ─────────────────────────────────────
    def test3():
        x, y, at = make_vars(nodes, vehicules)
        m = pulp.LpProblem("T3", pulp.LpMinimize)
        m += pulp.lpSum(y[v] for v in vehicules)
        for j in nodes:
            if j != 0:
                m += pulp.lpSum(
                    x[i, j, v] for i in nodes if i != j for v in vehicules
                ) >= 1, f"Desserte_{j}"
        for v in vehicules:
            m += pulp.lpSum(
                demand[j] * pulp.lpSum(x[i, j, v] for i in nodes if i != j)
                for j in nodes
            ) <= capacity[v], f"Cap_{v}"
            m += pulp.lpSum(x[0, j, v] for j in nodes if j != 0) == y[v], f"Dep_{v}"
            m += pulp.lpSum(x[i, 0, v] for i in nodes if i != 0) == y[v], f"Ret_{v}"
        return solve(m, "3. + Départ/Retour dépôt")
    results[3] = test3()

    # ── ÉTAPE 4 : + Continuité ───────────────────────────────────────────────
    def test4():
        x, y, at = make_vars(nodes, vehicules)
        m = pulp.LpProblem("T4", pulp.LpMinimize)
        m += pulp.lpSum(y[v] for v in vehicules)
        for j in nodes:
            if j != 0:
                m += pulp.lpSum(
                    x[i, j, v] for i in nodes if i != j for v in vehicules
                ) >= 1, f"Desserte_{j}"
        for v in vehicules:
            m += pulp.lpSum(
                demand[j] * pulp.lpSum(x[i, j, v] for i in nodes if i != j)
                for j in nodes
            ) <= capacity[v], f"Cap_{v}"
            m += pulp.lpSum(x[0, j, v] for j in nodes if j != 0) == y[v], f"Dep_{v}"
            m += pulp.lpSum(x[i, 0, v] for i in nodes if i != 0) == y[v], f"Ret_{v}"
            for j in nodes:
                if j != 0:
                    m += (
                        pulp.lpSum(x[i, j, v] for i in nodes if i != j) ==
                        pulp.lpSum(x[j, k, v] for k in nodes if k != j)
                    ), f"Cont_{j}_{v}"
        return solve(m, "4. + Continuité tournée")
    results[4] = test4()

    # ── ÉTAPE 5 : + Activation y[v] ──────────────────────────────────────────
    def test5():
        x, y, at = make_vars(nodes, vehicules)
        m = pulp.LpProblem("T5", pulp.LpMinimize)
        m += pulp.lpSum(y[v] for v in vehicules)
        for j in nodes:
            if j != 0:
                m += pulp.lpSum(
                    x[i, j, v] for i in nodes if i != j for v in vehicules
                ) >= 1, f"Desserte_{j}"
        for v in vehicules:
            m += pulp.lpSum(
                demand[j] * pulp.lpSum(x[i, j, v] for i in nodes if i != j)
                for j in nodes
            ) <= capacity[v], f"Cap_{v}"
            m += pulp.lpSum(x[0, j, v] for j in nodes if j != 0) == y[v], f"Dep_{v}"
            m += pulp.lpSum(x[i, 0, v] for i in nodes if i != 0) == y[v], f"Ret_{v}"
            for j in nodes:
                if j != 0:
                    m += (
                        pulp.lpSum(x[i, j, v] for i in nodes if i != j) ==
                        pulp.lpSum(x[j, k, v] for k in nodes if k != j)
                    ), f"Cont_{j}_{v}"
            for i in nodes:
                for j in nodes:
                    if i != j:
                        m += x[i, j, v] <= y[v], f"Act_{i}_{j}_{v}"
        return solve(m, "5. + Activation y[v]")
    results[5] = test5()

    # ── ÉTAPE 6 : + Heure départ dépôt ───────────────────────────────────────
    def test6():
        x, y, at = make_vars(nodes, vehicules)
        m = pulp.LpProblem("T6", pulp.LpMinimize)
        m += pulp.lpSum(y[v] for v in vehicules)
        for j in nodes:
            if j != 0:
                m += pulp.lpSum(
                    x[i, j, v] for i in nodes if i != j for v in vehicules
                ) >= 1, f"Desserte_{j}"
        for v in vehicules:
            m += pulp.lpSum(
                demand[j] * pulp.lpSum(x[i, j, v] for i in nodes if i != j)
                for j in nodes
            ) <= capacity[v], f"Cap_{v}"
            m += pulp.lpSum(x[0, j, v] for j in nodes if j != 0) == y[v], f"Dep_{v}"
            m += pulp.lpSum(x[i, 0, v] for i in nodes if i != 0) == y[v], f"Ret_{v}"
            for j in nodes:
                if j != 0:
                    m += (
                        pulp.lpSum(x[i, j, v] for i in nodes if i != j) ==
                        pulp.lpSum(x[j, k, v] for k in nodes if k != j)
                    ), f"Cont_{j}_{v}"
            for i in nodes:
                for j in nodes:
                    if i != j:
                        m += x[i, j, v] <= y[v], f"Act_{i}_{j}_{v}"
            m += at[0, v] >= DEPOT_OPEN * y[v],             f"DepT_{v}"
            m += at[0, v] <= DEPOT_OPEN + M * y[v],         f"DepI_{v}"
        return solve(m, "6. + Heure départ dépôt")
    results[6] = test6()

    # ── ÉTAPE 7 : + Cohérence temporelle ──────────────────────────────────────
    def test7():
        x, y, at = make_vars(nodes, vehicules)
        m = pulp.LpProblem("T7", pulp.LpMinimize)
        m += pulp.lpSum(y[v] for v in vehicules)
        for j in nodes:
            if j != 0:
                m += pulp.lpSum(
                    x[i, j, v] for i in nodes if i != j for v in vehicules
                ) >= 1, f"Desserte_{j}"
        for v in vehicules:
            m += pulp.lpSum(
                demand[j] * pulp.lpSum(x[i, j, v] for i in nodes if i != j)
                for j in nodes
            ) <= capacity[v], f"Cap_{v}"
            m += pulp.lpSum(x[0, j, v] for j in nodes if j != 0) == y[v], f"Dep_{v}"
            m += pulp.lpSum(x[i, 0, v] for i in nodes if i != 0) == y[v], f"Ret_{v}"
            for j in nodes:
                if j != 0:
                    m += (
                        pulp.lpSum(x[i, j, v] for i in nodes if i != j) ==
                        pulp.lpSum(x[j, k, v] for k in nodes if k != j)
                    ), f"Cont_{j}_{v}"
            for i in nodes:
                for j in nodes:
                    if i != j:
                        m += x[i, j, v] <= y[v], f"Act_{i}_{j}_{v}"
            m += at[0, v] >= DEPOT_OPEN * y[v],     f"DepT_{v}"
            m += at[0, v] <= DEPOT_OPEN + M * y[v], f"DepI_{v}"
        c = 0
        for (i, j, v) in x:
            if (i, j) in time_dict:
                svc = SERVICE_TIME if i != 0 else 0
                m += at[j, v] >= at[i, v] + svc + time_dict[i,j] - M*(1-x[i,j,v]), f"Coh_{c}"
                m += at[j, v] <= M * y[v], f"InT_{c}"
                c += 1
        return solve(m, "7. + Cohérence temporelle")
    results[7] = test7()

    # ── ÉTAPE 8 : + TW ouverture ──────────────────────────────────────────────
    def test8():
        x, y, at = make_vars(nodes, vehicules)
        m = pulp.LpProblem("T8", pulp.LpMinimize)
        m += pulp.lpSum(y[v] for v in vehicules)
        for j in nodes:
            if j != 0:
                m += pulp.lpSum(
                    x[i, j, v] for i in nodes if i != j for v in vehicules
                ) >= 1, f"Desserte_{j}"
        for v in vehicules:
            m += pulp.lpSum(
                demand[j] * pulp.lpSum(x[i, j, v] for i in nodes if i != j)
                for j in nodes
            ) <= capacity[v], f"Cap_{v}"
            m += pulp.lpSum(x[0, j, v] for j in nodes if j != 0) == y[v], f"Dep_{v}"
            m += pulp.lpSum(x[i, 0, v] for i in nodes if i != 0) == y[v], f"Ret_{v}"
            for j in nodes:
                if j != 0:
                    m += (
                        pulp.lpSum(x[i, j, v] for i in nodes if i != j) ==
                        pulp.lpSum(x[j, k, v] for k in nodes if k != j)
                    ), f"Cont_{j}_{v}"
            for i in nodes:
                for j in nodes:
                    if i != j:
                        m += x[i, j, v] <= y[v], f"Act_{i}_{j}_{v}"
            m += at[0, v] >= DEPOT_OPEN * y[v],     f"DepT_{v}"
            m += at[0, v] <= DEPOT_OPEN + M * y[v], f"DepI_{v}"
        c = 0
        for (i, j, v) in x:
            if (i, j) in time_dict:
                svc = SERVICE_TIME if i != 0 else 0
                m += at[j, v] >= at[i, v] + svc + time_dict[i,j] - M*(1-x[i,j,v]), f"Coh_{c}"
                m += at[j, v] <= M * y[v], f"InT_{c}"
                c += 1
        for j in nodes:
            if j == 0: continue
            for v in vehicules:
                vis = pulp.lpSum(x[i, j, v] for i in nodes if i != j)
                if tw_early.get(j) is not None:
                    m += at[j, v] >= tw_early[j] * vis, f"TWe_{j}_{v}"
        return solve(m, "8. + TW ouverture (HeureTot)")
    results[8] = test8()

    # ── ÉTAPE 9 : + TW fermeture ──────────────────────────────────────────────
    def test9():
        x, y, at = make_vars(nodes, vehicules)
        m = pulp.LpProblem("T9", pulp.LpMinimize)
        m += pulp.lpSum(y[v] for v in vehicules)
        for j in nodes:
            if j != 0:
                m += pulp.lpSum(
                    x[i, j, v] for i in nodes if i != j for v in vehicules
                ) >= 1, f"Desserte_{j}"
        for v in vehicules:
            m += pulp.lpSum(
                demand[j] * pulp.lpSum(x[i, j, v] for i in nodes if i != j)
                for j in nodes
            ) <= capacity[v], f"Cap_{v}"
            m += pulp.lpSum(x[0, j, v] for j in nodes if j != 0) == y[v], f"Dep_{v}"
            m += pulp.lpSum(x[i, 0, v] for i in nodes if i != 0) == y[v], f"Ret_{v}"
            for j in nodes:
                if j != 0:
                    m += (
                        pulp.lpSum(x[i, j, v] for i in nodes if i != j) ==
                        pulp.lpSum(x[j, k, v] for k in nodes if k != j)
                    ), f"Cont_{j}_{v}"
            for i in nodes:
                for j in nodes:
                    if i != j:
                        m += x[i, j, v] <= y[v], f"Act_{i}_{j}_{v}"
            m += at[0, v] >= DEPOT_OPEN * y[v],     f"DepT_{v}"
            m += at[0, v] <= DEPOT_OPEN + M * y[v], f"DepI_{v}"
        c = 0
        for (i, j, v) in x:
            if (i, j) in time_dict:
                svc = SERVICE_TIME if i != 0 else 0
                m += at[j, v] >= at[i, v] + svc + time_dict[i,j] - M*(1-x[i,j,v]), f"Coh_{c}"
                m += at[j, v] <= M * y[v], f"InT_{c}"
                c += 1
        for j in nodes:
            if j == 0: continue
            for v in vehicules:
                vis = pulp.lpSum(x[i, j, v] for i in nodes if i != j)
                if tw_early.get(j) is not None:
                    m += at[j, v] >= tw_early[j] * vis, f"TWe_{j}_{v}"
                if tw_late.get(j) is not None:
                    m += at[j, v] <= tw_late[j] + M*(1-vis), f"TWl_{j}_{v}"
        return solve(m, "9. + TW fermeture (HeureTard)")
    results[9] = test9()

    # ── ÉTAPE 10 : + Contrainte concert ──────────────────────────────────────
    def test10():
        x, y, at = make_vars(nodes, vehicules)
        m = pulp.LpProblem("T10", pulp.LpMinimize)
        m += pulp.lpSum(y[v] for v in vehicules)
        for j in nodes:
            if j != 0:
                m += pulp.lpSum(
                    x[i, j, v] for i in nodes if i != j for v in vehicules
                ) >= 1, f"Desserte_{j}"
        for v in vehicules:
            m += pulp.lpSum(
                demand[j] * pulp.lpSum(x[i, j, v] for i in nodes if i != j)
                for j in nodes
            ) <= capacity[v], f"Cap_{v}"
            m += pulp.lpSum(x[0, j, v] for j in nodes if j != 0) == y[v], f"Dep_{v}"
            m += pulp.lpSum(x[i, 0, v] for i in nodes if i != 0) == y[v], f"Ret_{v}"
            for j in nodes:
                if j != 0:
                    m += (
                        pulp.lpSum(x[i, j, v] for i in nodes if i != j) ==
                        pulp.lpSum(x[j, k, v] for k in nodes if k != j)
                    ), f"Cont_{j}_{v}"
            for i in nodes:
                for j in nodes:
                    if i != j:
                        m += x[i, j, v] <= y[v], f"Act_{i}_{j}_{v}"
            m += at[0, v] >= DEPOT_OPEN * y[v],     f"DepT_{v}"
            m += at[0, v] <= DEPOT_OPEN + M * y[v], f"DepI_{v}"
        c = 0
        for (i, j, v) in x:
            if (i, j) in time_dict:
                svc = SERVICE_TIME if i != 0 else 0
                m += at[j, v] >= at[i, v] + svc + time_dict[i,j] - M*(1-x[i,j,v]), f"Coh_{c}"
                m += at[j, v] <= M * y[v], f"InT_{c}"
                c += 1
        for j in nodes:
            if j == 0: continue
            for v in vehicules:
                vis = pulp.lpSum(x[i, j, v] for i in nodes if i != j)
                if tw_early.get(j) is not None:
                    m += at[j, v] >= tw_early[j] * vis,      f"TWe_{j}_{v}"
                if tw_late.get(j) is not None:
                    m += at[j, v] <= tw_late[j] + M*(1-vis), f"TWl_{j}_{v}"
                if concert.get(j) is not None:
                    m += at[j, v] <= (concert[j] - SERVICE_TIME) + M*(1-vis), f"TWc_{j}_{v}"
        return solve(m, "10. + Contrainte concert (HeureConcert)")
    results[10] = test10()

    # ── RÉSUMÉ ────────────────────────────────────────────────────────────────
    sep("RÉSUMÉ")
    noms = {
        1: "Desserte",
        2: "Capacité",
        3: "Dépôt départ/retour",
        4: "Continuité tournée",
        5: "Activation y[v]",
        6: "Heure départ dépôt",
        7: "Cohérence temporelle",
        8: "TW ouverture",
        9: "TW fermeture",
        10: "Concert"
    }
    premiere_erreur = None
    for i in range(1, 11):
        statut = "✅" if results[i] else "❌"
        print(f"  {statut} Étape {i:2d} : {noms[i]}")
        if not results[i] and premiere_erreur is None:
            premiere_erreur = i

    print()
    if premiere_erreur:
        print(f"  ⛔ PREMIÈRE CONTRAINTE BLOQUANTE : étape {premiere_erreur} ({noms[premiere_erreur]})")
        print(f"     → Toutes les contraintes APRÈS sont suspectes aussi.")
    else:
        print("  🎉 Toutes les contraintes sont faisables !")
        print("     → Le problème vient peut-être des données OSRM en production.")
    sep()

# ========================================
# POINT D'ENTRÉE
# ========================================

if __name__ == "__main__":
    run_tests()