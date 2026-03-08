from dataclasses import dataclass
from models.trajectories import Trajectory
from solver.problem import Problem
from models.graph import DepositNode
import pulp




@dataclass
class Result : 
  data : dict[str,Trajectory] 
  problem: Problem 
  pulp_problem: pulp.LpProblem

  def __post_init__(self):
      if not self.data:
          raise ValueError("Result data is empty.")
      if self.pulp_problem.status != pulp.LpStatusOptimal:
          raise ValueError(f"Result pulp_problem is not optimal. Status: {pulp.LpStatus[self.pulp_problem.status]}")
      


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
    )# + lp.alpha_time * pulp.lpSum(
        

    return pulp_problem


def _add_constraints(
    pulp_problem    : pulp.LpProblem,
    problem         : Problem,
    choose_edges    : dict[tuple[str, str, str], pulp.LpVariable],
    times_arrival   : dict[tuple[str, str], pulp.LpVariable],
    loads_at_arrival: dict[tuple[str, str], pulp.LpVariable],
) -> pulp.LpProblem:
    all_nodes = problem.all_nodes


    # === FLUX CONSTRAINTS ===
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

    # === TIME A LOCATION CONSTRAINT (FULFILL JOBS) ===

    # # Lower bound on arrival time for all nodes
    for node in problem.delivery_nodes + problem.recovery_nodes:
        for vehicule in problem.vehicles_dict.values():
            pulp_problem += times_arrival[node.get_id_for_pulp(), vehicule.id] >= node.time_window.start_minutes

    # Upper bound on arrival time for all nodes
    for node in problem.delivery_nodes + problem.recovery_nodes:
        for vehicule in problem.vehicles_dict.values():
            pulp_problem += times_arrival[node.get_id_for_pulp(), vehicule.id] <= node.time_window.end_minutes

    # Vehicle cannot leave before depot opens
    for vehicule in problem.vehicles_dict.values():
        pulp_problem += times_arrival[problem.deposit_node.get_id_for_pulp(), vehicule.id] >= problem.deposit_node.time_window.start_minutes
        pulp_problem += times_arrival[problem.deposit_node.get_id_for_pulp(), vehicule.id] <= problem.deposit_node.time_window.end_minutes

    M = 1600  # big-M > max possible journey duration (minutes)


    # Time propagation between consecutive nodes
    for node_1 in all_nodes:
        for node_2 in all_nodes:
            if node_1 != node_2:
                for vehicule in problem.vehicles_dict.values():
                    
                    pulp_problem += (
                        times_arrival[node_2.get_id_for_pulp(), vehicule.id] >= ( # arrival time at 2 must be lower than
                            times_arrival[node_1.get_id_for_pulp(), vehicule.id] # arrival time at 1 
                            + node_1.required_time # temps requis sur site.
                            + problem.oriented_edges.travel_times_min[node_1.id, node_2.id] # temps de 1 vers 2 
                            - M * (1 - choose_edges[node_1.get_id_for_pulp(), node_2.get_id_for_pulp(), vehicule.id]) # deactivate the constraint when edge's not active
                          )
                    )


    return pulp_problem


def build_pulp_problem(problem: Problem) -> pulp.LpProblem:
    all_nodes = problem.all_nodes
    all_nodes_except_deposit = problem.delivery_nodes + problem.recovery_nodes
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
        [(node.get_id_for_pulp(), vehicule.id) for node in  for vehicule in vehicules],
        lowBound=0,
        cat="Continuous",
    )

    # TODO: wire into capacity constraints
    loads_at_arrival = pulp.LpVariable.dicts(
        "load_at_arrival",
        [(node.get_id_for_pulp(), vehicule.id) for node in all_nodes for vehicule in vehicules],
        lowBound=0,
        cat="Continuous",
    )

    pulp_problem = pulp.LpProblem(problem.name, pulp.LpMinimize)
    pulp_problem = _add_loss(pulp_problem, problem, choose_edges)
    pulp_problem = _add_constraints(pulp_problem, problem, choose_edges,times_arrival, loads_at_arrival)

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

