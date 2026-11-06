"""Shared types and route utilities for classical optimizers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal, Sequence

import networkx as nx

ObjectiveName = Literal["cost", "time", "emissions"]
OBJECTIVE_ATTRIBUTES: dict[ObjectiveName, str] = {
    "cost": "cost",
    "time": "travel_time_hours",
    "emissions": "carbon_emissions_kg",
}


@dataclass(frozen=True)
class OptimizationResult:
    """Standard output returned by every classical optimization algorithm."""

    algorithm: str
    objective: ObjectiveName
    source: str
    destination: str
    nodes: tuple[str, ...]
    edge_ids: tuple[str, ...]
    modes: tuple[str, ...]
    objective_value: float
    feasible: bool
    iterations: int = 0
    metadata: dict[str, object] = field(default_factory=dict)


def validate_objective(objective: str) -> ObjectiveName:
    if objective not in OBJECTIVE_ATTRIBUTES:
        raise ValueError(
            f"Unsupported objective {objective!r}; expected cost, time or emissions"
        )
    return objective  # type: ignore[return-value]


def edge_weight(data: dict[str, object], objective: ObjectiveName) -> float:
    return float(data[OBJECTIVE_ATTRIBUTES[objective]])


def best_edge(
    graph: nx.MultiDiGraph, source: str, destination: str, objective: ObjectiveName
) -> tuple[str, dict[str, object]]:
    edges = graph.get_edge_data(source, destination)
    if not edges:
        raise nx.NetworkXNoPath(f"No edge from {source} to {destination}")
    key, data = min(edges.items(), key=lambda item: edge_weight(item[1], objective))
    return str(key), data


def route_from_nodes(
    graph: nx.MultiDiGraph,
    nodes: Sequence[str],
    objective: ObjectiveName,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], float]:
    if len(nodes) < 2:
        raise nx.NetworkXNoPath("A route requires a source and destination")
    if len(set(nodes)) != len(nodes):
        raise nx.NetworkXNoPath("A route cannot revisit a city")
    edge_ids: list[str] = []
    modes: list[str] = []
    total = 0.0
    for source, destination in zip(nodes, nodes[1:]):
        edge_id, data = best_edge(graph, source, destination, objective)
        edge_ids.append(edge_id)
        modes.append(str(data["mode"]))
        total += edge_weight(data, objective)
    return tuple(nodes), tuple(edge_ids), tuple(modes), total


def route_from_waypoints(
    graph: nx.MultiDiGraph,
    waypoints: Sequence[str],
    objective: ObjectiveName,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...], float]:
    """Decode waypoint genes into a feasible route using weighted path segments."""
    if len(waypoints) < 2:
        raise nx.NetworkXNoPath("A route requires a source and destination")
    if len(set(waypoints)) != len(waypoints):
        raise nx.NetworkXNoPath("Waypoint sequence cannot contain duplicates")
    attributes = OBJECTIVE_ATTRIBUTES[objective]
    decoded: list[str] = []
    for source, destination in zip(waypoints, waypoints[1:]):
        segment = nx.shortest_path(
            graph,
            source,
            destination,
            weight=lambda _u, _v, data: min(
                float(edge[attributes]) for edge in data.values()
            ),
            method="dijkstra",
        )
        if decoded:
            decoded.extend(segment[1:])
        else:
            decoded.extend(segment)
    return route_from_nodes(graph, decoded, objective)


def result_from_route(
    algorithm: str,
    objective: ObjectiveName,
    source: str,
    destination: str,
    graph: nx.MultiDiGraph,
    nodes: Sequence[str],
    *,
    iterations: int = 0,
    metadata: dict[str, object] | None = None,
) -> OptimizationResult:
    route_nodes, edge_ids, modes, value = route_from_nodes(graph, nodes, objective)
    return OptimizationResult(
        algorithm=algorithm,
        objective=objective,
        source=source,
        destination=destination,
        nodes=route_nodes,
        edge_ids=edge_ids,
        modes=modes,
        objective_value=value,
        feasible=True,
        iterations=iterations,
        metadata=metadata or {},
    )


def ensure_endpoints(graph: nx.MultiDiGraph, source: str, destination: str) -> None:
    missing = [node for node in (source, destination) if node not in graph]
    if missing:
        raise ValueError(f"Unknown graph node(s): {', '.join(missing)}")
    if source == destination:
        raise ValueError("Source and destination must be different")


Algorithm = Callable[..., OptimizationResult]


def optimize(
    algorithm: str,
    graph: nx.MultiDiGraph,
    source: str,
    destination: str,
    objective: str,
    **kwargs: object,
) -> OptimizationResult:
    """Dispatch an algorithm by name using the shared interface."""
    from .astar import astar_search
    from .ant_colony import ant_colony_optimize
    from .dijkstra import dijkstra_shortest_path
    from .nsga2 import nsga2_optimize
    from .simulated_annealing import simulated_annealing

    algorithms: dict[str, Algorithm] = {
        "dijkstra": dijkstra_shortest_path,
        "astar": astar_search,
        "nsga2": nsga2_optimize,
        "simulated_annealing": simulated_annealing,
        "aco": ant_colony_optimize,
    }
    try:
        selected = algorithms[algorithm]
    except KeyError as exc:
        raise ValueError(f"Unknown algorithm: {algorithm}") from exc
    return selected(graph, source, destination, objective, **kwargs)
