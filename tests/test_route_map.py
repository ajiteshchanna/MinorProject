import networkx as nx
import pytest

from app.components.route_map import (
    MODE_STYLES,
    RouteMapError,
    create_route_map,
    prepare_route_map_data,
)


def _graph() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    graph.add_node("C01", city_name="Ahmedabad", latitude=23.0, longitude=72.5)
    graph.add_node("C02", city_name="Mumbai", latitude=19.0, longitude=72.8)
    graph.add_node("C03", city_name="Delhi", latitude=28.6, longitude=77.2)
    graph.add_edge(
        "C01",
        "C02",
        key="road-1",
        connection_id="road-1",
        mode="road",
        distance_km=500,
        cost=100,
    )
    graph.add_edge(
        "C01",
        "C02",
        key="rail-1",
        connection_id="rail-1",
        mode="rail",
        distance_km=520,
        cost=80,
    )
    graph.add_edge(
        "C02",
        "C03",
        key="air-1",
        connection_id="air-1",
        mode="air",
        distance_km=800,
        cost=200,
    )
    return graph


def test_preparation_preserves_route_order_and_exact_parallel_edge() -> None:
    data = prepare_route_map_data(
        _graph(),
        ("C01", "C02", "C03"),
        ("rail-1", "air-1"),
        ("rail", "air"),
    )

    assert data.nodes == ("C01", "C02", "C03")
    assert data.city_names["C01"] == "Ahmedabad"
    assert data.city_coordinates["C03"] == (28.6, 77.2)
    assert data.segments[0].edge_id == "rail-1"
    assert data.segments[0].attributes["cost"] == 80
    assert data.segments[0].mode == "rail"


@pytest.mark.parametrize(
    ("mode", "color", "dash_array"),
    (
        ("road", "blue", ""),
        ("rail", "red", "10, 10"),
        ("air", "purple", "2, 8"),
        ("waterways", "green", "10, 5, 2, 5"),
    ),
)
def test_transport_mode_styles(mode: str, color: str, dash_array: str) -> None:
    assert MODE_STYLES[mode] == {"color": color, "dash_array": dash_array}


def test_map_contains_source_destination_and_connection_details() -> None:
    route_map = create_route_map(
        prepare_route_map_data(
            _graph(), ("C01", "C02"), ("rail-1",), ("rail",)
        )
    )

    rendered = route_map.get_root().render()
    assert "Ahmedabad" in rendered
    assert "Mumbai" in rendered
    assert "rail-1" in rendered
    assert "Distance (km)" in rendered
    assert "red" in rendered
    assert "color: #000000" in rendered
    assert "border: 1px solid #b0b0b0" in rendered
    for label in ("Source", "Destination", "Intermediate city", "Road", "Rail", "Air", "Waterways"):
        assert label in rendered


def test_missing_coordinates_and_invalid_routes_raise_clear_errors() -> None:
    graph = _graph()
    del graph.nodes["C03"]["latitude"]
    with pytest.raises(RouteMapError, match="no valid coordinates"):
        prepare_route_map_data(graph, ("C02", "C03"), ("air-1",), ("air",))

    with pytest.raises(RouteMapError, match="does not match"):
        prepare_route_map_data(_graph(), ("C01", "C02"), (), ())

    with pytest.raises(RouteMapError, match="missing"):
        prepare_route_map_data(_graph(), ("C01", "C02"), ("missing",), ("road",))

    with pytest.raises(RouteMapError, match="cannot revisit"):
        prepare_route_map_data(
            _graph(), ("C01", "C02", "C01"), ("road-1", "road-1"), ("road", "road")
        )
