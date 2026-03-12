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

    def __str__(self):
        return_str = "Result:\n >>> Trajectories :\n"
        for plate, trajectory in self.data.items():
            return_str += f"    - Vehicle {plate} :\n"
            for arrival_node, departure_node in zip(trajectory.arrival_nodes, trajectory.departure_nodes):
                return_str += f"        Departure from {departure_node.id} (type: {departure_node.__class__.__name__}) ------> Arrival at {arrival_node.id} (type: {arrival_node.__class__.__name__})\n"
        return return_str
      


from models.trajectories import Trajectory
def make_result_from_pulp_result(pulp_problem: pulp.LpProblem, problem: Problem) -> Result:
    chosen_edges = {var.name: var.varValue for var in pulp_problem.variables() if var.name.startswith("e_")}
    data = dict()

    chosen_edges_dict = dict()
    
    for plate in problem.vehicles_dict.keys(): 
        chosen_edges_dict[plate] = list()
    print(f"Initialized : {chosen_edges_dict}")

    for var_name, value in chosen_edges.items():
        if value >= 0.99:  # binary variable, consider as chosen if value is close to 1
            plate = var_name.split(',')[2].split("'")[1].replace("_","-")
            print(plate)

            node_start_id = var_name.split(',')[0].split("'")[1]
            node_end_id = var_name.split(',')[1].split("'")[1]


            chosen_edges_dict[plate].append((node_start_id, node_end_id))
        
        for plate, chain in chosen_edges_dict.items(): 
            if not chain:
                continue
            # build mapping and walk from depot (robuste)
            deposit_id = problem.deposit_node.get_id_for_pulp()
            mapping = {}
            for s, e in chain:
                mapping[s] = e
            current = deposit_id
            visited = set()
            arrival_node_index = []
            departure_node_index = [deposit_id]
            while True:
                if current in visited:
                    print("Cycle detected, stopping")
                    break
                visited.add(current)
                if current not in mapping:
                    print("No edge found for current departure:", current)
                    break
                nxt = mapping[current]
                arrival_node_index.append(nxt)
                departure_node_index.append(nxt)
                current = nxt
                if current == deposit_id:
                    break
            # build Trajectory from arrival_node_index / departure_node_index...
            trajectory = Trajectory(
                vehicle_id=plate,
                arrival_nodes=[problem.access_node_by_pulp_id(node_id.replace("_","-")) for node_id in arrival_node_index],
                departure_nodes=[problem.access_node_by_pulp_id(node_id.replace("_","-")) for node_id in departure_node_index],
            )
            data[plate] = trajectory

    return Result(data=data, problem=problem, pulp_problem=pulp_problem)


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

    time_arrival_deposit    : dict[tuple[str], pulp.LpVariable],
    time_departure_deposit  : dict[tuple[str], pulp.LpVariable],

    loads_at_arrival: dict[tuple[str, str], pulp.LpVariable],
) -> pulp.LpProblem:
    print(f"At reception : {time_arrival_deposit}\n {50*'-'}")
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
        print(f"VEHICULE : {vehicule.id}")
        print(time_arrival_deposit)
        print("=================================")
        pulp_problem += time_arrival_deposit[vehicule.id] >= problem.deposit_node.time_window.start_minutes
        pulp_problem += time_arrival_deposit[vehicule.id] <= problem.deposit_node.time_window.end_minutes

    M = 1600  # big-M > max possible journey duration (minutes)


    # Time propagation between consecutive nodes
    all_nodes_except_deposit = problem.delivery_nodes + problem.recovery_nodes
    # CASES STARTING FROM DEPOSIT
    for node_end in all_nodes_except_deposit:
        for vehicule in problem.vehicles_dict.values():

            travel_time = problem.oriented_edges.travel_times_min[problem.deposit_node.id, node_end.id] # travel time from deposit to node_end
            time_departure = time_departure_deposit[vehicule.id] # departure time from deposit

            pulp_problem += (
                 # arrival time at node_end must be >= departure time from deposit + travel time, if edge is chosen
                times_arrival[node_end.get_id_for_pulp(), vehicule.id] >= (time_departure + travel_time
                    - M * (1 - choose_edges[problem.deposit_node.get_id_for_pulp(), node_end.get_id_for_pulp(), vehicule.id]) # deactivate the constraint when edge's not active
                )
            )

    # CASES ENDING AT DEPOSIT
    for node_start in all_nodes_except_deposit:
        for vehicule in problem.vehicles_dict.values():
            time_departure = times_arrival[node_start.get_id_for_pulp(), vehicule.id] + node_start.required_time
            travel_time = problem.oriented_edges.travel_times_min[node_start.id, problem.deposit_node.id] # travel time from node_start to deposit
            pulp_problem += (
                 # arrival time at deposit must be >= departure time from node_start + travel_time, if edge is chosen
                time_arrival_deposit[vehicule.id] >= (time_departure + travel_time
                    - M * (1 - choose_edges[node_start.get_id_for_pulp(), problem.deposit_node.get_id_for_pulp(), vehicule.id]) # deactivate the constraint when edge's not active
                )
            )

    # CASES WHERE DEPOSIT IS NOT INVOLVED
    for node_start in all_nodes_except_deposit:
        for node_end in all_nodes_except_deposit:
            if node_start != node_end:
                for vehicule in problem.vehicles_dict.values():
                    time_departure = times_arrival[node_start.get_id_for_pulp(), vehicule.id] + node_start.required_time
                    travel_time = problem.oriented_edges.travel_times_min[node_start.id, node_end.id] # travel time from node_start to node_end
                    pulp_problem += (
                         # arrival time at node_end must be >= departure time from node_start + travel time, if edge is chosen
                        times_arrival[node_end.get_id_for_pulp(), vehicule.id] >= (time_departure + travel_time
                            - M * (1 - choose_edges[node_start.get_id_for_pulp(), node_end.get_id_for_pulp(), vehicule.id]) # deactivate the constraint when edge's not active
                          )
                    )
    
    # ########## Capacity constraints ##########

    # # L[v, k] = load (volume) on vehicle k upon ARRIVAL at node v

    # Upper bound: load never exceeds vehicle capacity
    # Lower bound already enforced via lowBound=0 in variable declaration
    for node in all_nodes_except_deposit:
        for vehicule in problem.vehicles_dict.values():
            pulp_problem += loads_at_arrival[node.get_id_for_pulp(), vehicule.id] <= vehicule.max_volume


    # Load propagation between consecutive nodes (big-M linearisation):
    #   If x[v,w,k] = 1  =>  L[w,k] = L[v,k] + demand[w]

    # for node_start in all_nodes:
    #     for node_arrival in all_nodes:
    #         if node_start != node_arrival:
    #             for vehicule in problem.vehicles_dict.values() :
    #                 demand = node_arrival.required_volume or 0.0
    #                 #print(demand)
    #                 pulp_problem += loads_at_arrival[node_arrival.get_id_for_pulp(), vehicule.id] >= loads_at_arrival[node_start.get_id_for_pulp(), vehicule.id] + demand - vehicule.max_volume * (1 - choose_edges[node_start.get_id_for_pulp(), node_arrival.get_id_for_pulp(), vehicule.id])
    #                 pulp_problem += loads_at_arrival[node_arrival.get_id_for_pulp(), vehicule.id] <= loads_at_arrival[node_start.get_id_for_pulp(), vehicule.id] + demand + vehicule.max_volume * (1 - choose_edges[node_start.get_id_for_pulp(), node_arrival.get_id_for_pulp(), vehicule.id])


    #for v in all_nodes:
    #     for w in all_nodes:
    #         if v != w:
    #             for k in vehicles:
    #                 prob += L[w, k] >= L[v, k] + demand[w] - Q[k] * (1 - x[v, w, k])
    #                 prob += L[w, k] <= L[v, k] + demand[w] + Q[k] * (1 - x[v, w, k])

    # # Note: L[depot, k] is NOT fixed explicitly.
    # # It represents the load upon RETURN to the depot.
    # # The big-M propagation above guarantees consistency throughout each route.
    # # The only natural constraints are L[depot,k] >= 0 (via lowBound) and <= Q[k].


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
        [(node.get_id_for_pulp(), vehicule.id) for node in all_nodes_except_deposit for vehicule in vehicules],
        lowBound=0,
        cat="Continuous",
    )

    time_arrival_deposit = pulp.LpVariable.dicts(
        "time_arrival_deposit",
        [vehicule.id for vehicule in vehicules],
        lowBound=0,
        cat="Continuous",
    )
    print(f"At creation : {time_arrival_deposit}\n {50*'-'}")
    time_departure_deposit = pulp.LpVariable.dicts(
        "time_departure_deposit",
        [vehicule.id for vehicule in vehicules],
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
    pulp_problem = _add_constraints(
        pulp_problem=pulp_problem,
        problem=problem,
        choose_edges=choose_edges,
        times_arrival=times_arrival,
        loads_at_arrival=loads_at_arrival,
        time_arrival_deposit=time_arrival_deposit,
        time_departure_deposit=time_departure_deposit
    )

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

