#!/usr/bin/env python3
"""Quick test to debug dual extraction with logging enabled."""
import sys
import os
import json

# Add backend/ to sys.path just like VRPPD.py does
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Now we can import from solver.solver
from solver.solver.problem import Problem, TimeMargin, build_problem
from solver.solver.loss_functions import BaselineLoss
from solver.solver.lip_solver import build_pulp_problem, solve_with_progress
from solver.viz_loss import viz_convergence

# Load data
data_path = os.path.join(backend_dir, "solver", "vrppd_data.json")
print(f"Loading data from {data_path}")
with open(data_path, 'r') as f:
    data = json.load(f)

print(f"Loaded {len(data['vehicles'])} vehicles, {len(data['locations'])} locations")

# Build problem
loss_function = BaselineLoss(alpha_time=1.0, alpha_distance=1.0, alpha_load=1.0)
time_margin = TimeMargin(before_concert=15, after_concert=20, before_closing=30)
problem = build_problem(data, loss_function, time_margin, recall_api=False)

# Build PuLP
print("\nBuilding PuLP problem...")
pulp_problem, choose_edges = build_pulp_problem(problem, verbose=False)

# Solve with logging to stderr
print("Solving... (debugging output will appear below)")
solve_with_progress(
    pulp_problem,
    problem=problem,
    choose_edges=choose_edges,
    verbose=False,
    warm_start=True,
)

# Now generate viz which will show debug output
print("\nGenerating visualization (will show dual extraction debug)...")
output_file = os.path.join(backend_dir, "solver", "solution", "convergence_debug.html")
try:
    html_path = viz_convergence(
        pulp_problem,
        problem,
        solve_time=1.0,  # dummy time
        output_file=output_file
    )
    print(f"\n✓ Visualization generated: {html_path}")
except Exception as e:
    print(f"\n✗ Visualization failed: {e}")
    import traceback
    traceback.print_exc()
