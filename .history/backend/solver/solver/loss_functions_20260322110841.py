from __future__ import annotations

from typing import TYPE_CHECKING

import pulp

if TYPE_CHECKING:
    from solver.solver.problem import Problem

class LossFunction:
    def __init__(self, name: str):
        self.name = name
    
class BaselineLoss(LossFunction):
    def __init__(self,
                alpha_time      :float,
                alpha_distance  :float,
                alpha_load      :float,
                ):
        super().__init__("baseline_loss")

        self.alpha_time = alpha_time
        self.alpha_distance = alpha_distance
        self.alpha_load = alpha_load


    def set_up_loss(self,
            pulp_problem: pulp.LpProblem,
            problem:      Problem,
            choose_edges: dict,)-> pulp.LpProblem:

        

        # Objective: minimize total active time (arrival - departure for each vehicle)
        # Inactive vehicles have arrival = departure (enforced by constraints in lip_solver.py)
        # so their contribution is 0

        pulp_problem += (
            + self.alpha_time * pulp.lpSum(
                pulp_problem.variablesDict()[f"time_arrival_deposit_{vehicule.id.replace('-', '_')}"]
                - pulp_problem.variablesDict()[f"time_departure_deposit_{vehicule.id.replace('-', '_')}"]
                for vehicule in problem.vehicles_dict.values()
            )

            + self.alpha_distance * pulp.lpSum(
                problem.oriented_edges.distances_km[(node_start.id, node_end.id)]
                * choose_edges[node_start.get_id_for_pulp(), node_end.get_id_for_pulp(), vehicule.id]
                for node_start in problem.all_nodes
                for node_end in problem.all_nodes
                for vehicule in problem.vehicles_dict.values()
                if node_start != node_end
            )
        )
        return pulp_problem


    
class MinTheMaxUseTime(LossFunction):
    def __init__(self,):
        super().__init__("loss_minimise_the_max_usetime")
    def set_up_loss(self,
            pulp_problem: pulp.LpProblem,
            problem:      Problem,
            choose_edges: dict,)-> pulp.LpProblem:


        # Objective: minimize total active time (arrival - departure for each vehicle)
        # Inactive vehicles have arrival = departure (enforced by constraints in lip_solver.py)
        # so their contribution is 0

        max_use_time = pulp.LpVariable("max_use_time", lowBound=0, cat="Continuous")
        # ADDS LINEAR CONSTRAINS max_use_time >= time_arrival_deposit - time_departure_deposit for each vehicle
        for vehicule in problem.vehicles_dict.values():
            pulp_problem += (
                max_use_time >= pulp_problem.variablesDict()[f"time_arrival_deposit_{vehicule.id.replace('-', '_')}"]
                - pulp_problem.variablesDict()[f"time_departure_deposit_{vehicule.id.replace('-', '_')}"]
            )
        # LOSS 
        pulp_problem +=  max_use_time

        return pulp_problem


class MixedUsedTimeAndTotalDist(LossFunction):
    def __init__(
            self,
            alpha_time      :float,
            alpha_distance  :float,
            alpha_load      :float,
            ):
        super().__init__("loss_minimise_the_max_usetime")
        self.alpha_time = alpha_time
        self.alpha_distance = alpha_distance
        self.alpha_load = alpha_load
    def set_up_loss(self,
            pulp_problem: pulp.LpProblem,
            problem:      Problem,
            choose_edges: dict,)-> pulp.LpProblem:

        

        typical_distance = problem.oriented_edges.get_distance_frobenius_norm()
        better_min_max_time = problem.oriented_edges.ideal_min_max_time()

        max_use_time = pulp.LpVariable("max_use_time", lowBound=0, cat="Continuous")
        # ADDS LINEAR CONSTRAINS max_use_time >= time_arrival_deposit - time_departure_deposit for each vehicle
        for vehicule in problem.vehicles_dict.values():
            pulp_problem += (
                max_use_time >= pulp_problem.variablesDict()[f"time_arrival_deposit_{vehicule.id.replace('-', '_')}"]
                - pulp_problem.variablesDict()[f"time_departure_deposit_{vehicule.id.replace('-', '_')}"]
            )
        # LOSS 
        pulp_problem +=  (
            max_use_time / better_min_max_time * self.alpha_time 
            + pulp.lpSum(
                problem.oriented_edges.distances_km[(node_start.id, node_end.id)]
                * choose_edges[node_start.get_id_for_pulp(), node_end.get_id_for_pulp(), vehicule.id]
                for node_start in problem.all_nodes
                for node_end in problem.all_nodes
                for vehicule in problem.vehicles_dict.values()
                if node_start != node_end
            ) / typical_distance * self.alpha_distance
            + pulp.lpSum(# if edge is active : multiply the distance by the maximum load (to encourage filling the vehicles, that is using lightest vehicules)
                problem.oriented_edges.distances_km[(node_start.id, node_end.id)]
                * choose_edges[node_start.get_id_for_pulp(), node_end.get_id_for_pulp(), vehicule.id]
                * vehicule.max_volume**(2/3) # mimic the conso is sunlinear
                for node_start in problem.all_nodes
                for node_end in problem.all_nodes
                for vehicule in problem.vehicles_dict.values()
                if node_start != node_end
            ) / (typical_distance * problem.get_mean_load_per_vehicle()) * self.alpha_load
        )

        return pulp_problem

class MixedUsedTotalDistAndTime(LossFunction):
    def __init__(self, alpha_time: float, alpha_distance: float, alpha_load: float):
        super().__init__("mixed_used_totaldist_and_time")
        self.alpha_time = alpha_time
        self.alpha_distance = alpha_distance
        self.alpha_load = alpha_load

    def set_up_loss(self, pulp_problem: pulp.LpProblem, problem: Problem, choose_edges: dict) -> pulp.LpProblem:
        typical_distance = problem.oriented_edges.get_distance_frobenius_norm()
        better_min_max_time = problem.oriented_edges.ideal_min_max_time()

        # max use time variable + constraints
        max_use_time = pulp.LpVariable("max_use_time", lowBound=0, cat="Continuous")
        for vehicule in problem.vehicles_dict.values():
            pulp_problem += (
                max_use_time >= pulp_problem.variablesDict()[f"time_arrival_deposit_{vehicule.id.replace('-', '_')}"]
                - pulp_problem.variablesDict()[f"time_departure_deposit_{vehicule.id.replace('-', '_')}"]
            )

        # distance term
        total_distance_term = pulp.lpSum(
            problem.oriented_edges.distances_km[(node_start.id, node_end.id)]
            * choose_edges[node_start.get_id_for_pulp(), node_end.get_id_for_pulp(), vehicule.id]
            for node_start in problem.all_nodes
            for node_end in problem.all_nodes
            for vehicule in problem.vehicles_dict.values()
            if node_start != node_end
        )

        # load-weighted distance term (encourage filling)
        load_dist_term = pulp.lpSum(
            problem.oriented_edges.distances_km[(node_start.id, node_end.id)]
            * choose_edges[node_start.get_id_for_pulp(), node_end.get_id_for_pulp(), vehicule.id]
            * (vehicule.max_volume ** (2/3))
            for node_start in problem.all_nodes
            for node_end in problem.all_nodes
            for vehicule in problem.vehicles_dict.values()
            if node_start != node_end
        )

        # Compose normalized objective
        pulp_problem += (
            (max_use_time / (better_min_max_time or 1.0)) * self.alpha_time
            + (total_distance_term / (typical_distance or 1.0)) * self.alpha_distance
            + (load_dist_term / ((typical_distance or 1.0) * max(1.0, problem.get_mean_load_per_vehicle()))) * self.alpha_load
        )

        return pulp_problem
