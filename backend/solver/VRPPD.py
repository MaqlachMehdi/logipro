import json
import argparse
from time import time_ns
import pulp


# import solver
from solver.solver.problem import Problem,TimeMargin,build_problem

from solver.solver.lip_solver import build_pulp_problem

DEBUG          = 0
RECALL_MAP_API = 0   # set to 1 to force fresh API calls and overwrite the cache

# Safety margins (minutes)
MARGIN_BEFORE_CONCERT  = 15   # buffer before concert start
MARGIN_AFTER_CONCERT   = 20   # possible concert delay
MARGIN_BEFORE_CLOSING  = 30   # cannot arrive too close to closing time


# ──────────────────────────────────────────────────────────────────────────────
# ANSI color codes for terminal output
# ──────────────────────────────────────────────────────────────────────────────
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    # Background colors
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"


def _hhmm(minutes: float | None) -> str:
    """Format minutes as HH:MM."""
    if minutes is None:
        return "—"
    return f"{int(minutes) // 60:02d}:{int(minutes) % 60:02d}"


def print_verbose_results(result, problem):
    """Print extensive solver results with colored output."""
    c = Colors

    print(f"\n{c.BOLD}{c.CYAN}{'═' * 80}{c.RESET}")
    print(f"{c.BOLD}{c.CYAN}                        VERBOSE SOLVER RESULTS{c.RESET}")
    print(f"{c.BOLD}{c.CYAN}{'═' * 80}{c.RESET}\n")

    # ── Summary ──────────────────────────────────────────────────────────────
    print(f"{c.BOLD}{c.WHITE}┌─ SOLUTION SUMMARY ─────────────────────────────────────────────┐{c.RESET}")
    status = pulp.LpStatus[result.pulp_problem.status]
    status_color = c.GREEN if status == "Optimal" else c.YELLOW
    obj_val = pulp.value(result.pulp_problem.objective)
    obj_str = f"{obj_val:.4f}" if obj_val is not None else "N/A"
    print(f"{c.WHITE}│{c.RESET}  Status:    {status_color}{c.BOLD}{status}{c.RESET}")
    print(f"{c.WHITE}│{c.RESET}  Objective: {c.CYAN}{obj_str}{c.RESET}")
    print(f"{c.WHITE}│{c.RESET}  Vehicles:  {c.CYAN}{len(result.data)}{c.RESET} active / {len(problem.vehicles_dict)} total")
    print(f"{c.WHITE}└────────────────────────────────────────────────────────────────┘{c.RESET}\n")

    # ── Per-vehicle trajectories ─────────────────────────────────────────────
    for plate, trajectory in result.data.items():
        vehicle = problem.vehicles_dict[plate]

        print(f"{c.BOLD}{c.MAGENTA}┌─ VEHICLE: {plate} ─────────────────────────────────────────────┐{c.RESET}")
        print(f"{c.MAGENTA}│{c.RESET}  Capacity: {c.YELLOW}{vehicle.max_volume:.2f} m³{c.RESET}")

        # Depot departure info
        dep_time = result.get_depot_departure_time(plate)
        dep_load = result.get_depot_departure_load(plate)
        print(f"{c.MAGENTA}│{c.RESET}  Departs depot at {c.GREEN}{_hhmm(dep_time)}{c.RESET} with {c.YELLOW}{dep_load:.2f} m³{c.RESET} ({dep_load/vehicle.max_volume*100:.0f}% full)")

        # Build ordered nodes
        ordered = [trajectory.departure_nodes[0]] + list(trajectory.arrival_nodes)

        print(f"{c.MAGENTA}│{c.RESET}")
        print(f"{c.MAGENTA}│{c.RESET}  {c.BOLD}Route ({len(ordered)} stops):{c.RESET}")

        for idx, node in enumerate(ordered):
            node_key = node.get_id_for_pulp()
            is_depot = hasattr(node, '__class__') and node.__class__.__name__ == 'DepositNode'

            # Volume change at this node
            vol_change = getattr(node, 'required_volume', 0) or 0

            # === POST-PROCESS: Compute times and loads ===
            if is_depot and idx == 0:
                # Departure from depot
                arr_time = dep_time
                dep_time_node = dep_time
                load = dep_load
                node_type = "DEPOT"
                type_color = c.WHITE
            elif is_depot:
                # Return to depot: compute load from previous node
                arr_time = result.get_depot_arrival_time(plate)
                prev_node = ordered[idx - 1]
                prev_key = prev_node.get_id_for_pulp()
                prev_load = result.get_load_at_arrival(prev_key, plate) or 0
                prev_vol = getattr(prev_node, 'required_volume', 0) or 0
                load = prev_load - prev_vol  # load after operation at previous node
                dep_time_node = None  # no departure from final depot
                node_type = "DEPOT"
                type_color = c.WHITE
            else:
                arr_time = result.get_arrival_time(node_key, plate)
                load = result.get_load_at_arrival(node_key, plate)
                # Compute departure time = arrival at next node - travel time
                if idx < len(ordered) - 1:
                    next_node = ordered[idx + 1]
                    next_key = next_node.get_id_for_pulp()
                    travel = problem.oriented_edges.travel_times_min.get((node.id, next_node.id)) or 0
                    if next_node.__class__.__name__ == 'DepositNode':
                        next_arr = result.get_depot_arrival_time(plate)
                    else:
                        next_arr = result.get_arrival_time(next_key, plate)
                    dep_time_node = (next_arr - travel) if next_arr is not None else None
                else:
                    dep_time_node = None

                if node.__class__.__name__ == 'DeliveryNode':
                    node_type = "DELIVERY"
                    type_color = c.BLUE
                else:
                    node_type = "RECOVERY"
                    type_color = c.RED

            # Compute arrival and departure loads
            arr_load = load if load is not None else 0
            dep_load_node = arr_load - vol_change  # load after operation

            # Format arrival load bar (yellow)
            arr_pct = arr_load / vehicle.max_volume * 100 if vehicle.max_volume > 0 else 0
            arr_bar_len = int(arr_pct / 5)  # 20 chars = 100%
            arr_bar = "█" * arr_bar_len + "░" * (20 - arr_bar_len)

            # Format departure load bar (purple)
            dep_pct = dep_load_node / vehicle.max_volume * 100 if vehicle.max_volume > 0 else 0
            dep_bar_len = int(dep_pct / 5)
            dep_bar = "█" * dep_bar_len + "░" * (20 - dep_bar_len)

            # Volume change string
            if vol_change > 0:
                vol_str = f"{c.BLUE}↓ -{vol_change:.2f} m³{c.RESET}"  # delivery = drop off
            elif vol_change < 0:
                vol_str = f"{c.RED}↑ +{abs(vol_change):.2f} m³{c.RESET}"  # recovery = pick up
            else:
                vol_str = ""

            # Time window
            tw = getattr(node, 'time_window', None)
            tw_str = f"[{_hhmm(tw.start_minutes)}-{_hhmm(tw.end_minutes)}]" if tw else ""

            # Format times
            arr_str = _hhmm(arr_time) if arr_time is not None else "—"
            dep_str = _hhmm(dep_time_node) if dep_time_node is not None else "—"

            print(f"{c.MAGENTA}│{c.RESET}    {c.DIM}{idx:2d}.{c.RESET} {type_color}{c.BOLD}{node_type:8s}{c.RESET} "
                  f"id={c.CYAN}{node.id}{c.RESET}  "
                  f"arr {c.GREEN}{arr_str}{c.RESET} → dep {c.GREEN}{dep_str}{c.RESET} {c.DIM}{tw_str}{c.RESET}")

            # Show single bar for depot, double bar for other nodes
            if is_depot:
                print(f"{c.MAGENTA}│{c.RESET}        Load: [{c.YELLOW}{arr_bar}{c.RESET}] {arr_load:6.2f} m³ ({arr_pct:5.1f}%)")
            else:
                print(f"{c.MAGENTA}│{c.RESET}        Arr:  [{c.YELLOW}{arr_bar}{c.RESET}] {arr_load:6.2f} m³ ({arr_pct:5.1f}%)  {vol_str}")
                print(f"{c.MAGENTA}│{c.RESET}        Dep:  [{c.MAGENTA}{dep_bar}{c.RESET}] {dep_load_node:6.2f} m³ ({dep_pct:5.1f}%)")

            # Show edge info to next node
            if idx < len(ordered) - 1:
                next_node = ordered[idx + 1]
                dist = problem.oriented_edges.distances_km.get((node.id, next_node.id))
                travel = problem.oriented_edges.travel_times_min.get((node.id, next_node.id))

                # Calculate transported load (after operation at current node)
                transported = arr_load - vol_change

                print(f"{c.MAGENTA}│{c.RESET}        {c.DIM}└──▶ {dist:.1f} km, {travel:.0f} min, carrying {transported:.2f} m³{c.RESET}")

        print(f"{c.MAGENTA}└────────────────────────────────────────────────────────────────┘{c.RESET}\n")

    # ── Raw PuLP Variables (selected) ────────────────────────────────────────
    print(f"{c.BOLD}{c.YELLOW}┌─ RAW PULP VARIABLES (non-zero) ───────────────────────────────┐{c.RESET}")

    # Group variables by type
    edge_vars = []
    load_vars = []
    time_vars = []
    other_vars = []

    for var in result.pulp_problem.variables():
        val = var.varValue
        if val is None or abs(val) < 1e-6:
            continue
        name = var.name
        if name.startswith("e_"):
            edge_vars.append((name, val))
        elif "load" in name.lower():
            load_vars.append((name, val))
        elif "time" in name.lower():
            time_vars.append((name, val))
        else:
            other_vars.append((name, val))

    print(f"{c.YELLOW}│{c.RESET}")
    print(f"{c.YELLOW}│{c.RESET}  {c.BOLD}{c.GREEN}EDGE DECISIONS (e_*):{c.RESET}")
    for name, val in sorted(edge_vars):
        print(f"{c.YELLOW}│{c.RESET}    {c.DIM}{name}{c.RESET} = {c.GREEN}{val:.0f}{c.RESET}")

    print(f"{c.YELLOW}│{c.RESET}")
    print(f"{c.YELLOW}│{c.RESET}  {c.BOLD}{c.BLUE}LOAD VARIABLES:{c.RESET}")
    for name, val in sorted(load_vars):
        print(f"{c.YELLOW}│{c.RESET}    {c.DIM}{name}{c.RESET} = {c.BLUE}{val:.4f}{c.RESET}")

    print(f"{c.YELLOW}│{c.RESET}")
    print(f"{c.YELLOW}│{c.RESET}  {c.BOLD}{c.CYAN}TIME VARIABLES:{c.RESET}")
    for name, val in sorted(time_vars):
        print(f"{c.YELLOW}│{c.RESET}    {c.DIM}{name}{c.RESET} = {c.CYAN}{val:.2f}{c.RESET} ({_hhmm(val)})")

    if other_vars:
        print(f"{c.YELLOW}│{c.RESET}")
        print(f"{c.YELLOW}│{c.RESET}  {c.BOLD}OTHER VARIABLES:{c.RESET}")
        for name, val in sorted(other_vars):
            print(f"{c.YELLOW}│{c.RESET}    {c.DIM}{name}{c.RESET} = {val:.4f}")

    print(f"{c.YELLOW}└────────────────────────────────────────────────────────────────┘{c.RESET}\n")


if __name__ == "__main__":
    import os as _os
    from solver.visualize import render_html, render_html_terminal

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="VRPPD Solver - Vehicle Routing Problem with Pickup and Delivery")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Display extensive solver results with colored output")
    args = parser.parse_args()

    # 1. Load data from JSON
    data_path = _os.path.join(_os.path.dirname(__file__), "vrppd_data.json")
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 2. Build the domain problem (nodes, edges, vehicles)

    from solver.solver.loss_functions import BaselineLoss, MinTheMaxUseTime,MixedUsedTimeAndTotalDist
    # loss_function = BaselineLoss(alpha_time=1.0, alpha_distance=1.0, alpha_load=1.0)
    # loss_function = MinTheMaxUseTime()

    alpha_time          = .5
    loss_function       = MixedUsedTimeAndTotalDist(alpha_time=alpha_time, alpha_distance=1-alpha_time)
    time_margin         = TimeMargin(before_concert=MARGIN_BEFORE_CONCERT, after_concert=MARGIN_AFTER_CONCERT, before_closing=MARGIN_BEFORE_CLOSING)
    problem             = build_problem(data, loss_function, time_margin, recall_api=RECALL_MAP_API)

    if not args.verbose:
        print(problem)

    # 3. Build the PuLP MILP model
    pulp_problem, choose_edges = build_pulp_problem(problem)

    # 4. Solve
    pulp_problem.solve(pulp.PULP_CBC_CMD(msg=not args.verbose))

    from solver.solver.lip_solver import make_result_from_pulp_result
    result = make_result_from_pulp_result(pulp_problem, problem)

    if args.verbose:
        print_verbose_results(result, problem)
    else:
        print("Status:", pulp.LpStatus[pulp_problem.status])
        pulp_problem.writeLP("debug_model.lp")

        print("Status    :", pulp.LpStatus[pulp_problem.status])
        print("Objective :", pulp.value(pulp_problem.objective))
        print(result)

    # 5. Visualize
    output_path = _os.path.join(_os.path.dirname(__file__), "solution.html")
    render_html(result, data, output_path)

    output_path_terminal = _os.path.join(_os.path.dirname(__file__), "solution_terminal.html")
    render_html_terminal(result, data, output_path_terminal)
