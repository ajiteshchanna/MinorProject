"""Ant Colony Optimization for cycle-free multimodal routes."""

from __future__ import annotations

from dataclasses import dataclass
import random

import networkx as nx

from .common import (
    OBJECTIVE_ATTRIBUTES,
    ObjectiveName,
    OptimizationResult,
    ensure_endpoints,
    validate_objective,
)


@dataclass(frozen=True)
class _AntRoute:
    nodes: tuple[str, ...]
    edge_ids: tuple[str, ...]
    modes: tuple[str, ...]
    value: float


def _edge_key(source: str, destination: str, key: object) -> tuple[str, str, str]:
    return source, destination, str(key)


def _weighted_choice(
    options: list[tuple[str, str, dict[str, object]]],
    pheromone: dict[tuple[str, str, str], float],
    source: str,
    objective: ObjectiveName,
    alpha: float,
    beta: float,
    rng: random.Random,
) -> tuple[str, str, dict[str, object]]:
    scores: list[float] = []
    attribute = OBJECTIVE_ATTRIBUTES[objective]
    for destination, key, data in options:
        weight = float(data[attribute])
        trail = pheromone[_edge_key(source, destination, key)]
        scores.append((trail**alpha) * ((1.0 / weight) ** beta))
    total = sum(scores)
    if total <= 0:
        return rng.choice(options)
    threshold = rng.random() * total
    cumulative = 0.0
    for option, score in zip(options, scores):
        cumulative += score
        if cumulative >= threshold:
            return option
    return options[-1]


def _construct_ant_route(
    graph: nx.MultiDiGraph,
    source: str,
    destination: str,
    objective: ObjectiveName,
    pheromone: dict[tuple[str, str, str], float],
    alpha: float,
    beta: float,
    rng: random.Random,
) -> _AntRoute | None:
    attribute = OBJECTIVE_ATTRIBUTES[objective]
    current = source
    visited = {source}
    nodes = [source]
    edge_ids: list[str] = []
    modes: list[str] = []
    value = 0.0

    while current != destination:
        options = [
            (str(target), str(key), data)
            for _, target, key, data in graph.out_edges(current, keys=True, data=True)
            if target not in visited
        ]
        if not options:
            return None
        target, key, data = _weighted_choice(
            options, pheromone, current, objective, alpha, beta, rng
        )
        visited.add(target)
        nodes.append(target)
        edge_ids.append(key)
        modes.append(str(data["mode"]))
        value += float(data[attribute])
        current = target

    return _AntRoute(tuple(nodes), tuple(edge_ids), tuple(modes), value)


def _result_from_ant(
    route: _AntRoute,
    objective: ObjectiveName,
    source: str,
    destination: str,
    iterations: int,
    metadata: dict[str, object],
) -> OptimizationResult:
    return OptimizationResult(
        "aco",
        objective,
        source,
        destination,
        route.nodes,
        route.edge_ids,
        route.modes,
        route.value,
        True,
        iterations=iterations,
        metadata=metadata,
    )


def ant_colony_optimize(
    graph: nx.MultiDiGraph,
    source: str,
    destination: str,
    objective: str,
    *,
    seed: int = 7,
    ants: int = 10,
    iterations: int = 30,
    alpha: float = 1.0,
    beta: float = 2.0,
    evaporation_rate: float = 0.5,
    pheromone_deposit: float = 1.0,
) -> OptimizationResult:
    selected_objective: ObjectiveName = validate_objective(objective)
    ensure_endpoints(graph, source, destination)
    if (
        ants < 1
        or iterations < 1
        or alpha < 0
        or beta < 0
        or not 0 < evaporation_rate < 1
        or pheromone_deposit <= 0
    ):
        raise ValueError("Invalid ant colony optimization parameters")

    rng = random.Random(seed)
    pheromone = {
        _edge_key(source_node, destination_node, key): 1.0
        for source_node, destination_node, key in graph.edges(keys=True)
    }
    best: _AntRoute | None = None
    convergence: list[float] = []
    feasible_ants = 0

    for _ in range(iterations):
        routes: list[_AntRoute] = []
        for _ in range(ants):
            route = _construct_ant_route(
                graph,
                source,
                destination,
                selected_objective,
                pheromone,
                alpha,
                beta,
                rng,
            )
            if route is None:
                continue
            routes.append(route)
            feasible_ants += 1
            if best is None or route.value < best.value:
                best = route

        for key in pheromone:
            pheromone[key] *= 1.0 - evaporation_rate
        for route in routes:
            deposit = pheromone_deposit / max(route.value, 1e-12)
            for source_node, destination_node, edge_id in zip(
                route.nodes, route.nodes[1:], route.edge_ids
            ):
                key = _edge_key(source_node, destination_node, edge_id)
                pheromone[key] += deposit
        convergence.append(best.value if best is not None else 1e15)

    if best is None:
        try:
            fallback_nodes = nx.shortest_path(
                graph,
                source,
                destination,
                weight=lambda _u, _v, data: min(
                    float(edge[OBJECTIVE_ATTRIBUTES[selected_objective]])
                    for edge in data.values()
                ),
                method="dijkstra",
            )
        except nx.NetworkXNoPath as exc:
            raise ValueError(f"No route from {source} to {destination}") from exc
        edge_ids: list[str] = []
        modes: list[str] = []
        value = 0.0
        attribute = OBJECTIVE_ATTRIBUTES[selected_objective]
        for source_node, destination_node in zip(fallback_nodes, fallback_nodes[1:]):
            edges = graph.get_edge_data(source_node, destination_node) or {}
            edge_id, data = min(
                edges.items(), key=lambda item: float(item[1][attribute])
            )
            edge_ids.append(str(edge_id))
            modes.append(str(data["mode"]))
            value += float(data[attribute])
        best = _AntRoute(
            tuple(fallback_nodes), tuple(edge_ids), tuple(modes), value
        )

    return _result_from_ant(
        best,
        selected_objective,
        source,
        destination,
        iterations,
        {
            "seed": seed,
            "ants": ants,
            "alpha": alpha,
            "beta": beta,
            "evaporation_rate": evaporation_rate,
            "pheromone_deposit": pheromone_deposit,
            "feasible_ants": feasible_ants,
            "function_evaluations": ants * iterations,
            "convergence": tuple(convergence),
        },
    )