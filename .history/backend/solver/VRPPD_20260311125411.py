import json
from time import time_ns
import pulp
from models.graph import DepositNode, DeliveryNode, Node, OrientedEdges, RecoveryNode, TimeWindow
from models.vehicules import Vehicle
from models.trajectories import Trajectory


# import solver 
from solver.problem import LossParams, Problem,TimeMargin,build_problem
from solver.solver import build_pulp_problem

DEBUG          = 0
RECALL_MAP_API = 0   # set to 1 to force fresh API calls and overwrite the cache

# Safety margins (minutes)
MARGIN_BEFORE_CONCERT  = 15   # buffer before concert start
MARGIN_AFTER_CONCERT   = 20   # possible concert delay
MARGIN_BEFORE_CLOSING  = 30   # cannot arrive too close to closing time
if __name__ == "__main__":
    import os as _os
    from visualize import render_html

    # 1. Load data from JSON
    data_path = _os.path.join(_os.path.dirname(__file__), "vrppd_data.json")
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 2. Build the domain problem (nodes, edges, vehicles)
    loss_params = LossParams(alpha_time=1.0, alpha_distance=1.0)
    time_margin = TimeMargin(before_concert=MARGIN_BEFORE_CONCERT, after_concert=MARGIN_AFTER_CONCERT, before_closing=MARGIN_BEFORE_CLOSING)
    problem     = build_problem(data, loss_params, time_margin, recall_api=RECALL_MAP_API)

    print(problem)

    # 3. Build the PuLP MILP model
    pulp_problem, choose_edges = build_pulp_problem(problem)

    # 4. Solve
    pulp_problem.solve(pulp.PULP_CBC_CMD(msg=1))

    from solver.solver import Result, make_result_from_pulp_result
    result = make_result_from_pulp_result(pulp_problem, problem)

    print("Status    :", pulp.LpStatus[pulp_problem.status])
    print("Objective :", pulp.value(pulp_problem.objective))
    print(result)

    # 5. Visualize
    output_path = _os.path.join(_os.path.dirname(__file__), "solution.html")
    render_html(result, data, output_path)
