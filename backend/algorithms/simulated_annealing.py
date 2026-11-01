"""Route-based simulated annealing optimizer."""

from __future__ import annotations

import math
import random

import networkx as nx

from .common import (
    ObjectiveName,
    OptimizationResult,
    ensure_endpoints,
    result_from_route,
    route_from_waypoints,
    validate_objective,
)


def simulated_annealing(
    graph: nx.MultiDiGraph,
    source: str,
    destination: str,
    objective: str,
    *,
    seed: int = 7,
    iterations: int = 500,
    initial_temperature: float = 100.0,
    cooling_rate: float = 0.995,
) -> OptimizationResult:
    selected_objective: ObjectiveName = validate_objective(objective)
    ensure_endpoints(graph, source, destination)
    if iterations < 1 or initial_temperature <= 0 or not 0 < cooling_rate < 1:
        raise ValueError("Invalid simulated annealing parameters")
    rng = random.Random(seed)
    candidates = [node for node in graph if node not in {source, destination}]
    waypoint_count = min(2, len(candidates))
    current = [source] + rng.sample(candidates, waypoint_count) + [destination]
    try:
        _, _, _, current_value = route_from_waypoints(graph, current, selected_objective)
    except nx.NetworkXNoPath as exc:
        raise ValueError(f"No route from {source} to {destination}") from exc
    best = current[:]
    best_value = current_value
    convergence = [best_value]
    temperature = initial_temperature
    accepted = 0
    for _ in range(iterations):
        candidate = current[:]
        if waypoint_count:
            index = rng.randrange(1, len(candidate) - 1)
            candidate[index] = rng.choice(candidates)
        try:
            _, _, _, candidate_value = route_from_waypoints(
                graph, candidate, selected_objective
            )
        except nx.NetworkXNoPath:
            temperature *= cooling_rate
            continue
        delta = candidate_value - current_value
        if delta < 0 or rng.random() < math.exp(-delta / max(temperature, 1e-12)):
            current, current_value = candidate, candidate_value
            accepted += 1
        if current_value < best_value:
            best, best_value = current[:], current_value
        convergence.append(best_value)
        temperature *= cooling_rate
    return result_from_route(
        "simulated_annealing",
        selected_objective,
        source,
        destination,
        graph,
        route_from_waypoints(graph, best, selected_objective)[0],
        iterations=iterations,
        metadata={
            "seed": seed,
            "accepted_moves": accepted,
            "function_evaluations": iterations + 1,
            "convergence": convergence,
        },
    )
