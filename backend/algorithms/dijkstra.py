"""Dijkstra shortest-path optimizer for multimodal graphs."""

from __future__ import annotations

import networkx as nx

from .common import (
    ObjectiveName,
    OptimizationResult,
    ensure_endpoints,
    result_from_route,
    validate_objective,
)


def dijkstra_shortest_path(
    graph: nx.MultiDiGraph,
    source: str,
    destination: str,
    objective: str,
) -> OptimizationResult:
    selected_objective: ObjectiveName = validate_objective(objective)
    ensure_endpoints(graph, source, destination)
    try:
        nodes = nx.shortest_path(
            graph,
            source,
            destination,
            weight=lambda u, v, data: min(
                float(edge[{
                    "cost": "cost",
                    "time": "travel_time_hours",
                    "emissions": "carbon_emissions_kg",
                }[selected_objective]])
                for edge in data.values()
            ),
            method="dijkstra",
        )
    except nx.NetworkXNoPath as exc:
        raise ValueError(f"No route from {source} to {destination}") from exc
    return result_from_route(
        "dijkstra", selected_objective, source, destination, graph, nodes,
        metadata={"path_nodes_explored": "networkx_weighted_shortest_path"},
    )
