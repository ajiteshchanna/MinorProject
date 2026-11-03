"""Evaluation and benchmarking utilities for classical route optimizers."""

from __future__ import annotations

from dataclasses import dataclass
import time
import tracemalloc
from typing import Iterable, Mapping

import networkx as nx
import pandas as pd

from .algorithms import OptimizationResult, optimize
from .algorithms.common import (
    OBJECTIVE_ATTRIBUTES,
    ObjectiveName,
    route_from_nodes,
    validate_objective,
)

OBJECTIVES = ("cost", "time", "emissions")
ALGORITHMS = ("dijkstra", "astar", "nsga2", "simulated_annealing")
ITERATIVE_CONVERGENCE_NOTE = (
    "Dijkstra and A* are single-pass shortest-path searches, so they have no "
    "iterative convergence history."
)
FUNCTION_EVALUATION_NOTE = (
    "NSGA-II counts pymoo evaluator calls (including the initial population); "
    "Simulated Annealing counts the initial route evaluation plus one evaluation "
    "per iteration."
)


@dataclass(frozen=True)
class RouteValidation:
    """Validation outcome and independently recalculated route metrics."""

    valid: bool
    metrics: dict[str, float]
    errors: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return self.valid


@dataclass(frozen=True)
class BenchmarkRecord:
    """Measured result for one algorithm execution.

    ``convergence`` contains best-so-far objective values for iterative
    algorithms. It is empty for Dijkstra and A* because they are single-pass
    searches rather than iterative optimizers.
    """

    algorithm: str
    objective: ObjectiveName
    run: int
    source: str
    destination: str
    valid: bool
    cost: float
    time: float
    emissions: float
    objective_value: float
    optimality_gap: float | None
    execution_time_ms: float
    peak_memory_bytes: int
    nodes_explored: int | None
    function_evaluations: int | None
    convergence: tuple[float, ...]
    nodes: tuple[str, ...]
    edge_ids: tuple[str, ...]
    modes: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Return a flat row suitable for CSV or pandas."""
        return {
            "algorithm": self.algorithm,
            "objective": self.objective,
            "run": self.run,
            "source": self.source,
            "destination": self.destination,
            "valid": self.valid,
            "cost": self.cost,
            "time": self.time,
            "emissions": self.emissions,
            "objective_value": self.objective_value,
            "optimality_gap": self.optimality_gap,
            "execution_time_ms": self.execution_time_ms,
            "peak_memory_bytes": self.peak_memory_bytes,
            "nodes_explored": self.nodes_explored,
            "function_evaluations": self.function_evaluations,
            "convergence": self.convergence,
            "nodes": self.nodes,
            "edge_ids": self.edge_ids,
            "modes": self.modes,
        }


def recalculate_route_metrics(
    graph: nx.MultiDiGraph, result: OptimizationResult
) -> dict[str, float]:
    """Recalculate all supported metrics from a result's exact edge IDs."""
    validation = validate_route(graph, result)
    if not validation.valid:
        raise ValueError("; ".join(validation.errors))
    return validation.metrics


def validate_route(
    graph: nx.MultiDiGraph, result: OptimizationResult
) -> RouteValidation:
    """Validate endpoints, edge identity, modes, and route feasibility."""
    errors: list[str] = []
    if not result.feasible:
        errors.append("optimizer returned an infeasible result")
    if not result.nodes:
        errors.append("route has no nodes")
    else:
        if result.nodes[0] != result.source:
            errors.append("route source does not match result.source")
        if result.nodes[-1] != result.destination:
            errors.append("route destination does not match result.destination")
    if len(result.edge_ids) != max(0, len(result.nodes) - 1):
        errors.append("edge count does not match route length")
    if len(result.modes) != len(result.edge_ids):
        errors.append("mode count does not match edge count")

    totals = {"cost": 0.0, "time": 0.0, "emissions": 0.0}
    for source, destination, edge_id, mode in zip(
        result.nodes, result.nodes[1:], result.edge_ids, result.modes
    ):
        edge_data = graph.get_edge_data(source, destination, edge_id)
        if edge_data is None:
            errors.append(f"missing edge {edge_id} for {source} -> {destination}")
            continue
        if str(edge_data.get("mode")) != mode:
            errors.append(f"mode mismatch for edge {edge_id}")
        for objective, attribute in OBJECTIVE_ATTRIBUTES.items():
            try:
                totals[objective] += float(edge_data[attribute])
            except (KeyError, TypeError, ValueError):
                errors.append(f"edge {edge_id} has invalid {attribute}")
    return RouteValidation(not errors, totals, tuple(errors))


def reference_solution(
    graph: nx.MultiDiGraph,
    source: str,
    destination: str,
    objective: str,
) -> OptimizationResult:
    """Return the objective-optimal route used as the benchmarking reference."""
    selected_objective = validate_objective(objective)
    attributes = OBJECTIVE_ATTRIBUTES[selected_objective]
    try:
        nodes = nx.shortest_path(
            graph,
            source,
            destination,
            weight=lambda _u, _v, data: min(
                float(edge[attributes]) for edge in data.values()
            ),
            method="dijkstra",
        )
    except (nx.NodeNotFound, nx.NetworkXNoPath) as exc:
        raise ValueError(f"No route from {source} to {destination}") from exc
    route_nodes, edge_ids, modes, objective_value = route_from_nodes(
        graph, nodes, selected_objective
    )
    result = OptimizationResult(
        "reference",
        selected_objective,
        source,
        destination,
        route_nodes,
        edge_ids,
        modes,
        objective_value,
        True,
    )
    metrics = recalculate_route_metrics(graph, result)
    return OptimizationResult(
        "reference",
        selected_objective,
        source,
        destination,
        route_nodes,
        edge_ids,
        modes,
        metrics[selected_objective],
        True,
    )


def optimality_gap(value: float, reference: float) -> float | None:
    """Return the percentage gap, or ``None`` when no percentage is defined."""
    if reference <= 0:
        return None
    return max(0.0, ((value - reference) / reference) * 100.0)


def benchmark(
    graph: nx.MultiDiGraph,
    source: str,
    destination: str,
    objective: str,
    *,
    algorithms: Iterable[str] = ALGORITHMS,
    repeats: int = 1,
    algorithm_kwargs: Mapping[str, Mapping[str, object]] | None = None,
) -> tuple[BenchmarkRecord, ...]:
    """Warm up and measure selected algorithms, optionally repeating each run.

    Exactly one unrecorded warm-up execution is performed per algorithm.
    Function-evaluation counts follow ``FUNCTION_EVALUATION_NOTE``.
    """
    selected_objective = validate_objective(objective)
    if repeats < 1:
        raise ValueError("repeats must be positive")
    selected_algorithms = tuple(algorithms)
    unknown = set(selected_algorithms) - set(ALGORITHMS)
    if unknown:
        raise ValueError(f"Unknown algorithm(s): {', '.join(sorted(unknown))}")
    reference = reference_solution(graph, source, destination, selected_objective)
    reference_value = reference.objective_value
    kwargs_by_algorithm = algorithm_kwargs or {}
    records: list[BenchmarkRecord] = []
    for algorithm in selected_algorithms:
        warmup_kwargs = dict(kwargs_by_algorithm.get(algorithm, {}))
        if algorithm in {"nsga2", "simulated_annealing"}:
            warmup_kwargs.setdefault("seed", 0)
        optimize(
            algorithm, graph, source, destination, selected_objective, **warmup_kwargs
        )
        for run in range(1, repeats + 1):
            kwargs = dict(kwargs_by_algorithm.get(algorithm, {}))
            if algorithm in {"nsga2", "simulated_annealing"}:
                kwargs.setdefault("seed", run)
            result, elapsed_ms, peak_memory = _measure_execution(
                graph, algorithm, source, destination, selected_objective, kwargs
            )
            validation = validate_route(graph, result)
            if not validation.valid:
                raise ValueError(f"Invalid {algorithm} result: {'; '.join(validation.errors)}")
            metadata = result.metadata
            records.append(
                BenchmarkRecord(
                    algorithm=algorithm,
                    objective=selected_objective,
                    run=run,
                    source=source,
                    destination=destination,
                    valid=True,
                    cost=validation.metrics["cost"],
                    time=validation.metrics["time"],
                    emissions=validation.metrics["emissions"],
                    objective_value=validation.metrics[selected_objective],
                    optimality_gap=optimality_gap(
                        validation.metrics[selected_objective], reference_value
                    ),
                    execution_time_ms=elapsed_ms,
                    peak_memory_bytes=peak_memory,
                    nodes_explored=_integer_metadata(metadata, "nodes_explored"),
                    function_evaluations=_integer_metadata(
                        metadata, "function_evaluations"
                    ),
                    convergence=_convergence_metadata(metadata),
                    nodes=result.nodes,
                    edge_ids=result.edge_ids,
                    modes=result.modes,
                )
            )
    return tuple(records)


def comparison_table(records: Iterable[BenchmarkRecord]) -> pd.DataFrame:
    """Create measured per-run rows with repeated aggregate statistics."""
    materialized = tuple(records)
    table = pd.DataFrame([record.as_dict() for record in materialized])
    if table.empty:
        return table
    aggregates = aggregate_statistics(materialized)
    return table.merge(aggregates, on=["algorithm", "objective"], how="left")


def aggregate_statistics(records: Iterable[BenchmarkRecord]) -> pd.DataFrame:
    """Return mean, median, and population standard deviation by algorithm.

    Statistics use only measured repetitions; warm-up executions are never
    represented by ``BenchmarkRecord``. Memory statistics are peak allocations
    observed by ``tracemalloc`` during each measured execution.
    """
    materialized = tuple(records)
    if not materialized:
        return pd.DataFrame(
            columns=[
                "algorithm",
                "objective",
                "execution_time_mean_ms",
                "execution_time_median_ms",
                "execution_time_stddev_ms",
                "peak_memory_mean_bytes",
                "peak_memory_median_bytes",
                "peak_memory_stddev_bytes",
            ]
        )
    table = pd.DataFrame(
        [
            {
                "algorithm": record.algorithm,
                "objective": record.objective,
                "execution_time_ms": record.execution_time_ms,
                "peak_memory_bytes": record.peak_memory_bytes,
            }
            for record in materialized
        ]
    )
    grouped = table.groupby(["algorithm", "objective"], as_index=False)
    statistics = grouped.agg(
        execution_time_mean_ms=("execution_time_ms", "mean"),
        execution_time_median_ms=("execution_time_ms", "median"),
        execution_time_stddev_ms=("execution_time_ms", lambda values: values.std(ddof=0)),
        peak_memory_mean_bytes=("peak_memory_bytes", "mean"),
        peak_memory_median_bytes=("peak_memory_bytes", "median"),
        peak_memory_stddev_bytes=("peak_memory_bytes", lambda values: values.std(ddof=0)),
    )
    return statistics


def _measure_execution(
    graph: nx.MultiDiGraph,
    algorithm: str,
    source: str,
    destination: str,
    objective: ObjectiveName,
    kwargs: Mapping[str, object],
) -> tuple[OptimizationResult, float, int]:
    """Apply the one measurement procedure to every recorded execution."""
    tracemalloc.start()
    try:
        started = time.perf_counter()
        result = optimize(algorithm, graph, source, destination, objective, **kwargs)
        elapsed_ms = (time.perf_counter() - started) * 1000
        _, peak_memory = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, elapsed_ms, peak_memory


def _integer_metadata(metadata: Mapping[str, object], key: str) -> int | None:
    value = metadata.get(key)
    return int(value) if isinstance(value, (int, float)) else None


def _convergence_metadata(metadata: Mapping[str, object]) -> tuple[float, ...]:
    value = metadata.get("convergence", ())
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(float(item) for item in value)
