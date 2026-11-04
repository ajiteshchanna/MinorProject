import networkx as nx
import pytest

from app.components.route_map import (
    MODE_STYLES,
    RouteMapError,
    create_route_map,
    eligible_alternative_connections,
    generate_alternative_routes,
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


def _route_graph() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    for node, name, latitude, longitude in (
        ("S", "Source", 20.0, 70.0),
        ("A", "Alpha", 21.0, 71.0),
        ("B", "Beta", 22.0, 72.0),
        ("T", "Destination", 23.0, 73.0),
    ):
        graph.add_node(node, city_name=name, latitude=latitude, longitude=longitude)

    def add_edge(
        source: str,
        destination: str,
        key: str,
        cost: float,
        time: float,
        emissions: float,
        distance: float,
    ) -> None:
        graph.add_edge(
            source,
            destination,
            key=key,
            connection_id=key,
            mode="road",
            cost=cost,
            travel_time_hours=time,
            carbon_emissions_kg=emissions,
            distance_km=distance,
        )

    add_edge("S", "A", "s-a", 2, 2, 2, 20)
    add_edge("S", "A", "s-a-rail", 5, 1, 1, 30)
    add_edge("A", "T", "a-t", 2, 2, 2, 20)
    add_edge("S", "B", "s-b", 3, 3, 3, 30)
    add_edge("B", "T", "b-t", 3, 3, 3, 30)
    add_edge("T", "S", "reverse", 1, 1, 1, 1)
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


def test_alternative_connections_use_source_destination_reachability() -> None:
    graph = _graph()
    graph.add_node("C04", city_name="Kochi", latitude=10.0, longitude=76.0)
    graph.add_edge("C04", "C03", key="unreachable-source", mode="road")

    alternatives = eligible_alternative_connections(graph, "C01", "C03")

    assert {connection.edge_id for connection in alternatives} == {
        "road-1",
        "rail-1",
        "air-1",
    }
    assert "unreachable-source" not in {connection.edge_id for connection in alternatives}


def test_alternative_layer_preserves_route_and_can_be_toggled() -> None:
    route_data = prepare_route_map_data(
        _graph(), ("C01", "C02", "C03"), ("rail-1", "air-1"), ("rail", "air")
    )

    rendered = create_route_map(route_data).get_root().render()

    assert len(route_data.alternative_connections) == 3
    assert rendered.count('color": "#4a4a4a"') == 3
    assert '"Show alternative connections" : feature_group_' in rendered
    assert '"color": "red"' in rendered
    assert '"dashArray": "10, 10"' in rendered
    assert rendered.index('"color": "#4a4a4a"') < rendered.index('"color": "red"')
    for connection_id in ("road-1", "rail-1", "air-1"):
        assert connection_id in rendered


def test_alternative_connections_handle_missing_path_and_same_city() -> None:
    graph = _graph()
    assert eligible_alternative_connections(graph, "C03", "C01") == ()
    assert eligible_alternative_connections(graph, "C01", "C01") == ()

    graph.add_edge("C03", "C01", key="return-1", mode="road")
    assert [edge.edge_id for edge in eligible_alternative_connections(graph, "C01", "C01")] == [
        "road-1",
        "rail-1",
        "air-1",
        "return-1",
    ]


def test_alternative_connections_do_not_enumerate_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("path enumeration is not allowed")

    monkeypatch.setattr(nx, "all_simple_paths", fail_if_called)

    alternatives = eligible_alternative_connections(_graph(), "C01", "C03")

    assert len(alternatives) == 3


def test_complete_alternatives_preserve_parallel_edges_and_rank_metrics() -> None:
    graph = _route_graph()

    alternatives = generate_alternative_routes(
        graph,
        "S",
        "T",
        "cost",
        selected_edge_ids=("s-a", "a-t"),
        max_routes=5,
    )

    assert [route.cost for route in alternatives] == [6, 7]
    assert [route.route_id for route in alternatives] == ["ALT_01", "ALT_02"]
    assert alternatives[0].coordinates == ((20.0, 70.0), (22.0, 72.0), (23.0, 73.0))
    assert [tuple(segment.edge_id for segment in route.segments) for route in alternatives] == [
        ("s-b", "b-t"),
        ("s-a-rail", "a-t"),
    ]
    assert alternatives[1].nodes == ("S", "A", "T")
    assert alternatives[1].travel_time == 3
    assert alternatives[1].emissions == 3
    assert alternatives[1].distance == 50
    assert all(route.nodes[0] == "S" and route.nodes[-1] == "T" for route in alternatives)
    assert len({tuple(segment.edge_id for segment in route.segments) for route in alternatives}) == 2


def test_complete_alternatives_rank_by_selected_objective_and_handle_no_path() -> None:
    graph = _route_graph()

    by_time = generate_alternative_routes(
        graph, "S", "T", "time", selected_edge_ids=("s-a-rail", "a-t")
    )
    by_emissions = generate_alternative_routes(
        graph, "S", "T", "emissions", selected_edge_ids=("s-a", "a-t")
    )

    assert [route.travel_time for route in by_time] == [4, 6]
    assert [route.emissions for route in by_emissions] == [3, 6]
    assert generate_alternative_routes(graph, "missing", "A", "cost") == ()


def test_complete_route_popup_is_selectable_without_changing_optimized_route() -> None:
    route_data = prepare_route_map_data(
        _route_graph(),
        ("S", "A", "T"),
        ("s-a", "a-t"),
        ("road", "road"),
        objective="cost",
    )

    rendered = create_route_map(route_data).get_root().render()

    assert len(route_data.alternative_routes) == 2
    assert "ALT_01" in rendered
    assert "Total cost" not in rendered
    assert "s-a-rail" in rendered
    assert "Connection 1" in rendered
    assert "Travel time" in rendered
    assert '"color": "blue"' in rendered


def test_selected_alternative_highlights_the_complete_route() -> None:
    route_data = prepare_route_map_data(
        _route_graph(),
        ("S", "A", "T"),
        ("s-a", "a-t"),
        ("road", "road"),
        objective="cost",
    )

    rendered = create_route_map(
        route_data, selected_alternative_route_id="ALT_01"
    ).get_root().render()

    assert rendered.count('"color": "#38BDF8"') == 1
    assert '"weight": 6' in rendered
    assert "ALT_01" in rendered
    assert '"color": "blue"' in rendered
    assert rendered.count('"route_id": "ALT_01"') == 1


def test_missing_coordinates_and_invalid_routes_raise_clear_errors() -> None:
    graph = _graph()
    del graph.nodes["C03"]["latitude"]
    with pytest.raises(RouteMapError, match="no valid coordinates"):
        prepare_route_map_data(graph, ("C02", "C03"), ("air-1",), ("air",))

    with pytest.raises(RouteMapError, match="does not match"):
        prepare_route_map_data(_graph(), ("C01", "C02"), (), ())

    with pytest.raises(RouteMapError, match="missing"):
        prepare_route_map_data(_graph(), ("C01", "C02"), ("missing",), ("road",))
