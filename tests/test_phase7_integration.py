from pathlib import Path

import networkx as nx
import pytest

from backend.algorithms import optimize
from backend.evaluation import recalculate_route_metrics, validate_route
from backend.graph import build_graph, load_graph


DATASETS = Path(__file__).parents[1] / "datasets" / "processed"
DATASET_NAMES = tuple(f"dataset_{size}" for size in (10, 20, 30, 40, 50, 60))
OBJECTIVES = ("cost", "time", "emissions")
ALGORITHMS = ("dijkstra", "astar", "nsga2", "simulated_annealing")


@pytest.mark.parametrize("dataset_name", DATASET_NAMES)
@pytest.mark.parametrize("objective", OBJECTIVES)
@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_all_supported_datasets_objectives_and_algorithms(
    dataset_name: str, objective: str, algorithm: str
) -> None:
    graph = load_graph(DATASETS / dataset_name)
    kwargs = (
        {"population_size": 4, "generations": 1}
        if algorithm == "nsga2"
        else {"iterations": 5}
        if algorithm == "simulated_annealing"
        else {}
    )

    result = optimize(algorithm, graph, "C01", "C10", objective, **kwargs)
    validation = validate_route(graph, result)

    assert validation.valid, validation.errors
    assert validation.metrics[objective] == result.objective_value
    assert recalculate_route_metrics(graph, result) == validation.metrics
    assert result.nodes[0] == "C01"
    assert result.nodes[-1] == "C10"


def test_disconnected_graph_and_invalid_inputs_are_explicit() -> None:
    cities = [
        {
            "city_id": "C01",
            "city_name": "A",
            "country": "India",
            "latitude": "1",
            "longitude": "2",
        },
        {
            "city_id": "C02",
            "city_name": "B",
            "country": "India",
            "latitude": "2",
            "longitude": "3",
        },
        {
            "city_id": "C03",
            "city_name": "C",
            "country": "India",
            "latitude": "3",
            "longitude": "4",
        },
    ]
    edge = {
        "connection_id": "edge-1",
        "source_city_id": "C01",
        "destination_city_id": "C02",
        "mode": "road",
        "distance_km": "10",
        "cost": "10",
        "travel_time_hours": "1",
        "carbon_emissions_kg": "1",
    }
    graph = build_graph(cities, [edge])

    with pytest.raises(ValueError, match="No route"):
        optimize("dijkstra", graph, "C01", "C03", "cost")
    with pytest.raises(ValueError, match="Unknown graph node"):
        optimize("astar", graph, "C01", "C99", "cost")
    with pytest.raises(ValueError, match="Unsupported objective"):
        optimize("dijkstra", graph, "C01", "C02", "distance")
