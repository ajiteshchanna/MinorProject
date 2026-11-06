from pathlib import Path

import pytest

from backend.algorithms import optimize
from backend.graph import load_graph


GRAPH = load_graph(Path(__file__).parents[1] / "datasets" / "processed" / "dataset_10")


@pytest.mark.parametrize("algorithm", ("dijkstra", "astar", "nsga2", "simulated_annealing", "aco"))
@pytest.mark.parametrize("objective", ("cost", "time", "emissions"))
def test_algorithms_return_standardized_feasible_routes(algorithm: str, objective: str) -> None:
    result = optimize(
        algorithm,
        GRAPH,
        "C01",
        "C10",
        objective,
        **({"population_size": 10, "generations": 3} if algorithm == "nsga2" else {}),
        **({"iterations": 30} if algorithm == "simulated_annealing" else {}),
        **({"ants": 5, "iterations": 10} if algorithm == "aco" else {}),
    )
    assert result.algorithm == algorithm
    assert result.objective == objective
    assert result.nodes[0] == "C01"
    assert result.nodes[-1] == "C10"
    assert len(result.edge_ids) == len(result.nodes) - 1
    assert len(result.modes) == len(result.edge_ids)
    assert result.feasible
    assert result.objective_value > 0


def test_stochastic_algorithms_are_reproducible_with_seed() -> None:
    first = optimize("nsga2", GRAPH, "C01", "C10", "cost", population_size=10, generations=3, seed=11)
    second = optimize("nsga2", GRAPH, "C01", "C10", "cost", population_size=10, generations=3, seed=11)
    assert first.nodes == second.nodes
    assert first.objective_value == second.objective_value

    first = optimize("simulated_annealing", GRAPH, "C01", "C10", "time", iterations=30, seed=11)
    second = optimize("simulated_annealing", GRAPH, "C01", "C10", "time", iterations=30, seed=11)
    assert first.nodes == second.nodes
    assert first.objective_value == second.objective_value

    first = optimize("aco", GRAPH, "C01", "C10", "emissions", ants=5, iterations=10, seed=11)
    second = optimize("aco", GRAPH, "C01", "C10", "emissions", ants=5, iterations=10, seed=11)
    assert first.nodes == second.nodes
    assert first.objective_value == second.objective_value


def test_rejects_invalid_objective_and_endpoint() -> None:
    with pytest.raises(ValueError, match="Unsupported objective"):
        optimize("dijkstra", GRAPH, "C01", "C10", "distance")
    with pytest.raises(ValueError, match="Unknown graph node"):
        optimize("astar", GRAPH, "C01", "C99", "cost")
