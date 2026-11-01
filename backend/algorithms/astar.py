"""A* shortest-path optimizer for multimodal graphs."""

from __future__ import annotations

import math

import networkx as nx

from .common import (
    ObjectiveName,
    OptimizationResult,
    ensure_endpoints,
    result_from_route,
    validate_objective,
)


def _heuristic(
    graph: nx.MultiDiGraph, node: str, destination: str, objective: ObjectiveName
) -> float:
    first = graph.nodes[node]
    second = graph.nodes[destination]
    lat_delta = float(first["latitude"]) - float(second["latitude"])
    lon_delta = float(first["longitude"]) - float(second["longitude"])
    distance = math.sqrt(lat_delta**2 + lon_delta**2)
    # The generated edge costs have positive lower bounds per km, so this is a
    # conservative geographic lower bound for each supported objective.
    lower_bounds = {"cost": 0.60, "time": 1 / 160, "emissions": 0.030}
    return distance * lower_bounds[objective]


def astar_search(
    graph: nx.MultiDiGraph,
    source: str,
    destination: str,
    objective: str,
) -> OptimizationResult:
    selected_objective: ObjectiveName = validate_objective(objective)
    ensure_endpoints(graph, source, destination)
    attributes = {
        "cost": "cost",
        "time": "travel_time_hours",
        "emissions": "carbon_emissions_kg",
    }
    try:
        nodes = nx.astar_path(
            graph,
            source,
            destination,
            heuristic=lambda node, target: _heuristic(
                graph, node, target, selected_objective
            ),
            weight=lambda u, v, data: min(
                float(edge[attributes[selected_objective]]) for edge in data.values()
            ),
        )
    except nx.NetworkXNoPath as exc:
        raise ValueError(f"No route from {source} to {destination}") from exc
    return result_from_route(
        "astar", selected_objective, source, destination, graph, nodes,
        metadata={"heuristic": "geographic_admissible_lower_bound"},
    )
