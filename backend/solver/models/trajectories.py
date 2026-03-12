from dataclasses import dataclass
from solver.models.graph import Node
@dataclass 
class Trajectory:
    vehicle_id: str

    arrival_nodes: list[Node]  # list of node ids in visit order
    departure_nodes: list[Node]  # corresponding departure times (minutes)

    # arrival_times : list[int]
    # departure_times : list[int]

    # load_at_arrival: list[float]  # corresponding load upon arrival (m³)

    # def health_check(self):
    #     if not self.node_sequence:
    #         raise ValueError("Node sequence is empty.")
    #     if not self.arrival_times:
    #         raise ValueError("Arrival times are empty.")
    #     if not self.load_at_arrival:
    #         raise ValueError("Load at arrival is empty.")
    #     if (
    #         len(self.node_sequence) != len(self.arrival_times)
    #         or len(self.node_sequence) != len(self.load_at_arrival)
    #     ):
    #         raise ValueError("Inconsistent lengths of trajectory lists.")
        
    def __post_init__(self):
        pass
        # self.health_check()