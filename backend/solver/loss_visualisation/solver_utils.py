"""Shared helpers for loading data, solving, and extracting loss components."""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import sys
from dataclasses import dataclass
from time import perf_counter

import pulp

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from solver.solver.lip_solver import build_pulp_problem, greedy_initial_solution
from solver.solver.loss_functions import MixedUsedTotalDistAndTime
from solver.solver.problem import TimeMargin, build_problem

MARGIN_BEFORE_CONCERT = 15
MARGIN_AFTER_CONCERT = 20
MARGIN_BEFORE_CLOSING = 30


def load_data(data_file: str) -> dict:
    """Load and validate the VRPPD JSON input file."""
    with open(data_file, "r", encoding="utf-8") as handle:
        data = json.load(handle)

    data["vehicles"] = [
        v for v in data.get("vehicles", []) if v.get("is_available", 1) != 0
    ]
    if not data["vehicles"]:
        raise ValueError("No available vehicles found in input data.")

    bad = [
        loc.get("name", str(loc.get("id")))
        for loc in data.get("locations", [])
        if loc.get("lat", 0) == 0 and loc.get("lon", 0) == 0
    ]
    if bad:
        raise ValueError("Locations without GPS coordinates: " + ", ".join(bad))

    return data


@dataclass
class LossComponents:
    """Raw (normalized) scalar values of each loss component for a solved solution."""
    time: float
    distance: float
    load: float


def _cache_path(data_file: str) -> str:
    """Return the .bin cache path sitting next to the data file."""
    base, _ = os.path.splitext(data_file)
    return base + "_solve_cache.bin"


def _data_hash(data_file: str) -> str:
    """SHA-256 of the raw JSON file content."""
    with open(data_file, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _load_cache(data_file: str) -> dict:
    path = _cache_path(data_file)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "rb") as f:
            cache = pickle.load(f)
        if cache.get("_data_hash") != _data_hash(data_file):
            print(f"  [cache] data file changed, invalidating cache")
            return {}
        return cache
    except Exception:
        return {}


def _save_cache(data_file: str, cache: dict) -> None:
    cache["_data_hash"] = _data_hash(data_file)
    path = _cache_path(data_file)
    with open(path, "wb") as f:
        pickle.dump(cache, f)


def _cache_key(alpha_time: float, alpha_distance: float, alpha_load: float) -> str:
    return f"{alpha_time:.10f}_{alpha_distance:.10f}_{alpha_load:.10f}"


def solve_and_extract(
    data: dict,
    alpha_time: float,
    alpha_distance: float,
    alpha_load: float,
    time_limit: int = 120,
    threads: int | None = None,
    verbose: bool = True,
    data_file: str | None = None,
) -> tuple[str, LossComponents, float, float, dict[tuple, float]]:
    """Solve the VRPPD for the given alpha weights and return the individual
    normalized loss components of the optimal solution.

    Returns
    -------
    status : str
        PuLP solve status label.
    components : LossComponents
        Normalized scalar for each component, evaluated on the solution.
    solve_time : float
        Wall-clock seconds spent solving.
    raw_objective : float
        The solver's objective value (should match recomputed loss).
    active_edges : dict[tuple, float]
        Mapping of (start_id, end_id, vehicle_id) -> value for edges with
        value >= 0.5 (i.e. selected in the solution).
    """
    # -- check cache --
    key = _cache_key(alpha_time, alpha_distance, alpha_load)
    if data_file is not None:
        cache = _load_cache(data_file)
        if key in cache:
            cached = cache[key]
            print(f"  [cache] HIT for alpha=({alpha_time}, {alpha_distance}, {alpha_load})")
            edges = {(e[0], e[1], e[2]): e[3] for e in cached.get("active_edges", [])}
            return cached["status"], LossComponents(**cached["components"]), cached["solve_time"], cached["raw_objective"], edges

    loss_function = MixedUsedTotalDistAndTime(
        alpha_time=alpha_time,
        alpha_distance=alpha_distance,
        alpha_load=alpha_load,
    )
    time_margin = TimeMargin(
        before_concert=MARGIN_BEFORE_CONCERT,
        after_concert=MARGIN_AFTER_CONCERT,
        before_closing=MARGIN_BEFORE_CLOSING,
    )
    problem = build_problem(data, loss_function, time_margin, recall_api=0)
    pulp_problem, choose_edges = build_pulp_problem(problem, verbose=verbose)

    # Warm-start with greedy heuristic
    greedy_initial_solution(problem, choose_edges, verbose=verbose)

    started_at = perf_counter()

    # Solve with HiGHS (Python API via highspy)
    solver = pulp.HiGHS(
        msg=verbose,
        timeLimit=time_limit,
        threads=threads,
    )
    status_code = pulp_problem.solve(solver)
    status = pulp.LpStatus.get(status_code, str(status_code))

    if status_code == pulp.LpStatusNotSolved or (
        status_code != pulp.LpStatusOptimal and pulp.value(pulp_problem.objective) is None
    ):
        raise RuntimeError("Solver timed out without finding a feasible solution.")

    solve_time = perf_counter() - started_at

    # -- extract individual normalized components from the solved variables ----
    typical_distance = problem.oriented_edges.get_distance_frobenius_norm() or 1.0
    better_min_max_time = problem.oriented_edges.ideal_min_max_time() or 1.0
    mean_load = max(1.0, problem.get_mean_load_per_vehicle())

    # time component: max_use_time / better_min_max_time
    max_use_time_var = pulp_problem.variablesDict().get("max_use_time")
    time_component = (max_use_time_var.varValue / better_min_max_time) if max_use_time_var else 0.0

    # distance component
    distance_val = 0.0
    load_dist_val = 0.0
    for node_start in problem.all_nodes:
        for node_end in problem.all_nodes:
            if node_start == node_end:
                continue
            dist_km = problem.oriented_edges.distances_km[(node_start.id, node_end.id)]
            for vehicule in problem.vehicles_dict.values():
                edge_var = choose_edges[
                    node_start.get_id_for_pulp(),
                    node_end.get_id_for_pulp(),
                    vehicule.id,
                ]
                edge_val = edge_var.varValue or 0.0
                distance_val += dist_km * edge_val
                load_dist_val += dist_km * edge_val * (vehicule.max_volume ** (2 / 3))

    distance_component = distance_val / typical_distance
    load_component = load_dist_val / (typical_distance * mean_load)

    # raw objective from the solver (for sanity check)
    raw_objective = float(pulp.value(pulp_problem.objective))

    components = LossComponents(time=time_component, distance=distance_component, load=load_component)

    # -- extract active edges (binary decisions) --
    active_edges: dict[tuple, float] = {}
    for edge_key, edge_var in choose_edges.items():
        val = edge_var.varValue or 0.0
        if val >= 0.5:
            active_edges[edge_key] = val

    # -- write cache --
    if data_file is not None:
        cache = _load_cache(data_file)
        cache[key] = {
            "status": status,
            "components": {"time": components.time, "distance": components.distance, "load": components.load},
            "solve_time": solve_time,
            "raw_objective": raw_objective,
            "active_edges": [[k[0], k[1], k[2], v] for k, v in active_edges.items()],
        }
        _save_cache(data_file, cache)
        print(f"  [cache] stored alpha=({alpha_time}, {alpha_distance}, {alpha_load})")

    return status, components, solve_time, raw_objective, active_edges
