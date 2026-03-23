from dataclasses import dataclass
from solver.solver.problem import Problem
from solver.models.trajectories import Trajectory
from solver.models.graph import DepositNode
import pulp
import sys
import time

# Maximum time (in seconds) to wait for the solver before returning
MAX_WAIT_TIME = 300  # 5 minutes


class SolverTimeoutError(Exception):
    """Raised when solver exceeds MAX_WAIT_TIME without finding any feasible solution."""
    pass


# ──────────────────────────────────────────────────────────────────────────────
# Progress logging utilities
# ──────────────────────────────────────────────────────────────────────────────

class SolverProgress:
    """Helper class to log solver progress with visual indicators."""

    COLORS = {
        'reset': '\033[0m',
        'bold': '\033[1m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'cyan': '\033[96m',
        'magenta': '\033[95m',
        'blue': '\033[94m',
        'red': '\033[91m',
    }

    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.start_time = None
        self.phase_start = None
        self.current_phase = None

    def _elapsed(self) -> str:
        if self.start_time is None:
            return "0.0s"
        return f"{time.time() - self.start_time:.1f}s"

    def _phase_elapsed(self) -> str:
        if self.phase_start is None:
            return "0.0s"
        return f"{time.time() - self.phase_start:.1f}s"

    def start(self, problem_name: str):
        """Start logging for a new problem."""
        self.start_time = time.time()
        if self.verbose:
            c = self.COLORS
            print(f"\n{c['bold']}{c['cyan']}╔══════════════════════════════════════════════════════════════════╗{c['reset']}")
            print(f"{c['bold']}{c['cyan']}║{c['reset']}  🚀 VRPPD Solver - Building MILP Model                           {c['bold']}{c['cyan']}║{c['reset']}")
            print(f"{c['bold']}{c['cyan']}║{c['reset']}  Problem: {problem_name:<54} {c['bold']}{c['cyan']}║{c['reset']}")
            print(f"{c['bold']}{c['cyan']}╚══════════════════════════════════════════════════════════════════╝{c['reset']}\n")

    def phase(self, name: str, details: str = ""):
        """Start a new phase."""
        self.current_phase = name
        self.phase_start = time.time()
        if self.verbose:
            c = self.COLORS
            detail_str = f" ({details})" if details else ""
            print(f"{c['yellow']}⏳{c['reset']} [{self._elapsed():>6}] {c['bold']}{name}{c['reset']}{detail_str}...", end="", flush=True)

    def phase_done(self, extra: str = ""):
        """Mark current phase as complete."""
        if self.verbose:
            c = self.COLORS
            extra_str = f" {c['cyan']}{extra}{c['reset']}" if extra else ""
            print(f" {c['green']}✓{c['reset']} ({self._phase_elapsed()}){extra_str}")

    def progress(self, current: int, total: int, label: str = ""):
        """Show progress bar for a loop."""
        if not self.verbose:
            return
        c = self.COLORS
        pct = current / total * 100
        bar_len = 30
        filled = int(bar_len * current / total)
        bar = "█" * filled + "░" * (bar_len - filled)
        label_str = f" {label}" if label else ""
        sys.stdout.write(f"\r{c['yellow']}⏳{c['reset']} [{self._elapsed():>6}] [{c['magenta']}{bar}{c['reset']}] {pct:5.1f}%{label_str}  ")
        sys.stdout.flush()
        if current == total:
            print()

    def solving_start(self):
        """Mark the start of the solving phase."""
        self.phase_start = time.time()
        if self.verbose:
            c = self.COLORS
            print(f"\n{c['bold']}{c['blue']}┌──────────────────────────────────────────────────────────────────┐{c['reset']}")
            print(f"{c['bold']}{c['blue']}│{c['reset']}  🔧 Solving MILP with CBC...                                     {c['bold']}{c['blue']}│{c['reset']}")
            print(f"{c['bold']}{c['blue']}└──────────────────────────────────────────────────────────────────┘{c['reset']}\n")

    def solving_done(self, status: str, objective: float = None):
        """Mark solving as complete."""
        if self.verbose:
            c = self.COLORS
            status_color = c['green'] if status == "Optimal" else c['yellow']
            obj_str = f", Objective: {objective:.4f}" if objective is not None else ""
            print(f"\n{c['bold']}{c['green']}╔══════════════════════════════════════════════════════════════════╗{c['reset']}")
            print(f"{c['bold']}{c['green']}║{c['reset']}  ✅ Solution found in {self._elapsed():<43} {c['bold']}{c['green']}║{c['reset']}")
            print(f"{c['bold']}{c['green']}║{c['reset']}  Status: {status_color}{status:<55}{c['reset']} {c['bold']}{c['green']}║{c['reset']}")
            if objective is not None:
                print(f"{c['bold']}{c['green']}║{c['reset']}  Objective: {c['cyan']}{objective:<52.4f}{c['reset']} {c['bold']}{c['green']}║{c['reset']}")
            print(f"{c['bold']}{c['green']}╚══════════════════════════════════════════════════════════════════╝{c['reset']}\n")


# Global progress logger
_progress = SolverProgress(verbose=True)


def set_solver_verbose(verbose: bool):
    """Enable or disable solver progress logging."""
    global _progress
    _progress = SolverProgress(verbose=verbose)


# ──────────────────────────────────────────────────────────────────────────────
# Greedy Heuristic for Warm Start
# ──────────────────────────────────────────────────────────────────────────────

# Budget (in iterations) for greedy heuristic local search improvements
GREEDY_IMPROVEMENT_BUDGET = 50


def greedy_initial_solution(
    problem: "Problem",
    choose_edges: dict,
    verbose: bool = True,
    improvement_budget: int = None,
) -> bool:
    """
    Build a greedy initial solution using nearest-neighbor heuristic.

    Strategy:
    1. Sort nodes by time window (earliest deadline first)
    2. For each unassigned node, find the best vehicle that can serve it
    3. Insert node into vehicle's route at best position
    4. Apply local search improvements (swap, relocate) within budget

    Args:
        problem: The Problem instance.
        choose_edges: Edge decision variables dict.
        verbose: If True, show progress.
        improvement_budget: Number of local search iterations. Defaults to GREEDY_IMPROVEMENT_BUDGET.

    Returns True if a feasible solution was found, False otherwise.
    """
    if improvement_budget is None:
        improvement_budget = GREEDY_IMPROVEMENT_BUDGET
    c = SolverProgress.COLORS if verbose else {k: '' for k in SolverProgress.COLORS}

    if verbose:
        print(f"\n{c['bold']}{c['yellow']}┌──────────────────────────────────────────────────────────────────┐{c['reset']}")
        print(f"{c['bold']}{c['yellow']}│{c['reset']}  🎯 Building greedy initial solution (warm start)               {c['bold']}{c['yellow']}│{c['reset']}")
        print(f"{c['bold']}{c['yellow']}└──────────────────────────────────────────────────────────────────┘{c['reset']}")

    # Initialize all edge variables to 0
    for var in choose_edges.values():
        var.setInitialValue(0)

    vehicles = list(problem.vehicles_dict.values())
    deposit = problem.deposit_node
    deposit_id = deposit.get_id_for_pulp()

    # Track vehicle state
    vehicle_routes = {v.id: [] for v in vehicles}  # List of nodes in order
    vehicle_loads = {v.id: 0.0 for v in vehicles}  # Current load
    vehicle_times = {v.id: deposit.time_window.start_minutes for v in vehicles}  # Current time
    vehicle_positions = {v.id: deposit for v in vehicles}  # Current position

    # Get all nodes to visit (deliveries first, then recoveries)
    # Sort by time window end (earliest deadline first)
    delivery_nodes = sorted(
        problem.delivery_nodes,
        key=lambda n: n.time_window.end_minutes
    )
    recovery_nodes = sorted(
        problem.recovery_nodes,
        key=lambda n: n.time_window.start_minutes  # Recoveries: earliest start
    )

    # We need to deliver before we can recover from same location
    # Group by location ID
    location_deliveries = {n.id: n for n in delivery_nodes}
    location_recoveries = {n.id: n for n in recovery_nodes}

    assigned_deliveries = set()
    assigned_recoveries = set()

    def get_travel_time(from_node, to_node):
        """Get travel time between two nodes."""
        return problem.oriented_edges.travel_times_min.get(
            (from_node.id, to_node.id), float('inf')
        )

    def can_serve_delivery(vehicle, node, current_load, current_time, current_pos):
        """Check if vehicle can serve this delivery node."""
        travel_time = get_travel_time(current_pos, node)
        arrival_time = current_time + travel_time

        # Check time window
        if arrival_time > node.time_window.end_minutes:
            return False, None, None

        # Wait if too early
        service_start = max(arrival_time, node.time_window.start_minutes)

        # Check if we have enough load to deliver
        required = node.required_volume or 0
        if current_load < required:
            return False, None, None

        new_load = current_load - required
        new_time = service_start + (node.required_time or 0)

        # Check if we can return to depot in time
        return_time = new_time + get_travel_time(node, deposit)
        if return_time > deposit.time_window.end_minutes:
            return False, None, None

        return True, new_load, new_time

    def can_serve_recovery(vehicle, node, current_load, current_time, current_pos):
        """Check if vehicle can serve this recovery node."""
        travel_time = get_travel_time(current_pos, node)
        arrival_time = current_time + travel_time

        # Check time window
        if arrival_time > node.time_window.end_minutes:
            return False, None, None

        # Wait if too early
        service_start = max(arrival_time, node.time_window.start_minutes)

        # Check capacity (recovery adds load, required_volume is negative)
        pickup = abs(node.required_volume or 0)
        v = problem.vehicles_dict[vehicle]
        if current_load + pickup > v.max_volume:
            return False, None, None

        new_load = current_load + pickup
        new_time = service_start + (node.required_time or 0)

        # Check if we can return to depot in time
        return_time = new_time + get_travel_time(node, deposit)
        if return_time > deposit.time_window.end_minutes:
            return False, None, None

        return True, new_load, new_time

    # Phase 1: Assign deliveries
    # First, compute total delivery volume needed
    total_delivery_volume = sum(n.required_volume or 0 for n in delivery_nodes)

    if verbose:
        print(f"  📦 Deliveries: {len(delivery_nodes)} nodes, {total_delivery_volume:.1f} m³ total")
        print(f"  📥 Recoveries: {len(recovery_nodes)} nodes")
        print(f"  🚛 Vehicles: {len(vehicles)} available")

    # Pre-load vehicles with delivery volume (greedy bin packing)
    delivery_assignments = {v.id: [] for v in vehicles}
    remaining_deliveries = list(delivery_nodes)

    for v in sorted(vehicles, key=lambda x: -x.max_volume):  # Biggest first
        capacity = v.max_volume
        current_load = 0

        # Greedy: pack deliveries that fit
        still_remaining = []
        for node in remaining_deliveries:
            vol = node.required_volume or 0
            if current_load + vol <= capacity:
                delivery_assignments[v.id].append(node)
                current_load += vol
            else:
                still_remaining.append(node)
        remaining_deliveries = still_remaining
        vehicle_loads[v.id] = current_load  # Initial load when leaving depot

    if remaining_deliveries:
        if verbose:
            print(f"  {c['yellow']}⚠️  {len(remaining_deliveries)} deliveries couldn't be assigned (capacity){c['reset']}")
        return False

    # Phase 2: Build routes for each vehicle using nearest neighbor
    success = True
    total_edges_set = 0

    for v in vehicles:
        assigned_nodes = delivery_assignments[v.id]
        if not assigned_nodes:
            continue

        # Sort by nearest neighbor from depot
        route = []
        current_pos = deposit
        current_time = deposit.time_window.start_minutes
        current_load = vehicle_loads[v.id]
        unvisited = list(assigned_nodes)

        while unvisited:
            # Find nearest feasible node
            best_node = None
            best_time = float('inf')
            best_load = None
            best_arrival = None

            for node in unvisited:
                can_do, new_load, new_time = can_serve_delivery(
                    v.id, node, current_load, current_time, current_pos
                )
                if can_do:
                    travel = get_travel_time(current_pos, node)
                    if travel < best_time:
                        best_node = node
                        best_time = travel
                        best_load = new_load
                        best_arrival = new_time

            if best_node is None:
                # Can't serve remaining nodes - try to recover
                if verbose:
                    print(f"  {c['yellow']}⚠️  Vehicle {v.id}: stuck with {len(unvisited)} unserved deliveries{c['reset']}")
                success = False
                break

            # Add edge from current position to best node
            from_id = current_pos.get_id_for_pulp()
            to_id = best_node.get_id_for_pulp()
            edge_key = (from_id, to_id, v.id)
            if edge_key in choose_edges:
                choose_edges[edge_key].setInitialValue(1)
                total_edges_set += 1

            route.append(best_node)
            assigned_deliveries.add(best_node.id)
            unvisited.remove(best_node)
            current_pos = best_node
            current_time = best_arrival
            current_load = best_load

        # Try to add recoveries for locations we delivered to
        for delivery_node in route:
            loc_id = delivery_node.id
            if loc_id in location_recoveries and loc_id not in assigned_recoveries:
                recovery_node = location_recoveries[loc_id]
                can_do, new_load, new_time = can_serve_recovery(
                    v.id, recovery_node, current_load, current_time, current_pos
                )
                if can_do:
                    from_id = current_pos.get_id_for_pulp()
                    to_id = recovery_node.get_id_for_pulp()
                    edge_key = (from_id, to_id, v.id)
                    if edge_key in choose_edges:
                        choose_edges[edge_key].setInitialValue(1)
                        total_edges_set += 1

                    assigned_recoveries.add(loc_id)
                    current_pos = recovery_node
                    current_time = new_time
                    current_load = new_load

        # Return to depot
        if route:
            from_id = current_pos.get_id_for_pulp()
            edge_key = (from_id, deposit_id, v.id)
            if edge_key in choose_edges:
                choose_edges[edge_key].setInitialValue(1)
                total_edges_set += 1

        vehicle_routes[v.id] = route

    # Phase 3: Assign remaining recoveries to any vehicle with capacity
    remaining_recoveries = [n for n in recovery_nodes if n.id not in assigned_recoveries]

    for recovery_node in remaining_recoveries:
        assigned = False
        for v in vehicles:
            if not vehicle_routes[v.id]:
                continue

            # Check if this vehicle can handle one more recovery
            # Simplified: just check capacity
            pickup = abs(recovery_node.required_volume or 0)
            # This is approximate - real check would need to track actual loads
            if pickup <= v.max_volume * 0.3:  # Conservative
                # Add to this vehicle's route (at end before depot)
                last_node = vehicle_routes[v.id][-1] if vehicle_routes[v.id] else deposit

                # Remove edge from last_node to depot
                from_id = last_node.get_id_for_pulp()
                edge_key = (from_id, deposit_id, v.id)
                if edge_key in choose_edges:
                    choose_edges[edge_key].setInitialValue(0)

                # Add edge from last_node to recovery
                to_id = recovery_node.get_id_for_pulp()
                edge_key = (from_id, to_id, v.id)
                if edge_key in choose_edges:
                    choose_edges[edge_key].setInitialValue(1)
                    total_edges_set += 1

                # Add edge from recovery to depot
                edge_key = (to_id, deposit_id, v.id)
                if edge_key in choose_edges:
                    choose_edges[edge_key].setInitialValue(1)
                    total_edges_set += 1

                assigned_recoveries.add(recovery_node.id)
                assigned = True
                break

        if not assigned and verbose:
            print(f"  {c['yellow']}⚠️  Recovery {recovery_node.id} not assigned{c['reset']}")

    # Phase 4: Local search improvements
    if improvement_budget > 0 and verbose:
        print(f"\n  🔄 Running local search improvements ({improvement_budget} iterations)...")

    def compute_route_cost(route, start_pos=deposit):
        """Compute total travel time for a route."""
        if not route:
            return 0
        cost = get_travel_time(start_pos, route[0])
        for i in range(len(route) - 1):
            cost += get_travel_time(route[i], route[i + 1])
        cost += get_travel_time(route[-1], deposit)
        return cost

    def rebuild_edges_for_vehicle(v_id, route):
        """Clear and rebuild edge variables for a vehicle's route."""
        # Clear all edges for this vehicle
        for key, var in choose_edges.items():
            if key[2] == v_id:
                var.setInitialValue(0)

        if not route:
            return 0

        edges_set = 0
        # Depot -> first node
        edge_key = (deposit_id, route[0].get_id_for_pulp(), v_id)
        if edge_key in choose_edges:
            choose_edges[edge_key].setInitialValue(1)
            edges_set += 1

        # Node -> node
        for i in range(len(route) - 1):
            edge_key = (route[i].get_id_for_pulp(), route[i + 1].get_id_for_pulp(), v_id)
            if edge_key in choose_edges:
                choose_edges[edge_key].setInitialValue(1)
                edges_set += 1

        # Last node -> depot
        edge_key = (route[-1].get_id_for_pulp(), deposit_id, v_id)
        if edge_key in choose_edges:
            choose_edges[edge_key].setInitialValue(1)
            edges_set += 1

        return edges_set

    improvements_made = 0
    for iteration in range(improvement_budget):
        improved = False

        # Try 2-opt within each route (reverse a segment)
        for v in vehicles:
            route = vehicle_routes[v.id]
            if len(route) < 3:
                continue

            best_cost = compute_route_cost(route)
            best_route = route[:]

            for i in range(len(route) - 1):
                for j in range(i + 2, len(route)):
                    # Reverse segment [i+1, j]
                    new_route = route[:i+1] + route[i+1:j+1][::-1] + route[j+1:]
                    new_cost = compute_route_cost(new_route)
                    if new_cost < best_cost:
                        best_cost = new_cost
                        best_route = new_route
                        improved = True

            if best_route != route:
                vehicle_routes[v.id] = best_route
                improvements_made += 1

        # Try swap between routes (exchange one node from each)
        vehicle_list = [v for v in vehicles if vehicle_routes[v.id]]
        for i, v1 in enumerate(vehicle_list):
            for v2 in vehicle_list[i+1:]:
                route1 = vehicle_routes[v1.id]
                route2 = vehicle_routes[v2.id]

                if not route1 or not route2:
                    continue

                cost_before = compute_route_cost(route1) + compute_route_cost(route2)

                # Try swapping each pair of nodes
                for idx1, node1 in enumerate(route1):
                    for idx2, node2 in enumerate(route2):
                        # Skip if node types don't match (both delivery or both recovery)
                        if type(node1).__name__ != type(node2).__name__:
                            continue

                        # Create new routes with swapped nodes
                        new_route1 = route1[:idx1] + [node2] + route1[idx1+1:]
                        new_route2 = route2[:idx2] + [node1] + route2[idx2+1:]

                        cost_after = compute_route_cost(new_route1) + compute_route_cost(new_route2)

                        if cost_after < cost_before:
                            vehicle_routes[v1.id] = new_route1
                            vehicle_routes[v2.id] = new_route2
                            route1, route2 = new_route1, new_route2
                            cost_before = cost_after
                            improved = True
                            improvements_made += 1

        if not improved:
            break

    # Rebuild all edge variables from improved routes
    total_edges_set = 0
    for v in vehicles:
        total_edges_set += rebuild_edges_for_vehicle(v.id, vehicle_routes[v.id])

    if verbose and improvement_budget > 0:
        print(f"  ✨ Local search: {improvements_made} improvements in {iteration + 1} iterations")

    # Summary
    n_assigned_d = len(assigned_deliveries)
    n_assigned_r = len(assigned_recoveries)
    n_total_d = len(delivery_nodes)
    n_total_r = len(recovery_nodes)

    if verbose:
        status = "✅" if (n_assigned_d == n_total_d and n_assigned_r == n_total_r) else "⚠️"
        print(f"\n  {status} Greedy result: {n_assigned_d}/{n_total_d} deliveries, {n_assigned_r}/{n_total_r} recoveries")
        print(f"  📊 Set {total_edges_set} edge variables to 1")

        active_vehicles = sum(1 for v in vehicles if vehicle_routes[v.id])
        print(f"  🚛 Active vehicles: {active_vehicles}/{len(vehicles)}")

    feasible = (n_assigned_d == n_total_d and n_assigned_r == n_total_r)

    if verbose:
        if feasible:
            print(f"  {c['green']}✓ Feasible initial solution found!{c['reset']}\n")
        else:
            print(f"  {c['yellow']}⚠ Partial solution (will help solver anyway){c['reset']}\n")

    return feasible


@dataclass
class Result:
    data: dict[str, Trajectory]
    problem: Problem
    pulp_problem: pulp.LpProblem

    # Load/time data extracted from PuLP solution for visualization
    # Keys use original IDs (with dashes), matching vehicle.id and node.id
    loads_at_arrival: dict[tuple[str, str], float] | None = None       # (node_id, vehicle_id) -> load m³
    times_arrival: dict[tuple[str, str], float] | None = None          # (node_id, vehicle_id) -> minutes
    time_departure_depot: dict[str, float] | None = None               # vehicle_id -> minutes
    time_arrival_depot: dict[str, float] | None = None                 # vehicle_id -> minutes
    loads_departure_depot: dict[str, float] | None = None              # vehicle_id -> load m³

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

    def get_load_at_arrival(self, node_id: str, vehicle_id: str) -> float | None:
        """Get the vehicle load upon arrival at a node."""
        if self.loads_at_arrival is None:
            return None
        return self.loads_at_arrival.get((node_id, vehicle_id))

    def get_arrival_time(self, node_id: str, vehicle_id: str) -> float | None:
        """Get arrival time at node (minutes from midnight)."""
        if self.times_arrival is None:
            return None
        return self.times_arrival.get((node_id, vehicle_id))

    def get_depot_departure_load(self, vehicle_id: str) -> float | None:
        """Get vehicle load when departing from depot."""
        if self.loads_departure_depot is None:
            return None
        return self.loads_departure_depot.get(vehicle_id)

    def get_depot_departure_time(self, vehicle_id: str) -> float | None:
        """Get departure time from depot."""
        if self.time_departure_depot is None:
            return None
        return self.time_departure_depot.get(vehicle_id)

    def get_depot_arrival_time(self, vehicle_id: str) -> float | None:
        """Get arrival time back at depot."""
        if self.time_arrival_depot is None:
            return None
        return self.time_arrival_depot.get(vehicle_id)
      


def _extract_load_time_data(pulp_problem: pulp.LpProblem) -> tuple[dict, dict, dict, dict, dict]:
    """
    Extract load and time values from solved PuLP variables.

    Returns:
        loads_at_arrival: dict[(node_id, vehicle_id), float]
        times_arrival: dict[(node_id, vehicle_id), float]
        time_departure_depot: dict[vehicle_id, float]
        time_arrival_depot: dict[vehicle_id, float]
        loads_departure_depot: dict[vehicle_id, float]

    All IDs are converted back to original format (dashes instead of underscores).
    """
    loads_at_arrival = {}
    times_arrival = {}
    time_departure_depot = {}
    time_arrival_depot = {}
    loads_departure_depot = {}

    for var in pulp_problem.variables():
        name = var.name
        val = var.varValue
        if val is None:
            continue

        # load_at_arrival_('node_id',_'vehicle_id')
        if name.startswith("load_at_arrival_("):
            parts = name.replace("load_at_arrival_(", "").rstrip(")").split(",_")
            if len(parts) == 2:
                node_id = parts[0].strip("'").replace("_", "-")
                veh_id = parts[1].strip("'").replace("_", "-")
                loads_at_arrival[(node_id, veh_id)] = val

        # time_arrival_('node_id',_'vehicle_id')
        elif name.startswith("time_arrival_(") and not name.startswith("time_arrival_deposit"):
            parts = name.replace("time_arrival_(", "").rstrip(")").split(",_")
            if len(parts) == 2:
                node_id = parts[0].strip("'").replace("_", "-")
                veh_id = parts[1].strip("'").replace("_", "-")
                times_arrival[(node_id, veh_id)] = val

        # time_departure_deposit_'vehicle_id'
        elif name.startswith("time_departure_deposit_"):
            veh_id = name.replace("time_departure_deposit_", "").strip("'").replace("_", "-")
            time_departure_depot[veh_id] = val

        # time_arrival_deposit_'vehicle_id'
        elif name.startswith("time_arrival_deposit_"):
            veh_id = name.replace("time_arrival_deposit_", "").strip("'").replace("_", "-")
            time_arrival_depot[veh_id] = val

        # load_departure_depot_'vehicle_id'
        elif name.startswith("load_departure_depot_"):
            veh_id = name.replace("load_departure_depot_", "").strip("'").replace("_", "-")
            loads_departure_depot[veh_id] = val

    return loads_at_arrival, times_arrival, time_departure_depot, time_arrival_depot, loads_departure_depot


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
                    # print("Cycle detected, stopping")
                    break
                visited.add(current)
                if current not in mapping:
                    # print("No edge found for current departure:", current)
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

    # Extract load and time data from PuLP solution
    loads_at_arrival, times_arrival, time_departure_depot, time_arrival_depot, loads_departure_depot = \
        _extract_load_time_data(pulp_problem)

    return Result(
        data=data,
        problem=problem,
        pulp_problem=pulp_problem,
        loads_at_arrival=loads_at_arrival,
        times_arrival=times_arrival,
        time_departure_depot=time_departure_depot,
        time_arrival_depot=time_arrival_depot,
        loads_departure_depot=loads_departure_depot,
    )


# ──────────────────────────────────────────────────────────────────────────────
# PuLP problem builder
# ──────────────────────────────────────────────────────────────────────────────


def _add_constraints(
    pulp_problem    : pulp.LpProblem,
    problem         : Problem,
    choose_edges    : dict[tuple[str, str, str], pulp.LpVariable],

    times_arrival   : dict[tuple[str, str], pulp.LpVariable],

    time_arrival_deposit    : dict[tuple[str], pulp.LpVariable],
    time_departure_deposit  : dict[tuple[str], pulp.LpVariable],

    loads_at_arrival: dict[tuple[str, str], pulp.LpVariable],
    loads_departure_deposit : dict[tuple[str],pulp.LpVariable],
    is_vehicule_active: dict[str, pulp.LpVariable],
) -> pulp.LpProblem:
    all_nodes = problem.all_nodes
    n_delivery = len(problem.delivery_nodes)
    n_recovery = len(problem.recovery_nodes)
    n_vehicles = len(problem.vehicles_dict)

    # === FLUX CONSTRAINTS ===
    _progress.phase("Adding flux constraints", f"{n_delivery} deliveries, {n_recovery} recoveries")

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

    _progress.phase_done(f"{n_delivery + n_recovery} constraints")

    # Flow conservation on intermediate nodes
    _progress.phase("Adding flow conservation constraints", f"{n_delivery + n_recovery} nodes × {n_vehicles} vehicles")
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

    _progress.phase_done()

    # Each vehicle departs from the depot at most once
    _progress.phase("Adding depot constraints", f"{n_vehicles} vehicles")
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

    _progress.phase_done()

    # === TIME WINDOW CONSTRAINTS ===
    _progress.phase("Adding time window constraints", f"{(n_delivery + n_recovery) * n_vehicles * 2} bounds")

    # Lower bound on arrival time for all nodes
    for node in problem.delivery_nodes + problem.recovery_nodes:
        for vehicule in problem.vehicles_dict.values():
            pulp_problem += times_arrival[node.get_id_for_pulp(), vehicule.id] >= node.time_window.start_minutes

    # Upper bound on arrival time for all nodes
    for node in problem.delivery_nodes + problem.recovery_nodes:
        for vehicule in problem.vehicles_dict.values():
            pulp_problem += times_arrival[node.get_id_for_pulp(), vehicule.id] <= node.time_window.end_minutes

    # Vehicle cannot leave before depot opens
    for vehicule in problem.vehicles_dict.values():
        pulp_problem += time_arrival_deposit[vehicule.id] >= problem.deposit_node.time_window.start_minutes
        pulp_problem += time_arrival_deposit[vehicule.id] <= problem.deposit_node.time_window.end_minutes
        # Vehicle cannot depart before depot opens
        pulp_problem += time_departure_deposit[vehicule.id] >= problem.deposit_node.time_window.start_minutes
        # Also prevent departures after depot closing
        pulp_problem += time_departure_deposit[vehicule.id] <= problem.deposit_node.time_window.end_minutes

    _progress.phase_done()

    # ===   ===     ===     ===     VEHICLE ACTIVATION CONSTRAINTS
    _progress.phase("Adding vehicle activation constraints")
    M = 1600  # big-M > max possible journey duration (minutes)
    deposit_pulp_id = problem.deposit_node.get_id_for_pulp()
    all_nodes_for_activation = problem.delivery_nodes + problem.recovery_nodes

    for vehicule in problem.vehicles_dict.values():
        # Link is_active to edges: if any edge FROM depot is chosen, vehicle is active
        for node in all_nodes_for_activation:
            edge_key = (deposit_pulp_id, node.get_id_for_pulp(), vehicule.id)
            if edge_key in choose_edges:
                pulp_problem += is_vehicule_active[vehicule.id] >= choose_edges[edge_key]

        # If vehicle is inactive, force arrival = departure (duration = 0)
        # arrival <= departure + M * is_active
        # arrival >= departure - M * is_active
        pulp_problem += time_arrival_deposit[vehicule.id] <= time_departure_deposit[vehicule.id] + M * is_vehicule_active[vehicule.id]
        pulp_problem += time_arrival_deposit[vehicule.id] >= time_departure_deposit[vehicule.id] - M * is_vehicule_active[vehicule.id]

    _progress.phase_done()

    # Time propagation between consecutive nodes
    all_nodes_except_deposit = problem.delivery_nodes + problem.recovery_nodes
    n_nodes = len(all_nodes_except_deposit)
    total_time_constraints = n_nodes * n_vehicles * 2 + n_nodes * n_nodes * n_vehicles
    _progress.phase("Adding time propagation constraints", f"~{total_time_constraints} constraints")

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
            
            # Upper bound counterpart to enforce equality when edge active
            pulp_problem += (
                times_arrival[node_end.get_id_for_pulp(), vehicule.id] <= (time_departure + travel_time
                    + M * (1 - choose_edges[problem.deposit_node.get_id_for_pulp(), node_end.get_id_for_pulp(), vehicule.id])
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
            
            # Upper bound counterpart to enforce equality when edge active
            pulp_problem += (
                time_arrival_deposit[vehicule.id] <= (time_departure + travel_time
                    + M * (1 - choose_edges[node_start.get_id_for_pulp(), problem.deposit_node.get_id_for_pulp(), vehicule.id])
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

    _progress.phase_done()

    # ########## Capacity constraints ##########
    total_cap_constraints = n_nodes * n_vehicles + n_nodes * n_vehicles * 2 + n_nodes * n_nodes * n_vehicles * 4
    _progress.phase("Adding capacity constraints", f"~{total_cap_constraints} constraints")

    # # L[v, k] = load (volume) on vehicle k upon ARRIVAL at node v
    # Upper bound: load never exceeds vehicle capacity
    # Lower bound already enforced via lowBound=0 in variable declaration
    for node in all_nodes_except_deposit:
        for vehicule in problem.vehicles_dict.values():
            pulp_problem += (
                loads_at_arrival[node.get_id_for_pulp(), vehicule.id] <= vehicule.max_volume
            )
    # Case of the deposit
    for vehicule in problem.vehicles_dict.values():
        pulp_problem += loads_departure_deposit[vehicule.id] <= vehicule.max_volume

    # Load propagation between consecutive nodes (big-M linearisation):
    #   If x[v,w,k] = 1  =>  L[w,k] = L[v,k] + demand[w]
    # === Capacity propagation (big-M), structured like time propagation ===
    
    M_cap = (
        max(vehicule.max_volume*2 for vehicule in problem.vehicles_dict.values()) 
        + max(abs(node.required_volume)*2 for node in all_nodes_except_deposit)
        )
    
    #  Propagation dépôt → premier nœud (PREMIER TRAJECT)
    #    Le véhicule PERD du volume sur un delivery (required_volume > 0)
    #    Le véhicule GAGNE du volume sur un recovery (required_volume < 0)
    for node_end in all_nodes_except_deposit:
        for vehicule in problem.vehicles_dict.values():
            demand = node_end.required_volume or 0.0  # >0 = perte, <0 = gain
            edge = choose_edges[
                problem.deposit_node.get_id_for_pulp(),
                node_end.get_id_for_pulp(),
                vehicule.id
            ]
            # L[node_end, k] = L[depot_départ, k] - demand  si arête active
            pulp_problem += (
                loads_at_arrival[node_end.get_id_for_pulp(), vehicule.id]
                >= loads_departure_deposit[vehicule.id]
                - M_cap * (1 - edge)
            )
            pulp_problem += (
                loads_at_arrival[node_end.get_id_for_pulp(), vehicule.id]
                <= loads_departure_deposit[vehicule.id]
                + M_cap * (1 - edge)
            )

    # 3. Propagation nœud → nœud (hors dépôt)
    for node_start in all_nodes_except_deposit:
        for node_end in all_nodes_except_deposit:
            if node_start == node_end:
                continue
            for vehicule in problem.vehicles_dict.values():
                

                load_at_departure_previous = loads_at_arrival[node_start.get_id_for_pulp(), vehicule.id] - node_start.required_volume

                demand_next = node_end.required_volume or 0.0

                edge = choose_edges[
                    node_start.get_id_for_pulp(),
                    node_end.get_id_for_pulp(),
                    vehicule.id
                ]

                # load_departure-previous == load_arrival-next 
                pulp_problem += (
                    loads_at_arrival[node_end.get_id_for_pulp(), vehicule.id] #load_arrival-next 
                    >= load_at_departure_previous
                    - M_cap * (1 - edge)
                )
                pulp_problem += (
                    loads_at_arrival[node_end.get_id_for_pulp(), vehicule.id]
                    <= load_at_departure_previous
                    + M_cap * (1 - edge)
                )

                # Ensure in delivery, loads is sufficient to deliver
                pulp_problem += (
                    loads_at_arrival[node_end.get_id_for_pulp(), vehicule.id]
                    >= demand_next * edge
                )
                # Ensure in recovery, loads don't exceed capacity
                pulp_problem += (
                    loads_at_arrival[node_end.get_id_for_pulp(), vehicule.id] - demand_next * edge # load at departure of end node.
                    <= vehicule.max_volume
                )

    # 4. Propagation nœud → dépôt (retour)
    for node_start in all_nodes_except_deposit:
        for vehicule in problem.vehicles_dict.values():
            edge = choose_edges[
                node_start.get_id_for_pulp(),
                problem.deposit_node.get_id_for_pulp(),
                vehicule.id
            ]
            # Le dépôt lui-même n'a pas de demand → L[depot_retour] = L[node_start]
            pulp_problem += (
                loads_at_arrival[problem.deposit_node.get_id_for_pulp(), vehicule.id]
                >= loads_at_arrival[node_start.get_id_for_pulp(), vehicule.id]
                - M_cap * (1 - edge)
            )
            pulp_problem += (
                loads_at_arrival[problem.deposit_node.get_id_for_pulp(), vehicule.id]
                <= loads_at_arrival[node_start.get_id_for_pulp(), vehicule.id]
                + M_cap * (1 - edge)
            )

    # 5. Conservation globale des instruments
    #    Ce qui part du dépôt (toute la flotte) doit revenir
    pulp_problem += (
        pulp.lpSum(
            loads_at_arrival[problem.deposit_node.get_id_for_pulp(), vehicule.id]
            for vehicule in problem.vehicles_dict.values()
        )
        ==
        pulp.lpSum(
            loads_departure_deposit[vehicule.id]
            for vehicule in problem.vehicles_dict.values()
        )
    )

    # 6. Link vehicle initial load to assigned deliveries
    #    Ensure a vehicle's departure load equals the sum of delivery volumes
    #    for which it is the assigned delivering vehicle. This prevents the
    #    model from using volumes picked up at concerts to satisfy other
    #    deliveries (mixing commodities across venues).
    for vehicule in problem.vehicles_dict.values():
        pulp_problem += (
            loads_departure_deposit[vehicule.id]
            ==
            pulp.lpSum(
                (delivery.required_volume or 0.0) * \
                pulp.lpSum(
                    choose_edges[node_start.get_id_for_pulp(), delivery.get_id_for_pulp(), vehicule.id]
                    for node_start in all_nodes
                    if node_start.get_id_for_pulp() != delivery.get_id_for_pulp()
                )
                for delivery in problem.delivery_nodes
            )
        )

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

    _progress.phase_done()

    return pulp_problem


def build_pulp_problem(problem: Problem, verbose: bool = True) -> pulp.LpProblem:
    """Build the PuLP MILP problem for VRPPD.

    Args:
        problem: The Problem instance containing all routing data.
        verbose: If True, show progress logging.

    Returns:
        Tuple of (pulp_problem, choose_edges dict).
    """
    global _progress
    _progress = SolverProgress(verbose=verbose)
    _progress.start(problem.name)

    all_nodes = problem.all_nodes
    all_nodes_except_deposit = problem.delivery_nodes + problem.recovery_nodes
    vehicules = list(problem.vehicles_dict.values())

    n_nodes = len(all_nodes)
    n_vehicles = len(vehicules)
    n_edges = n_nodes * n_nodes * n_vehicles

    # === CREATE VARIABLES ===
    _progress.phase("Creating decision variables", f"~{n_edges} edge vars")

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
    _progress.phase_done(f"{len(indices)} binary vars")

    _progress.phase("Creating time variables")
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
    time_departure_deposit = pulp.LpVariable.dicts(
        "time_departure_deposit",
        [vehicule.id for vehicule in vehicules],
        lowBound=0,
        cat="Continuous",
    )
    _progress.phase_done()


    # ===   ===     ===     ===     LOADS
    _progress.phase("Creating load variables")
    loads_departure_deposit = pulp.LpVariable.dicts(
        "load_departure_depot",
        [vehicule.id for vehicule in problem.vehicles_dict.values()],
        lowBound=0,
        cat="Continuous",
    )
    loads_at_arrival = pulp.LpVariable.dicts(
        "load_at_arrival",
        [(node.get_id_for_pulp(), vehicule.id) for node in all_nodes for vehicule in vehicules],
        lowBound=0,
        cat="Continuous",
    )
    _progress.phase_done()

    # ===   ===     ===     ===     VEHICLE ACTIVATION
    _progress.phase("Creating vehicle activation variables")
    is_vehicule_active = pulp.LpVariable.dicts(
        "is_vehicule_active",
        [vehicule.id for vehicule in vehicules],
        cat="Binary",
    )
    _progress.phase_done()

    pulp_problem = pulp.LpProblem(problem.name, pulp.LpMinimize)

    #===    ===     ===     ===     SET UP CONSTRAINTS
    pulp_problem = _add_constraints(
        pulp_problem=pulp_problem,
        problem=problem,
        #   SELECTION
        choose_edges=choose_edges,
        #   TIMES
        times_arrival=times_arrival,
        time_arrival_deposit=time_arrival_deposit,
        time_departure_deposit=time_departure_deposit,
        #   LOADS
        loads_at_arrival=loads_at_arrival,
        loads_departure_deposit=loads_departure_deposit,
        #   ACTIVATION
        is_vehicule_active=is_vehicule_active,
    )

    #===    ===     ===     ===     OBJECTIVE / LOSS FUNCTION
    _progress.phase("Setting up objective function", f"{problem.loss_function.__class__.__name__}")
    loss_function = problem.loss_function
    pulp_problem = loss_function.set_up_loss(
        pulp_problem=pulp_problem, problem=problem, choose_edges=choose_edges,
    )
    _progress.phase_done()

    # Summary
    n_vars = len(pulp_problem.variables())
    n_constraints = len(pulp_problem.constraints)
    if _progress.verbose:
        c = _progress.COLORS
        print(f"\n{c['cyan']}📊 Model size: {n_vars} variables, {n_constraints} constraints{c['reset']}\n")

    return pulp_problem, choose_edges


def solve_with_progress(
    pulp_problem: pulp.LpProblem,
    problem: "Problem" = None,
    choose_edges: dict = None,
    verbose: bool = True,
    time_limit: int = None,
    threads: int = None,
    warm_start: bool = True,
) -> int:
    """Solve the PuLP problem with progress logging and optional warm start.

    Args:
        pulp_problem: The PuLP problem to solve.
        problem: The Problem instance (needed for warm start heuristic).
        choose_edges: The edge decision variables dict (needed for warm start).
        verbose: If True, show CBC solver output and progress.
        time_limit: Optional time limit in seconds. Defaults to MAX_WAIT_TIME.
        threads: Optional number of threads to use.
        warm_start: If True, build a greedy initial solution before solving.

    Returns:
        The PuLP status code.

    Raises:
        SolverTimeoutError: If solver times out without finding any feasible solution.
    """
    global _progress

    # Use MAX_WAIT_TIME as default time limit
    if time_limit is None:
        time_limit = MAX_WAIT_TIME

    # Build greedy initial solution if requested
    use_warm_start = warm_start and problem is not None and choose_edges is not None
    if use_warm_start:
        greedy_initial_solution(problem, choose_edges, verbose=verbose)

    _progress.solving_start()

    # Configure CBC solver options
    solver_options = []
    solver_options.append(f"sec {time_limit}")
    if threads:
        solver_options.append(f"threads {threads}")

    solver = pulp.PULP_CBC_CMD(
        msg=verbose,
        warmStart=use_warm_start,  # Enable warm start in CBC
        options=solver_options,
    )

    status = pulp_problem.solve(solver)
    objective = pulp.value(pulp_problem.objective)

    # Check result status
    status_str = pulp.LpStatus[status]

    if status == pulp.LpStatusOptimal:
        # Optimal solution found
        _progress.solving_done(status_str, objective)
    elif status == pulp.LpStatusNotSolved:
        # Timeout with no feasible solution
        c = _progress.COLORS if verbose else {k: '' for k in SolverProgress.COLORS}
        print(f"\n{c['bold']}{c['red']}╔══════════════════════════════════════════════════════════════════╗{c['reset']}")
        print(f"{c['bold']}{c['red']}║{c['reset']}  ❌ Solver timed out after {time_limit}s - NO FEASIBLE SOLUTION          {c['bold']}{c['red']}║{c['reset']}")
        print(f"{c['bold']}{c['red']}╚══════════════════════════════════════════════════════════════════╝{c['reset']}\n")
        raise SolverTimeoutError(f"Solver exceeded {time_limit}s without finding any feasible solution.")
    elif objective is not None:
        # Suboptimal but feasible solution (e.g., timeout with incumbent)
        c = _progress.COLORS if verbose else {k: '' for k in SolverProgress.COLORS}
        print(f"\n{c['bold']}{c['yellow']}╔══════════════════════════════════════════════════════════════════╗{c['reset']}")
        print(f"{c['bold']}{c['yellow']}║{c['reset']}  ⚠️  Solver timed out - returning SUBOPTIMAL solution             {c['bold']}{c['yellow']}║{c['reset']}")
        print(f"{c['bold']}{c['yellow']}║{c['reset']}  Status: {status_str:<55} {c['bold']}{c['yellow']}║{c['reset']}")
        print(f"{c['bold']}{c['yellow']}║{c['reset']}  Objective: {c['cyan']}{objective:<52.4f}{c['reset']} {c['bold']}{c['yellow']}║{c['reset']}")
        print(f"{c['bold']}{c['yellow']}╚══════════════════════════════════════════════════════════════════╝{c['reset']}\n")
    else:
        # Infeasible or other error
        c = _progress.COLORS if verbose else {k: '' for k in SolverProgress.COLORS}
        print(f"\n{c['bold']}{c['red']}╔══════════════════════════════════════════════════════════════════╗{c['reset']}")
        print(f"{c['bold']}{c['red']}║{c['reset']}  ❌ Solver failed: {status_str:<44} {c['bold']}{c['red']}║{c['reset']}")
        print(f"{c['bold']}{c['red']}╚══════════════════════════════════════════════════════════════════╝{c['reset']}\n")
        raise SolverTimeoutError(f"Solver failed with status: {status_str}")

    return status




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

