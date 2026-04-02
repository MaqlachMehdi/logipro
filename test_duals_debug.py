#!/usr/bin/env python3
"""Quick test to debug dual extraction with logging enabled."""
import sys
import os
import json

# Add backend/ to sys.path just like VRPPD.py does
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Install required packages first
import subprocess
packages = ["tqdm", "requests"]
for pkg in packages:
    try:
        __import__(pkg)
    except ImportError:
        print(f"Installing {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

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

# Filter out unavailable vehicles
data['vehicles'] = [v for v in data['vehicles'] if v.get('is_available', 1) != 0]

print(f"Loaded {len(data['vehicles'])} available vehicles, {len(data['locations'])} locations")

# Build problem
loss_function = BaselineLoss(alpha_time=1.0, alpha_distance=1.0, alpha_load=1.0)
time_margin = TimeMargin(before_concert=15, after_concert=20, before_closing=30)
problem = build_problem(data, loss_function, time_margin, recall_api=False)

# Build PuLP
print("\nBuilding PuLP problem...")
pulp_problem, choose_edges = build_pulp_problem(problem, verbose=False)
print(f"  Variables: {len(pulp_problem.variables())}, Constraints: {len(pulp_problem.constraints)}")

# Solve with logging to stderr
print("\nSolving... (debug output coming below)")
print("=" * 80)
solve_with_progress(
    pulp_problem,
    problem=problem,
    choose_edges=choose_edges,
    verbose=False,
    warm_start=True,
)
print("=" * 80)

# Now generate viz which will show debug output
print("\nGenerating visualization (will show dual extraction debug)...")
print("=" * 80)
output_file = os.path.join(backend_dir, "solver", "solution", "convergence_debug.html")
try:
    html_path = viz_convergence(
        pulp_problem,
        problem,
        solve_time=1.0,  # dummy time
        output_file=output_file
    )
    print("=" * 80)
    print(f"\n✓ Visualization generated: {html_path}")
except Exception as e:
    print("=" * 80)
    print(f"\n✗ Visualization failed: {e}")
    import traceback
    traceback.print_exc()

