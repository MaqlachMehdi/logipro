import hashlib
import json
import os
import pickle
import time as time_module
from dataclasses import dataclass
from time import time_ns

import pulp
import requests
from tqdm import tqdm

# ──────────────────────────────────────────────────────────────────────────────
# Global flags / solver constants
# ──────────────────────────────────────────────────────────────────────────────

DEBUG          = 0
RECALL_MAP_API = 0   # set to 1 to force fresh API calls and overwrite the cache

# Safety margins (minutes)
MARGIN_BEFORE_CONCERT  = 15   # buffer before concert start
MARGIN_AFTER_CONCERT   = 20   # possible concert delay
MARGIN_BEFORE_CLOSING  = 30   # cannot arrive too close to closing time

# ──────────────────────────────────────────────────────────────────────────────
# Data-classes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class LossParams:
    alpha_time:     float
    alpha_distance: float


@dataclass
class OrientedEdges:
    distances_km:      dict  # (node_id_from, node_id_to) -> float
    travel_times_min:  dict  # (node_id_from, node_id_to) -> float

    def __str__(self):
        lines = ["===  DISTANCE"]
        for (i, j), d in self.distances_km.items():
            lines.append(f"({i} --> {j}) : {d:.2f} km")
        lines.append("===  TRAVEL TIME")
        for (i, j), d in self.travel_times_min.items():
            lines.append(f"({i} --> {j}) : {d:.0f} min")
        return "\n".join(lines)


@dataclass
class TimeWindow:
    start_minutes: int
    end_minutes:   int

    def __post_init__(self):
        if self.start_minutes < 0 or self.end_minutes < self.start_minutes:
            raise ValueError(
                f"Invalid time window: {self.start_minutes} -> {self.end_minutes}"
            )

    def __str__(self):
        return f"TimeWindow: {self.start_minutes} min - {self.end_minutes} min"


@dataclass
class Vehicle:
    id:         str
    max_volume: float

    def __post_init__(self):
        if self.max_volume <= 0:
            raise ValueError(
                f"Vehicle {self.id} has non-positive volume ({self.max_volume} m³)"
            )

    def __str__(self):
        return f"Vehicle: {self.id} (max {self.max_volume} m³)"


@dataclass
class Node:
    id:               int
    required_volume:  float       | None = None
    time_window:      TimeWindow  | None = None
    gps_coordinates:  tuple       | None = None  # (lat, lon)


class DepositNode(Node):
    def __init__(self, id):
        super().__init__(id)

    def __str__(self):
        return f"Deposit node #{self.id}"
    
    def get_id_for_pulp(self)->str:
        return f"{self.id}"

class DeliveryNode(Node):
    def __init__(self, id):
        super().__init__(id)

    def __str__(self):
        return f"Delivery node #{self.id}  vol={self.required_volume}"

    def health_check(self):
        if self.required_volume is not None and self.required_volume < 0:
            raise ValueError("Delivery node has negative volume.")
        if self.gps_coordinates is not None and len(self.gps_coordinates) != 2:
            raise ValueError(
                f"GPS coordinates length {len(self.gps_coordinates)}, expected 2."
            )
    def get_id_for_pulp(self)->str:
        return f"{self.id}-D"


class RecoveryNode(Node):
    def __init__(self, id):
        super().__init__(id)

    def __str__(self):
        return f"Recovery node #{self.id}  vol={self.required_volume}"

    def health_check(self):
        if self.required_volume is not None and self.required_volume > 0:
            raise ValueError("Recovery node has positive volume.")
        
    def get_id_for_pulp(self)->str:
        return f"{self.id}-R"


@dataclass
class Problem:
    name:            str
    deposit_node:    DepositNode
    delivery_nodes:  list[DeliveryNode]
    recovery_nodes:  list[RecoveryNode]
    oriented_edges:  OrientedEdges
    vehicles_dict:   dict          # plate -> Vehicle
    loss_params:     LossParams

    def health_check(self):
        if len(self.delivery_nodes) != len(self.recovery_nodes):
            raise ValueError("Mismatch between delivery and recovery node counts.")
        for d, r in zip(self.delivery_nodes, self.recovery_nodes):
            if not isinstance(d, DeliveryNode):
                raise TypeError(f"Expected DeliveryNode, got {type(d)}")
            if not isinstance(r, RecoveryNode):
                raise TypeError(f"Expected RecoveryNode, got {type(r)}")

    def __post_init__(self):
        self.number_of_locations = len(self.delivery_nodes)
        self.health_check()

    @property
    def n_of_nodes(self) -> int:
        return 2 * self.number_of_locations + 1

    @property
    def all_nodes(self) -> list:
        return [self.deposit_node] + self.delivery_nodes + self.recovery_nodes

    def __str__(self) -> str:
        def hhmm(m: int) -> str:
            return f"{int(m)//60:02d}h{int(m)%60:02d}"

        sep  = "─" * 60
        lines = [
            sep,
            f"  PROBLEM : {self.name}",
            f"  Loss    : α_time={self.loss_params.alpha_time}  α_dist={self.loss_params.alpha_distance}",
            f"  Nodes   : {self.n_of_nodes}  ({self.number_of_locations} venues × 2 + depot)",
            f"  Vehicles: {len(self.vehicles_dict)}",
            sep,
        ]

        # ── Depot ──────────────────────────────────────────────────────────
        d = self.deposit_node
        tw = d.time_window
        lines += [
            "DEPOT",
            f"  id={d.id}  GPS={d.gps_coordinates}",
            f"  TW : [{tw.start_minutes}, {tw.end_minutes}]  "
            f"({hhmm(tw.start_minutes)} – {hhmm(tw.end_minutes)})" if tw else "  TW : None",
        ]

        # ── Delivery nodes ─────────────────────────────────────────────────
        lines += ["", "DELIVERY NODES (drop-off before concert)"]
        for node in self.delivery_nodes:
            tw  = node.time_window
            tw_s = (f"[{tw.start_minutes}, {tw.end_minutes}]  "
                    f"({hhmm(tw.start_minutes)} – {hhmm(tw.end_minutes)})"
                    if tw else "None")
            lines.append(
                f"  DeliveryNode id={node.id:>3}  "
                f"vol={node.required_volume:+.3f} m³  "
                f"GPS={node.gps_coordinates}  TW={tw_s}"
            )

        # ── Recovery nodes ─────────────────────────────────────────────────
        lines += ["", "RECOVERY NODES (pick-up after concert)"]
        for node in self.recovery_nodes:
            tw  = node.time_window
            tw_s = (f"[{tw.start_minutes}, {tw.end_minutes}]  "
                    f"({hhmm(tw.start_minutes)} – {hhmm(tw.end_minutes)})"
                    if tw else "None")
            lines.append(
                f"  RecoveryNode id={node.id:>3}  "
                f"vol={node.required_volume:+.3f} m³  "
                f"GPS={node.gps_coordinates}  TW={tw_s}"
            )

        # ── Vehicles ───────────────────────────────────────────────────────
        lines += ["", "VEHICLES"]
        for v in self.vehicles_dict.values():
            lines.append(f"  {v}")

        # ── Node-ID uniqueness check (critical for choose_edges keys) ──────
        lines += ["", "NODE-ID UNIQUENESS CHECK"]
        from collections import Counter
        id_counts = Counter(n.id for n in self.all_nodes)
        duplicates = {i: c for i, c in id_counts.items() if c > 1}
        if duplicates:
            lines.append("  *** WARNING: duplicate node IDs detected! ***")
            lines.append("  Delivery and Recovery nodes sharing the same id will")
            lines.append("  collapse to the SAME choose_edges variable — constraints")
            lines.append("  will reference the wrong edges.")
            for nid, count in duplicates.items():
                node_objs = [type(n).__name__ for n in self.all_nodes if n.id == nid]
                lines.append(f"    id={nid}  appears {count}× → {node_objs}")
        else:
            lines.append("  OK — all node IDs are unique")

        # ── Oriented edges summary ─────────────────────────────────────────
        lines += ["", "ORIENTED EDGES (distance km / travel time min)"]
        all_ids = sorted(set(i for i, _ in self.oriented_edges.distances_km))
        for i in all_ids:
            for j in all_ids:
                key = (i, j)
                if key in self.oriented_edges.distances_km:
                    d_km = self.oriented_edges.distances_km[key]
                    t_min = self.oriented_edges.travel_times_min.get(key, float("nan"))
                    lines.append(
                        f"  ({i:>3} → {j:>3})  {d_km:6.2f} km  {t_min:5.1f} min"
                    )

        # ── Time-window feasibility check ──────────────────────────────────
        lines += ["", "TIME-WINDOW FEASIBILITY"]
        for d_node, r_node in zip(self.delivery_nodes, self.recovery_nodes):
            d_tw = d_node.time_window
            r_tw = r_node.time_window
            ok_d = d_tw and d_tw.end_minutes > d_tw.start_minutes
            ok_r = r_tw and r_tw.end_minutes > r_tw.start_minutes
            lines.append(
                f"  venue id={d_node.id}  "
                f"delivery=[{d_tw.start_minutes},{d_tw.end_minutes}] {'OK' if ok_d else '*** INVALID ***'}  "
                f"recovery=[{r_tw.start_minutes},{r_tw.end_minutes}] {'OK' if ok_r else '*** INVALID ***'}"
            )

        # ── Volume vs vehicle capacity ─────────────────────────────────────
        lines += ["", "VOLUME vs VEHICLE CAPACITY"]
        total_vol = sum(
            abs(n.required_volume)
            for n in self.delivery_nodes
            if n.required_volume is not None
        )
        max_cap   = max(v.max_volume for v in self.vehicles_dict.values())
        total_cap = sum(v.max_volume for v in self.vehicles_dict.values())
        lines.append(f"  Total instrument volume : {total_vol:.3f} m³")
        lines.append(f"  Largest vehicle cap     : {max_cap:.1f} m³")
        lines.append(f"  Combined fleet cap      : {total_cap:.1f} m³")
        if total_vol > total_cap:
            lines.append("  *** WARNING: total volume exceeds fleet capacity — problem is infeasible ***")
        else:
            lines.append("  OK — fleet capacity sufficient")

        lines.append(sep)
        return "\n".join(lines)

@dataclass 
class Trajectory:
    vehicle_id: str
    node_sequence: list[Node]  # list of node ids in visit order
    arrival_times: list[int]  # corresponding arrival times (minutes)
    load_at_arrival: list[float]  # corresponding load upon arrival (m³)

    def health_check(self):
        if not self.node_sequence:
            raise ValueError("Node sequence is empty.")
        if not self.arrival_times:
            raise ValueError("Arrival times are empty.")
        if not self.load_at_arrival:
            raise ValueError("Load at arrival is empty.")
        if (
            len(self.node_sequence) != len(self.arrival_times)
            or len(self.node_sequence) != len(self.load_at_arrival)
        ):
            raise ValueError("Inconsistent lengths of trajectory lists.")
        
    def __post_init__(self):
        self.health_check()

@dataclass
class Result : 
  data : dict[str,Trajectory] 
  problem: Problem 
  pulp_problem: pulp.LpProblem

  def __post_init__(self):
      if not self.data:
          raise ValueError("Result data is empty.")

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


def make_oriented_edges(
    recovery_nodes:  list[RecoveryNode],
    delivery_nodes:  list[DeliveryNode],
    deposit_node:    DepositNode,
) -> OrientedEdges:
    distances    = {}
    travel_times = {}

    distances[(deposit_node.id, deposit_node.id)]    = 0.0
    travel_times[(deposit_node.id, deposit_node.id)] = 0.0

    print("Fetching geo data from OSRM...")
    total_geo_ns = 0
    total_edges  = 0

    for node1 in tqdm(recovery_nodes):
        lat1, lon1 = node1.gps_coordinates
        dlat, dlon = deposit_node.gps_coordinates

        dist_to_depot,   time_to_depot   = osrm_time_distance(lat1, lon1, dlat, dlon)
        dist_from_depot, time_from_depot = osrm_time_distance(dlat, dlon, lat1, lon1)

        distances[(node1.id, deposit_node.id)]    = dist_to_depot
        travel_times[(node1.id, deposit_node.id)] = time_to_depot
        distances[(deposit_node.id, node1.id)]    = dist_from_depot
        travel_times[(deposit_node.id, node1.id)] = time_from_depot
        total_edges += 2

        for node2 in delivery_nodes:
            print(f"Buidling edge : {node1.id}-->{node2.id}")
            lat2, lon2 = node2.gps_coordinates
            t0 = time_ns()
            dist, time = osrm_time_distance(lat1, lon1, lat2, lon2)
            total_geo_ns += time_ns() - t0
            distances[(node1.id, node2.id)]    = dist
            travel_times[(node1.id, node2.id)] = time
            total_edges += 1

    if total_edges:
        print(f"Avg OSRM latency: {total_geo_ns / total_edges / 1_000_000:.1f} ms")

    return OrientedEdges(distances_km=distances, travel_times_min=travel_times)


def _edges_cache_path(all_nodes: list) -> str:
    """Return a deterministic .bin path based on the coordinates of all nodes."""
    coords = sorted(
        (n.gps_coordinates[0], n.gps_coordinates[1])
        for n in all_nodes
        if n.gps_coordinates is not None
    )
    key = str(coords).encode()
    h   = hashlib.md5(key).hexdigest()
    return os.path.join(os.path.dirname(__file__), f"oriented_edges_{h}.bin")


def make_oriented_edges_cached(
    recovery_nodes:  list,
    delivery_nodes:  list,
    deposit_node:    DepositNode,
) -> OrientedEdges:
    all_nodes  = [deposit_node] + delivery_nodes + recovery_nodes
    cache_path = _edges_cache_path(all_nodes)

    if RECALL_MAP_API == 0 and os.path.exists(cache_path):
        print(f"Loading oriented edges from cache: {cache_path}")
        with open(cache_path, "rb") as f:
            return pickle.load(f)

    edges = make_oriented_edges(recovery_nodes, delivery_nodes, deposit_node)

    with open(cache_path, "wb") as f:
        pickle.dump(edges, f)
    print(f"Oriented edges cached to: {cache_path}")

    return edges


# ──────────────────────────────────────────────────────────────────────────────
# Problem builder
# ──────────────────────────────────────────────────────────────────────────────

def _compute_location_volume(location: dict, vol_lookup: dict) -> float:
    """Sum the volume of all instruments listed for a location."""
    raw = location.get("instruments", "")
    items = [s.strip() for s in raw.split(",") if s.strip()]
    return sum(vol_lookup.get(item, 0.0) for item in items)


def build_problem(data: dict, loss_params: LossParams) -> Problem:
    """
    Build a Problem from a data dict matching the vrppd_data.json schema.

    Parameters
    ----------
    data        : dict loaded from vrppd_data.json
    loss_params : optional
    """


    # --- instrument volume lookup -------------------------------------------
    vol_lookup = {
        inst["name"]: inst["volume_m3"]
        for inst in data["instrument_catalog"]
    }

    # --- split depot vs. venue locations ------------------------------------
    depot_data = next(loc for loc in data["locations"] if loc["id"] == 0)
    venue_data = [loc for loc in data["locations"] if loc["id"] != 0]
    venue_ids  = [loc["id"] for loc in venue_data]

    # --- depot node ---------------------------------------------------------
    deposit_node = DepositNode(depot_data["id"])
    deposit_node.gps_coordinates = (depot_data["lat"], depot_data["lon"])
    deposit_node.time_window = TimeWindow(
        start_minutes=depot_data["open_time_min"],
        end_minutes=depot_data["close_time_min"],
    )

    # --- delivery + recovery nodes ------------------------------------------
    delivery_nodes = [DeliveryNode(vid) for vid in venue_ids]
    recovery_nodes = [RecoveryNode(vid) for vid in venue_ids]

    for loc, delivery_node, recovery_node in zip(venue_data, delivery_nodes, recovery_nodes):
        assert delivery_node.id == recovery_node.id == loc["id"]

        venue_volume = _compute_location_volume(loc, vol_lookup)
        delivery_node.required_volume = +venue_volume
        recovery_node.required_volume = -venue_volume

        concert_start  = loc["concert_start_min"]
        open_time      = loc["open_time_min"]
        close_time     = loc["close_time_min"]
        setup_time     = loc["setup_duration_min"]
        teardown_time  = loc["teardown_duration_min"]
        concert_dur    = loc["concert_duration_min"]
        coords         = (loc["lat"], loc["lon"])

        delivery_node.time_window = TimeWindow(
            start_minutes=open_time,
            end_minutes=concert_start - setup_time - MARGIN_BEFORE_CONCERT,
        )
        recovery_node.time_window = TimeWindow(
            start_minutes=concert_start + concert_dur + MARGIN_AFTER_CONCERT,
            end_minutes=close_time - teardown_time - MARGIN_BEFORE_CLOSING,
        )

        delivery_node.gps_coordinates = coords
        recovery_node.gps_coordinates = coords

        delivery_node.health_check()
        recovery_node.health_check()

    # --- oriented edges (with caching) --------------------------------------
    oriented_edges = make_oriented_edges_cached(
        recovery_nodes, delivery_nodes, deposit_node
    )

    # --- vehicles -----------------------------------------------------------
    vehicles_dict: dict[str, Vehicle] = {}
    for v in data["vehicles"]:
        vehicles_dict[v["plate"]] = Vehicle(id=v["plate"], max_volume=v["capacity_m3"])

    return Problem(
        name="VRPPD Concerts",
        deposit_node=deposit_node,
        delivery_nodes=delivery_nodes,
        recovery_nodes=recovery_nodes,
        oriented_edges=oriented_edges,
        vehicles_dict=vehicles_dict,
        loss_params=loss_params,
    )


# ──────────────────────────────────────────────────────────────────────────────
# PuLP problem builder
# ──────────────────────────────────────────────────────────────────────────────

def _add_loss(
    pulp_problem: pulp.LpProblem,
    problem:      Problem,
    choose_edges: dict,
) -> pulp.LpProblem:
    lp = problem.loss_params
    print(choose_edges.keys())
    pulp_problem += lp.alpha_distance * pulp.lpSum(
        problem.oriented_edges.distances_km[(node_start.id, node_end.id)]*choose_edges[node_start.get_id_for_pulp(), node_end.get_id_for_pulp(), vehicule.id]
        for node_start in problem.all_nodes
        for node_end   in problem.all_nodes
        for vehicule   in problem.vehicles_dict.values()
        if node_start != node_end
    )
    return pulp_problem


def _add_constraints(
    pulp_problem: pulp.LpProblem,
    problem:      Problem,
    choose_edges: dict,
) -> pulp.LpProblem:
    all_nodes = problem.all_nodes

    # Each venue must be delivered exactly once
    for delivery_node in problem.delivery_nodes:
        pulp_problem += (
            pulp.lpSum(
                choose_edges[delivery_node.get_id_for_pulp(), node_end.get_id_for_pulp(), vehicule.id]
                for node_end in all_nodes
                for vehicule in problem.vehicles_dict.values()
                if node_end.get_id_for_pulp() != delivery_node.get_id_for_pulp()
            ) == 1
        )

    # Each venue must be picked up exactly once
    for recovery_node in problem.recovery_nodes:
        pulp_problem += (
            pulp.lpSum(
                choose_edges[recovery_node.get_id_for_pulp(), node_end.get_id_for_pulp(), vehicule.id]
                for node_end in all_nodes
                for vehicule in problem.vehicles_dict.values()
                if node_end.get_id_for_pulp() != recovery_node.get_id_for_pulp()
            ) == 1
        )

    # Flow conservation on intermediate nodes
    for node in problem.delivery_nodes + problem.recovery_nodes:
        for vehicule in problem.vehicles_dict.values():
            pulp_problem += (
                pulp.lpSum(
                    choose_edges[node_start.get_id_for_pulp(), node.get_id_for_pulp(), vehicule.id]
                    for node_start in all_nodes if node_start.get_id_for_pulp() != node.get_id_for_pulp()
                )
                ==
                pulp.lpSum(
                    choose_edges[node.get_id_for_pulp(), node_end.get_id_for_pulp(), vehicule.id]
                    for node_end in all_nodes if node_end.get_id_for_pulp() != node.get_id_for_pulp()
                )
            )

  # Each vehicle departs from the depot at most once
    for vehicule in problem.vehicles_dict.values():
        pulp_problem += pulp.lpSum(choose_edges[problem.deposit_node.get_id_for_pulp(), node_end.get_id_for_pulp(), vehicule.id] for node_end in all_nodes if node_end.get_id_for_pulp() != problem.deposit_node.get_id_for_pulp()) <= 1

    # # Each vehicle returns to the depot at most once
        for vehicule in problem.vehicles_dict.values():
            pulp_problem += pulp.lpSum(choose_edges[node_start.get_id_for_pulp(), problem.deposit_node.get_id_for_pulp(), vehicule.id] for node_start in all_nodes if node_start.get_id_for_pulp() != problem.deposit_node.get_id_for_pulp()) <= 1

    # # Consistency: nb departures == nb arrivals (if leaves, it returns)
    for vehicule in problem.vehicles_dict.values():
        pulp_problem += (
            pulp.lpSum(choose_edges[problem.deposit_node.get_id_for_pulp(), node_end.get_id_for_pulp(), vehicule.id] for node_end in all_nodes if node_end.get_id_for_pulp() != problem.deposit_node.get_id_for_pulp())
            ==
            pulp.lpSum(choose_edges[node_start.get_id_for_pulp(), problem.deposit_node.get_id_for_pulp(), vehicule.id] for node_start in all_nodes if node_start.get_id_for_pulp() != problem.deposit_node.get_id_for_pulp())
        )

    return pulp_problem


def build_pulp_problem(problem: Problem) -> pulp.LpProblem:
    all_nodes = problem.all_nodes
    vehicules = list(problem.vehicles_dict.values())

    # choose_edges[node_start_id, node_end_id, vehicule_id] = 1 if vehicule travels that edge
    indices = dict()

    for node_start in all_nodes:
        for node_end in all_nodes:
            
            start_id = node_start.get_id_for_pulp()
            end_id = node_end.get_id_for_pulp()
            
            if start_id != end_id or isinstance(node_start, DepositNode):
                for vehicule in vehicules:
                    indices[start_id, end_id, vehicule.id] = None

    choose_edges = pulp.LpVariable.dicts(
        "e",
        indices=indices,
        cat="Binary",
    )

    # TODO: wire into constraints (time-window propagation)
    times_arrival = pulp.LpVariable.dicts(
        "time_arrival",
        [(node.id, vehicule.id) for node in all_nodes for vehicule in vehicules],
        lowBound=0,
        cat="Continuous",
    )

    # TODO: wire into capacity constraints
    loads_at_arrival = pulp.LpVariable.dicts(
        "load_at_arrival",
        [(node.id, vehicule.id) for node in all_nodes for vehicule in vehicules],
        lowBound=0,
        cat="Continuous",
    )

    pulp_problem = pulp.LpProblem(problem.name, pulp.LpMinimize)
    pulp_problem = _add_loss(pulp_problem, problem, choose_edges)
    pulp_problem = _add_constraints(pulp_problem, problem, choose_edges)

    return pulp_problem, choose_edges


# ──────────────────────────────────────────────────────────────────────────────
# Constraints to implement later
# ──────────────────────────────────────────────────────────────────────────────

# ########## Temporal constraints ##########

# # Lower bound on arrival time for all nodes
# for v in nodes_delivery + nodes_recovery:
#     for k in vehicles:
#         prob += T[v, k] >= a[v]

# # Upper bound on arrival time for all nodes
# for v in nodes_delivery + nodes_recovery:
#     for k in vehicles:
#         prob += T[v, k] <= b[v]

# # Vehicle cannot leave before depot opens
# for k in vehicles:
#     prob += T[id_depot, k] >= a[id_depot]   # a[0] = 480 min = 8h00
#     prob += T[id_depot, k] <= b[id_depot]   # b[0] = 1380 min = 23h00

# M = 1600  # big-M > max possible journey duration (minutes)

# # Service time per node (load/unload duration)
# s = {}
# for v in nodes:
#     s[(v, "d")] = location_data[v]["setup_duration_min"]
#     s[(v, "r")] = location_data[v]["teardown_duration_min"]
# s[id_depot] = 0

# # Time propagation between consecutive nodes
# for v in all_nodes:
#     for w in all_nodes:
#         if v != w:
#             for k in vehicles:
#                 prob += (
#                     T[w, k] >= T[v, k] + s[v] + get_time(v, w) - M * (1 - x[v, w, k])
#                 )


# ########## Capacity constraints ##########

# # L[v, k] = load (volume) on vehicle k upon ARRIVAL at node v

# # Upper bound: load never exceeds vehicle capacity
# for v in all_nodes:
#     for k in vehicles:
#         prob += L[v, k] <= Q[k]

# # Lower bound already enforced via lowBound=0 in variable declaration

# # Load propagation between consecutive nodes (big-M linearisation):
# #   If x[v,w,k] = 1  =>  L[w,k] = L[v,k] + demand[w]
# for v in all_nodes:
#     for w in all_nodes:
#         if v != w:
#             for k in vehicles:
#                 prob += L[w, k] >= L[v, k] + demand[w] - Q[k] * (1 - x[v, w, k])
#                 prob += L[w, k] <= L[v, k] + demand[w] + Q[k] * (1 - x[v, w, k])

# # Note: L[depot, k] is NOT fixed explicitly.
# # It represents the load upon RETURN to the depot.
# # The big-M propagation above guarantees consistency throughout each route.
# # The only natural constraints are L[depot,k] >= 0 (via lowBound) and <= Q[k].


# ########## Early-arrival waiting times (penalty variables) ##########

# # W_d[v, k]: waiting time before unloading = max(0, a[(v,"d")] - T[(v,"d"), k])
# W_d = pulp.LpVariable.dicts("W_d",
#     [(v, k) for v in nodes for k in vehicles], lowBound=0, cat="Continuous")

# # W_r[v, k]: waiting time before pickup = max(0, a[(v,"r")] - T[(v,"r"), k])
# W_r = pulp.LpVariable.dicts("W_r",
#     [(v, k) for v in nodes for k in vehicles], lowBound=0, cat="Continuous")

# # Constraints defining W
# for v in nodes:
#     for k in vehicles:
#         prob += W_d[(v, k)] >= a[(v, "d")] - T[(v, "d"), k]
#         prob += W_r[(v, k)] >= a[(v, "r")] - T[(v, "r"), k]

# # Time-window constraints (prevent "cheating" via waiting variables)
# for v in nodes:
#     for k in vehicles:
#         prob += T[(v, "d"), k] >= a[(v, "d")]   # not before opening
#         prob += T[(v, "d"), k] <= b[(v, "d")]   # not after delivery deadline
#         prob += T[(v, "r"), k] >= a[(v, "r")]   # not before concert ends
#         prob += T[(v, "r"), k] <= b[(v, "r")]   # not after pickup deadline


# ──────────────────────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import os as _os
    from visualize import extract_solution, render_html

    # 1. Load data from JSON
    data_path = _os.path.join(_os.path.dirname(__file__), "vrppd_data.json")
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 2. Build the domain problem (nodes, edges, vehicles)
    loss_params  = LossParams(alpha_time=0.0, alpha_distance=1.0)
    problem      = build_problem(data, loss_params)

    print(problem)

    # 3. Build the PuLP MILP model
    pulp_problem, choose_edges = build_pulp_problem(problem)

    # 4. Solve
    pulp_problem.solve(pulp.PULP_CBC_CMD(msg=1))

    status    = pulp.LpStatus[pulp_problem.status]
    objective = pulp.value(pulp_problem.objective)
    print("Status    :", status)
    print("Objective :", objective)

    # 5. Visualize
    routes      = extract_solution(problem, choose_edges)
    output_path = _os.path.join(_os.path.dirname(__file__), "solution.html")
    render_html(
        problem,
        data,
        routes,
        output_path,
        solve_status=status,
        objective_value=objective,
    )
