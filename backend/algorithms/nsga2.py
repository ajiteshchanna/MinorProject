"""Single-objective route optimization using pymoo's NSGA-II engine."""

from __future__ import annotations

import numpy as np
import networkx as nx
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.core.problem import ElementwiseProblem
from pymoo.optimize import minimize

from .common import (
    ObjectiveName,
    OptimizationResult,
    ensure_endpoints,
    result_from_route,
    route_from_waypoints,
    validate_objective,
)


class _WaypointProblem(ElementwiseProblem):
    def __init__(
        self,
        graph: nx.MultiDiGraph,
        source: str,
        destination: str,
        objective: ObjectiveName,
        waypoints: list[str],
        waypoint_count: int,
    ) -> None:
        self.graph = graph
        self.source = source
        self.destination = destination
        self.objective = objective
        self.waypoints = waypoints
        super().__init__(
            n_var=waypoint_count,
            n_obj=1,
            n_ieq_constr=1,
            xl=0,
            xu=max(0, len(waypoints) - 1),
            vtype=int,
        )

    def _evaluate(self, x: np.ndarray, out: dict[str, np.ndarray], *args: object, **kwargs: object) -> None:
        selected = [self.waypoints[int(index)] for index in x]
        duplicate_count = len(selected) - len(set(selected))
        out["G"] = np.array([duplicate_count], dtype=float)
        if duplicate_count:
            out["F"] = 1e15
            return
        nodes = [self.source] + selected + [self.destination]
        try:
            _, _, _, value = route_from_waypoints(self.graph, nodes, self.objective)
        except nx.NetworkXNoPath:
            value = 1e15
        out["F"] = value


def nsga2_optimize(
    graph: nx.MultiDiGraph,
    source: str,
    destination: str,
    objective: str,
    *,
    seed: int = 7,
    population_size: int = 40,
    generations: int = 30,
    waypoint_count: int = 2,
) -> OptimizationResult:
    selected_objective: ObjectiveName = validate_objective(objective)
    ensure_endpoints(graph, source, destination)
    if population_size < 2 or generations < 1 or waypoint_count < 1:
        raise ValueError("population_size, generations and waypoint_count must be positive")
    waypoints = [node for node in graph if node not in {source, destination}]
    if not waypoints:
        return result_from_route("nsga2", selected_objective, source, destination, graph, [source, destination])
    problem = _WaypointProblem(
        graph, source, destination, selected_objective, waypoints, waypoint_count
    )
    result = minimize(
        problem,
        NSGA2(pop_size=population_size),
        termination=("n_gen", generations),
        seed=seed,
        save_history=True,
        verbose=False,
    )
    chromosome = np.atleast_1d(result.X[0] if np.ndim(result.X) > 1 else result.X)
    selected = [waypoints[int(index)] for index in chromosome]
    fallback = False
    try:
        route_nodes, _, _, _ = route_from_waypoints(
            graph, [source] + selected + [destination], selected_objective
        )
    except nx.NetworkXNoPath:
        route_nodes, _, _, _ = route_from_waypoints(
            graph, [source, destination], selected_objective
        )
        fallback = True
    convergence = tuple(
        float(np.min(np.asarray(history.opt.get("F"))))
        for history in result.history
    )
    evaluator = getattr(getattr(result, "algorithm", None), "evaluator", None)
    function_evaluations = int(
        getattr(evaluator, "n_eval", population_size * generations)
    )
    return result_from_route(
        "nsga2",
        selected_objective,
        source,
        destination,
        graph,
        route_nodes,
        iterations=generations,
        metadata={
            "seed": seed,
            "population_size": population_size,
            "waypoint_count": waypoint_count,
            "function_evaluations": function_evaluations,
            "feasible_chromosome": not fallback,
            "convergence": convergence,
        },
    )
