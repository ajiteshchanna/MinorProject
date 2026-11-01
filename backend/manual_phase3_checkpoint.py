"""Run the complete manual Phase 3 execution checkpoint."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import networkx as nx

from .algorithms import OptimizationResult, optimize
from .graph import load_graph

OBJECTIVES = ("cost", "time", "emissions")
ALGORITHMS = ("dijkstra", "astar", "nsga2", "simulated_annealing")
METRIC_FIELDS = {
    "cost": "cost",
    "time": "travel_time_hours",
    "emissions": "carbon_emissions_kg",
}
METRIC_LABELS = {
    "cost": "cost",
    "time": "travel time",
    "emissions": "carbon emissions",
}


def route_metrics(
    graph: nx.MultiDiGraph, result: OptimizationResult
) -> dict[str, float]:
    """Recalculate all metrics from the result's exact edge identities."""
    if not result.feasible or result.nodes[0] != result.source or result.nodes[-1] != result.destination:
        raise AssertionError(f"Invalid route endpoints for {result.algorithm}")
    if len(result.edge_ids) != len(result.nodes) - 1:
        raise AssertionError(f"Invalid route length for {result.algorithm}")

    totals = {"cost": 0.0, "time": 0.0, "emissions": 0.0}
    for source, destination, edge_id, mode in zip(
        result.nodes, result.nodes[1:], result.edge_ids, result.modes
    ):
        edge_data = graph.get_edge_data(source, destination, edge_id)
        if edge_data is None:
            raise AssertionError(
                f"Missing edge {edge_id} for {source} -> {destination}"
            )
        if edge_data["mode"] != mode:
            raise AssertionError(f"Mode mismatch for edge {edge_id}")
        for objective, field in METRIC_FIELDS.items():
            totals[objective] += float(edge_data[field])
    return totals


def run_algorithm(
    graph: nx.MultiDiGraph, algorithm: str, objective: str
) -> tuple[OptimizationResult, dict[str, float], float]:
    parameters: dict[str, object] = {}
    if algorithm == "nsga2":
        parameters = {"population_size": 10, "generations": 3, "seed": 11}
    elif algorithm == "simulated_annealing":
        parameters = {"iterations": 30, "seed": 11}
    start = time.perf_counter()
    result = optimize(algorithm, graph, "C01", "C10", objective, **parameters)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return result, route_metrics(graph, result), elapsed_ms


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-dir",
        type=Path,
        default=Path("datasets/processed/dataset_10"),
    )
    args = parser.parse_args()
    graph = load_graph(args.dataset_dir)
    print(f"Dataset: {args.dataset_dir}")
    print(f"Graph: {graph.number_of_nodes()} cities, {graph.number_of_edges()} directed edges")
    print("Source: C01 | Destination: C10")
    print("NSGA-II parameters: population_size=10, generations=3, seed=11")
    print("Simulated Annealing parameters: iterations=30, seed=11")

    for objective in OBJECTIVES:
        print(f"\n=== Objective: {METRIC_LABELS[objective]} ===")
        results: dict[str, tuple[OptimizationResult, dict[str, float], float]] = {}
        for algorithm in ALGORITHMS:
            results[algorithm] = run_algorithm(graph, algorithm, objective)
            result, totals, elapsed_ms = results[algorithm]
            print(
                f"{algorithm}: valid=True, route={' -> '.join(result.nodes)}, "
                f"modes={','.join(result.modes)}, cost={totals['cost']:.2f}, "
                f"time={totals['time']:.2f} h, emissions={totals['emissions']:.2f} kg, "
                f"selected_objective={result.objective_value:.2f}, "
                f"execution={elapsed_ms:.2f} ms"
            )

        dijkstra_value = results["dijkstra"][1][objective]
        astar_value = results["astar"][1][objective]
        match = abs(dijkstra_value - astar_value) <= 1e-9
        print(
            f"Dijkstra/A* comparison: dijkstra={dijkstra_value:.2f}, "
            f"astar={astar_value:.2f}, match={match}"
        )
        if not match:
            raise AssertionError(f"Dijkstra and A* differ for {objective}")

        stochastic = {
            algorithm: results[algorithm][1][objective]
            for algorithm in ("nsga2", "simulated_annealing")
        }
        best_algorithm = min(stochastic, key=stochastic.__getitem__)
        print(
            "Best-so-far stochastic result: "
            f"{best_algorithm} ({stochastic[best_algorithm]:.2f} "
            f"{METRIC_LABELS[objective]})"
        )

    print("\nCheckpoint status: PASS")


if __name__ == "__main__":
    main()
