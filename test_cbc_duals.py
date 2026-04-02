#!/usr/bin/env python3
"""Minimal test to check if CBC exposes constraint duals in PuLP."""
import pulp

# Create a tiny LP problem
prob = pulp.LpProblem("test", pulp.LpMaximize)

# Variables
x = pulp.LpVariable("x", lowBound=0)
y = pulp.LpVariable("y", lowBound=0)

# Objective
prob += x + 2*y, "objective"

# Constraints
prob += x + y <= 5, "constraint1"
prob += 2*x + y <= 8, "constraint2"

# Solve with MIP
print("Solving as MIP...")
prob.solve(pulp.PULP_CBC_CMD(msg=0))
print(f"MIP Status: {pulp.LpStatus[prob.status]}")
print(f"MIP Objective: {pulp.value(prob.objective)}")

# Check constraint.pi for MIP solution
print("\nMIP Constraint Pi values:")
for name, constraint in prob.constraints.items():
    pi = getattr(constraint, "pi", "NOT SET")
    print(f"  {name}: pi={pi}")

# Now try as LP (solve as MIP, then relax and resolve)
prob2 = prob.deepcopy()
prob2.solve(pulp.PULP_CBC_CMD(msg=0, mip=False))
print(f"\nLP Status: {pulp.LpStatus[prob2.status]}")
print(f"LP Objective: {pulp.value(prob2.objective)}")

print("\nLP Constraint Pi values:")
for name, constraint in prob2.constraints.items():
    pi = getattr(constraint, "pi", "NOT SET")
    print(f"  {name}: pi={pi}")

print("\nConclusion:")
if all(getattr(c, "pi", None) is None for c in prob.constraints.values()):
    print("MIP does NOT expose constraint duals (pi=None)")
if any(getattr(c, "pi", None) is not None for c in prob2.constraints.values()):
    print("LP DOES expose constraint duals (pi is set)")
