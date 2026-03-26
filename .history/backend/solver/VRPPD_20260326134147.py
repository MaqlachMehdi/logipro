import json
import argparse
import os as _os
import sys as _sys

# Ensure backend/ (parent of this file's directory) is in sys.path
# so that "solver.solver.*" imports resolve correctly regardless of how the script is invoked
_project_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _project_root not in _sys.path:
    _sys.path.insert(0, _project_root)

from time import time_ns
import pulp


# import solver
from solver.solver.problem import Problem,TimeMargin,build_problem
from solver.solver.loss_functions import MixedUsedTotalDistAndTime
from solver.solver.lip_solver import build_pulp_problem, solve_with_progress, make_result_from_pulp_result

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
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="VRPPD Solver - Vehicle Routing Problem with Pickup and Delivery")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Display extensive solver results with colored output")
    parser.add_argument("--api", action="store_true",
                        help="API mode: read JSON from stdin, output JSON result to stdout")
    args = parser.parse_args()

    from solver.solver.loss_functions import BaselineLoss, MinTheMaxUseTime, MixedUsedTimeAndTotalDist

    if args.api:
        # ── API MODE ────────────────────────────────────────────────────────────
        # Read JSON input from stdin
        data = json.loads(_sys.stdin.read())

        # Filter out unavailable vehicles
        data['vehicles'] = [v for v in data['vehicles'] if v.get('is_available', 1) != 0]

        if not data['vehicles']:
            _sys.stdout.buffer.write((json.dumps({'success': False, 'error': 'Aucun véhicule disponible (is_available=0 pour tous)'}, ensure_ascii=False) + '\n').encode('utf-8'))
            _sys.exit(0)

        # Validate that every location has real GPS coordinates
        bad_locs = [
            loc['name'] for loc in data.get('locations', [])
            if loc.get('lat', 0) == 0 and loc.get('lon', 0) == 0
        ]
        if bad_locs:
            _sys.stdout.buffer.write((json.dumps({
                'success': False,
                'error': (
                    f"Lieux sans coordonnées GPS : {', '.join(bad_locs)}. "
                    "Supprimez-les et re-saisissez une adresse valide dans 'Gestion des lieux'."
                )
            }, ensure_ascii=False) + '\n').encode('utf-8'))
            _sys.exit(0)

        # Redirect stdout → stderr so solver progress output doesn't corrupt the JSON response
        _real_stdout = _sys.stdout
        _sys.stdout = _sys.stderr

        try:
            #loss_function = MixedUsedTotalDistAndTime(alpha_time=0.5, alpha_distance=0.3, alpha_load=0.2)
            #loss_function =MixedUsedTimeAndTotalDist(alpha_time=0.7, alpha_distance=0.3, alpha_load=0.0)
            loss_function = BaselineLoss(alpha_time=1.0, alpha_distance=1.0, alpha_load=1.0)
            time_margin = TimeMargin(
                before_concert=MARGIN_BEFORE_CONCERT,
                after_concert=MARGIN_AFTER_CONCERT,
                before_closing=MARGIN_BEFORE_CLOSING,
            )
            problem = build_problem(data, loss_function, time_margin, recall_api=RECALL_MAP_API)
            pulp_problem, choose_edges = build_pulp_problem(problem, verbose=True)
            solve_with_progress(
                pulp_problem,
                problem=problem,
                choose_edges=choose_edges,
                verbose=True,
                warm_start=True,
            )

            status = pulp.LpStatus[pulp_problem.status]
            if pulp_problem.status != pulp.LpStatusOptimal:
                _sys.stdout = _real_stdout
                _sys.stdout.buffer.write((json.dumps({'success': False, 'error': f'Pas de solution optimale: {status}'}, ensure_ascii=False) + '\n').encode('utf-8'))
                _sys.exit(0)

            result = make_result_from_pulp_result(pulp_problem, problem)

            # Map location id → name for destination labels
            loc_names = {loc['id']: loc['name'] for loc in data['locations']}
            config_label = data.get('config', 'equilibre')

            from solver.models.graph import DeliveryNode as _DeliveryNode

            details_vehicules = []
            total_time = 0.0
            total_distance = 0.0

            for plate, trajectory in result.data.items():
                ordered = [trajectory.departure_nodes[0]] + list(trajectory.arrival_nodes)

                destinations = [
                    loc_names.get(node.id, str(node.id))
                    for node in trajectory.arrival_nodes
                    if isinstance(node, _DeliveryNode)
                ]

                # Pure travel time (sum of edge durations, not mission elapsed time)
                vehicle_travel = sum(
                    problem.oriented_edges.travel_times_min.get((ordered[i].id, ordered[i + 1].id), 0) or 0
                    for i in range(len(ordered) - 1)
                )

                vehicle_dist = sum(
                    problem.oriented_edges.distances_km.get((ordered[i].id, ordered[i + 1].id), 0) or 0
                    for i in range(len(ordered) - 1)
                )

                # Build per-step details for the UI
                etapes = []
                for i in range(len(ordered) - 1):
                    n_from = ordered[i]
                    n_to   = ordered[i + 1]
                    step_dist   = problem.oriented_edges.distances_km.get((n_from.id, n_to.id), 0) or 0
                    step_travel = problem.oriented_edges.travel_times_min.get((n_from.id, n_to.id), 0) or 0
                    etapes.append({
                        'de':          loc_names.get(n_from.id, str(n_from.id)),
                        'vers':        loc_names.get(n_to.id,   str(n_to.id)),
                        'dist_km':     round(step_dist,   2),
                        'trajet_min':  round(step_travel, 1),
                    })

                total_time     += vehicle_travel
                total_distance += vehicle_dist

                details_vehicules.append({
                    'nom': plate,
                    'destinations': destinations,
                    'temps_min': round(vehicle_travel, 1),
                    'distance_km': round(vehicle_dist, 2),
                    'etapes': etapes,
                })

            # ── DEBUG: print per-vehicle summary to stderr ───────────────────
            sep = "-" * 60
            print(f"\n{sep}", file=_sys.stderr)
            print(f"  RESULTATS SOLVEUR -- {len(result.data)} vehicule(s)", file=_sys.stderr)
            print(sep, file=_sys.stderr)
            for v in details_vehicules:
                dest_str = " -> ".join(v['destinations']) if v['destinations'] else "(aucune livraison)"
                print(f"  {v['nom']:<20}  {v['temps_min']:>6.1f} min  {v['distance_km']:>6.2f} km", file=_sys.stderr)
                print(f"    {dest_str}", file=_sys.stderr)
            print(sep, file=_sys.stderr)
            print(f"  TOTAL  {total_time:>6.1f} min  {total_distance:>6.2f} km  |  objectif={round(pulp.value(pulp_problem.objective), 4)}", file=_sys.stderr)
            print(f"{sep}\n", file=_sys.stderr)
            # ─────────────────────────────────────────────────────────────────

            # ── Generate HTML files (same as CLI mode) ───────────────────────
            from solver.visualize import render_html_terminal, render_html_multi
            _solver_dir = _os.path.dirname(__file__)
            _obj_val = pulp.value(pulp_problem.objective)
            _status  = pulp.LpStatus[pulp_problem.status]
            render_html_multi(result, data, _os.path.join(_solver_dir, "solution"),
                              solve_status=_status, objective_value=_obj_val)
            render_html_terminal(result, data, _os.path.join(_solver_dir, "solution_terminal.html"),
                                 solve_status=_status, objective_value=_obj_val)
            print("[api] HTML genere : solution_terminal.html + solution/", file=_sys.stderr)
            # ─────────────────────────────────────────────────────────────────

            # ── Enrich details_vehicules with per-stop data from roadmap ─────
            from solver.visualize import _build_roadmap_data
            roadmaps = _build_roadmap_data(result, data)
            roadmap_by_plate = {rm['plate']: rm for rm in roadmaps}
            for veh in details_vehicules:
                rm = roadmap_by_plate.get(veh['nom'], {})
                veh['arrets'] = rm.get('stops', [])
                veh['capacite_m3'] = rm.get('capacity', 0)
            # ─────────────────────────────────────────────────────────────────

            output = {
                'success': True,
                'solution': {
                    'label': config_label,
                    'nb_vehicules': len(result.data),
                    'temps_total_min': round(total_time, 1),
                    'distance_totale_km': round(total_distance, 2),
                    'objectif': round(pulp.value(pulp_problem.objective), 2),
                    'details_vehicules': details_vehicules,
                },
            }

        except Exception as _e:
            output = {'success': False, 'error': str(_e)}

        _sys.stdout = _real_stdout
        _sys.stdout.buffer.write((json.dumps(output, ensure_ascii=False) + '\n').encode('utf-8'))

    else:
        # ── CLI MODE ────────────────────────────────────────────────────────────
        from solver.visualize import render_html, render_html_terminal, render_html_multi

        # 1. Load data from JSON
        data_path = _os.path.join(_os.path.dirname(__file__), "vrppd_data.json")
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 2. Build the domain problem (nodes, edges, vehicles)

        # loss_function = BaselineLoss(alpha_time=1.0, alpha_distance=1.0, alpha_load=1.0)
        # loss_function = MinTheMaxUseTime()

        alpha_time          = 0.0
        """loss_function       = MixedUsedTimeAndTotalDist(
            alpha_time=alpha_time,
            alpha_distance=0,
            alpha_load=1-alpha_time,
            )

        loss_function = MinTheMaxUseTime()"""

        loss_function = MixedUsedTotalDistAndTime(alpha_time=0.5, alpha_distance=0.3, alpha_load=0.2)

        time_margin         = TimeMargin(before_concert=MARGIN_BEFORE_CONCERT, after_concert=MARGIN_AFTER_CONCERT, before_closing=MARGIN_BEFORE_CLOSING)
        problem             = build_problem(data, loss_function, time_margin, recall_api=RECALL_MAP_API)

        if not args.verbose:
            print(problem)

        # 3. Build the PuLP MILP model (with progress logging)
        pulp_problem, choose_edges = build_pulp_problem(problem, verbose=True)

        # 4. Solve with greedy warm start
        solve_with_progress(
            pulp_problem,
            problem=problem,
            choose_edges=choose_edges,
            verbose=True,
            warm_start=True,  # Use greedy heuristic for initial solution
        )

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
        # Multi-file dark mode (grey/orange/purple)
        output_dir = _os.path.join(_os.path.dirname(__file__), "solution")
        render_html_multi(result, data, output_dir)

        # Terminal style (single file)
        output_path_terminal = _os.path.join(_os.path.dirname(__file__), "solution_terminal.html")
        render_html_terminal(result, data, output_path_terminal)
