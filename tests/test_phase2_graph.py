from pathlib import Path

import networkx as nx
import pytest

from backend.graph import (
    GraphDataError,
    build_graph,
    connectivity_report,
    load_graph,
    parallel_mode_pairs,
)


DATASETS_DIR = Path(__file__).parents[1] / "datasets" / "processed"


def test_loads_dataset_as_multidigraph_and_preserves_edge_identity() -> None:
    graph = load_graph(DATASETS_DIR / "dataset_60")

    assert isinstance(graph, nx.MultiDiGraph)
    assert graph.number_of_nodes() == 60
    assert graph.number_of_edges() == 592
    edge_data = graph.get_edge_data("C30", "C44")
    assert edge_data is not None
    assert set(edge_data) == {"C30_C44_waterway"}
    assert edge_data["C30_C44_waterway"]["mode"] == "waterway"
    assert edge_data["C30_C44_waterway"]["carbon_emissions_kg"] > 0
    pair_modes = parallel_mode_pairs(graph)
    assert {"road", "rail", "air"} == set(pair_modes[("C01", "C02")])


def test_reports_connectivity_and_parallel_modes() -> None:
    graph = load_graph(DATASETS_DIR / "dataset_30")

    assert connectivity_report(graph) == {
        "weakly_connected": True,
        "strongly_connected": True,
    }
    pairs = parallel_mode_pairs(graph)
    assert ("C01", "C02") in pairs or ("C02", "C01") in pairs
    assert {"road", "rail", "air"} == set(next(iter(pairs.values())))


def test_rejects_unknown_endpoints_and_duplicate_edge_ids() -> None:
    cities = [{"city_id": "C01", "city_name": "A", "country": "India", "latitude": "1", "longitude": "2"}]
    connection = {
        "connection_id": "edge-1",
        "source_city_id": "C01",
        "destination_city_id": "C99",
        "mode": "road",
        "distance_km": "10",
        "cost": "10",
        "travel_time_hours": "1",
        "carbon_emissions_kg": "1",
    }
    with pytest.raises(GraphDataError, match="unknown city"):
        build_graph(cities, [connection])

    connection["destination_city_id"] = "C01"
    cities.append(
        {"city_id": "C02", "city_name": "B", "country": "India", "latitude": "2", "longitude": "3"}
    )
    connection["destination_city_id"] = "C02"
    with pytest.raises(GraphDataError, match="Duplicate connection_id"):
        build_graph(cities, [connection, connection.copy()])
