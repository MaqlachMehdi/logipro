from dataclasses import dataclass
import hashlib
import os
import pickle

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
class Node:
    id:               int
    required_volume:  float       | None = None
    time_window:      TimeWindow  | None = None
    gps_coordinates:  tuple       | None = None  # (lat, lon)
    required_time  :  int         | None = None # min


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




from solver.utils.geo_api import osrm_time_distance
from tqdm import tqdm
from time import time_ns
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


def _edges_cache_path(all_nodes: list[Node]) -> str:
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
    recall_api:        bool
) -> OrientedEdges:
    all_nodes  = [deposit_node] + delivery_nodes + recovery_nodes
    cache_path = _edges_cache_path(all_nodes)

    if recall_api == 0 and os.path.exists(cache_path):
        print(f"Loading oriented edges from cache: {cache_path}")
        with open(cache_path, "rb") as f:
            return pickle.load(f)

    edges = make_oriented_edges(recovery_nodes, delivery_nodes, deposit_node)

    with open(cache_path, "wb") as f:
        pickle.dump(edges, f)
    print(f"Oriented edges cached to: {cache_path}")

    return edges