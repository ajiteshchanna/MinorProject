from pathlib import Path

import pandas as pd
import networkx as nx
import pytest

from backend.evaluation import (
    aggregate_statistics,
    benchmark,
    comparison_table,
    recalculate_route_metrics,
    reference_solution,
    validate_route,
)
from backend.algorithms.common import (
    OptimizationResult,
    route_from_nodes,
    route_from_waypoints,
)
from backend.graph import load_graph


GRAPH = load_graph(Path(__file__).parents[1] / "datasets" / "processed" / "dataset_10")


def test_route_validation_recalculates_all_edge_metrics() -> None:
    result = reference_solution(GRAPH, "C01", "C10", "cost")

    validation = validate_route(GRAPH, result)

    assert validation.valid
    assert validation.errors == ()
    assert validation.metrics == recalculate_route_metrics(GRAPH, result)
    assert validation.metrics["cost"] == result.objective_value
    assert validation.metrics["distance"] > 0


def test_cyclic_routes_are_rejected_by_construction_and_validation() -> None:
    graph = nx.MultiDiGraph()
    for source, destination in (("S", "A"), ("A", "B"), ("B", "A"), ("B", "T")):
        graph.add_edge(
            source,
            destination,
            key=f"{source}-{destination}",
            mode="road",
            distance_km=1,
            cost=1,
            travel_time_hours=1,
            carbon_emissions_kg=1,
        )

    with pytest.raises(nx.NetworkXNoPath, match="cannot revisit"):
        route_from_nodes(graph, ("S", "A", "B", "A", "B", "T"), "cost")

    with pytest.raises(nx.NetworkXNoPath, match="Waypoint sequence cannot contain duplicates"):
        route_from_waypoints(graph, ("S", "A", "A", "T"), "cost")

    result = OptimizationResult(
        "test",
        "cost",
        "S",
        "T",
        ("S", "A", "B", "A", "B", "T"),
        ("S-A", "A-B", "B-A", "A-B", "B-T"),
        ("road", "road", "road", "road", "road"),
        5,
        True,
    )
    validation = validate_route(graph, result)
    assert not validation.valid
    assert "route revisits a city" in validation.errors


def test_benchmark_repeats_stochastic_runs_and_builds_comparison_table() -> None:
    records = benchmark(
        GRAPH,
        "C01",
        "C10",
        "time",
        repeats=2,
        algorithms=("dijkstra", "nsga2", "simulated_annealing"),
        algorithm_kwargs={
            "nsga2": {"population_size": 10, "generations": 3},
            "simulated_annealing": {"iterations": 10},
        },
    )

    table = comparison_table(records)

    assert isinstance(table, pd.DataFrame)
    assert len(records) == 6
    assert table["valid"].all()
    assert (table["execution_time_ms"] >= 0).all()
    assert (table["peak_memory_bytes"] >= 0).all()
    assert (table["optimality_gap"] >= 0).all()
    assert all(len(value) > 0 for value in table.loc[table["algorithm"] != "dijkstra", "convergence"])
    for column in (
        "execution_time_mean_ms",
        "execution_time_median_ms",
        "execution_time_stddev_ms",
        "peak_memory_mean_bytes",
        "peak_memory_median_bytes",
        "peak_memory_stddev_bytes",
    ):
        assert column in table


def test_warmups_are_excluded_and_aggregates_use_measured_runs(monkeypatch) -> None:
    import backend.evaluation as evaluation

    calls = []
    original_optimize = evaluation.optimize

    def counting_optimize(*args, **kwargs):
        calls.append(kwargs.get("seed"))
        return original_optimize(*args, **kwargs)

    monkeypatch.setattr(evaluation, "optimize", counting_optimize)
    records = benchmark(
        GRAPH,
        "C01",
        "C10",
        "cost",
        algorithms=("simulated_annealing",),
        repeats=2,
        algorithm_kwargs={"simulated_annealing": {"iterations": 5}},
    )

    assert calls == [0, 1, 2]
    assert [record.run for record in records] == [1, 2]
    statistics = aggregate_statistics(records).iloc[0]
    assert statistics["execution_time_mean_ms"] == sum(
        record.execution_time_ms for record in records
    ) / 2
