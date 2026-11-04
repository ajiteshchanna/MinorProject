"""Interactive schematic route maps for multimodal transportation routes."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
import heapq
from itertools import count
from typing import Mapping, Sequence

import folium
import networkx as nx

INDIA_CENTER = (22.5, 79.0)
MODE_STYLES: dict[str, dict[str, str]] = {
    "road": {"color": "blue", "dash_array": ""},
    "rail": {"color": "red", "dash_array": "10, 10"},
    "air": {"color": "purple", "dash_array": "2, 8"},
    "water": {"color": "green", "dash_array": "10, 5, 2, 5"},
    "waterway": {"color": "green", "dash_array": "10, 5, 2, 5"},
    "waterways": {"color": "green", "dash_array": "10, 5, 2, 5"},
}
EDGE_ATTRIBUTES = (
    ("connection_id", "Connection ID"),
    ("mode", "Transport mode"),
    ("distance_km", "Distance (km)"),
    ("cost", "Cost"),
    ("travel_time_hours", "Travel time (hours)"),
    ("carbon_emissions_kg", "Carbon emissions (kg)"),
)


class RouteMapError(ValueError):
    """Raised when a route cannot be represented on a map."""


@dataclass(frozen=True)
class RouteSegment:
    """An exact selected MultiDiGraph edge between two route cities."""

    source: str
    destination: str
    edge_id: str
    mode: str
    attributes: Mapping[str, object]


@dataclass(frozen=True)
class AlternativeRoute:
    """A complete source-to-destination route with exact keyed segments."""

    route_id: str
    nodes: tuple[str, ...]
    coordinates: tuple[tuple[float, float], ...]
    segments: tuple[RouteSegment, ...]
    cost: float
    travel_time: float
    emissions: float
    distance: float


OBJECTIVE_ATTRIBUTES = {
    "cost": "cost",
    "time": "travel_time_hours",
    "emissions": "carbon_emissions_kg",
}
ROUTE_METRIC_ATTRIBUTES = (
    ("cost", "cost"),
    ("travel_time", "travel_time_hours"),
    ("emissions", "carbon_emissions_kg"),
    ("distance", "distance_km"),
)


def _edge_metric_values(attributes: Mapping[str, object]) -> dict[str, float] | None:
    try:
        return {
            metric: float(attributes[attribute])
            for metric, attribute in ROUTE_METRIC_ATTRIBUTES
        }
    except (KeyError, TypeError, ValueError):
        return None


def generate_alternative_routes(
    graph: nx.MultiDiGraph,
    source: str,
    destination: str,
    objective: str,
    selected_edge_ids: Sequence[str] = (),
    max_routes: int = 5,
    max_expansions: int = 10000,
) -> tuple[AlternativeRoute, ...]:
    """Generate a bounded, edge-aware set of ranked simple routes."""
    objective_attribute = OBJECTIVE_ATTRIBUTES.get(str(objective))
    if (
        objective_attribute is None
        or max_routes <= 0
        or source not in graph
        or destination not in graph
        or source == destination
    ):
        return ()

    selected_ids = tuple(str(edge_id) for edge_id in selected_edge_ids)
    pending: list[tuple[float, int, str, tuple[str, ...], tuple[RouteSegment, ...]]] = []
    sequence = count()
    heapq.heappush(pending, (0.0, next(sequence), str(source), (str(source),), ()))
    alternatives: list[AlternativeRoute] = []
    seen_routes: set[tuple[tuple[str, ...], tuple[str, ...]]] = set()
    expansions = 0

    while pending and len(alternatives) < max_routes and expansions < max_expansions:
        _, _, node, nodes, segments = heapq.heappop(pending)
        if node == str(destination):
            edge_ids = tuple(segment.edge_id for segment in segments)
            route_identity = (nodes, edge_ids)
            if edge_ids != selected_ids and route_identity not in seen_routes:
                seen_routes.add(route_identity)
                totals = {
                    metric: sum(
                        float(segment.attributes[attribute]) for segment in segments
                    )
                    for metric, attribute in ROUTE_METRIC_ATTRIBUTES
                }
                alternatives.append(
                    AlternativeRoute(
                        f"ALT_{len(alternatives) + 1:02d}",
                        nodes,
                        tuple(
                            (
                                float(graph.nodes[node]["latitude"]),
                                float(graph.nodes[node]["longitude"]),
                            )
                            for node in nodes
                        ),
                        segments,
                        totals["cost"],
                        totals["travel_time"],
                        totals["emissions"],
                        totals["distance"],
                    )
                )
            continue

        expansions += 1
        for _, next_node, edge_key, attributes in graph.out_edges(
            node, keys=True, data=True
        ):
            next_node_id = str(next_node)
            if next_node_id in nodes:
                continue
            metric_values = _edge_metric_values(attributes)
            if metric_values is None:
                continue
            segment = RouteSegment(
                node,
                next_node_id,
                str(edge_key),
                str(attributes.get("mode", "")),
                dict(attributes),
            )
            heapq.heappush(
                pending,
                (
                    sum(
                        float(item.attributes[objective_attribute])
                        for item in (*segments, segment)
                    ),
                    next(sequence),
                    next_node_id,
                    (*nodes, next_node_id),
                    (*segments, segment),
                ),
            )
    return tuple(alternatives)


def eligible_alternative_connections(
    graph: nx.MultiDiGraph,
    source: str,
    destination: str,
) -> tuple[RouteSegment, ...]:
    """Return every keyed edge on at least one directed source-to-destination path."""
    source_id = str(source)
    destination_id = str(destination)
    if source_id not in graph or destination_id not in graph:
        return ()

    reachable_from_source = {source_id} | {
        str(node) for node in nx.descendants(graph, source_id)
    }
    can_reach_destination = {destination_id} | {
        str(node) for node in nx.ancestors(graph, destination_id)
    }
    eligible: list[RouteSegment] = []
    for edge_source, edge_destination, edge_key, attributes in graph.edges(
        keys=True, data=True
    ):
        if (
            str(edge_source) in reachable_from_source
            and str(edge_destination) in can_reach_destination
        ):
            eligible.append(
                RouteSegment(
                    str(edge_source),
                    str(edge_destination),
                    str(edge_key),
                    str(attributes.get("mode", "")),
                    dict(attributes),
                )
            )
    return tuple(eligible)


@dataclass(frozen=True)
class RouteMapData:
    """Resolved city coordinates and exact edges used by a route map."""

    nodes: tuple[str, ...]
    city_coordinates: Mapping[str, tuple[float, float]]
    city_names: Mapping[str, str]
    segments: tuple[RouteSegment, ...]
    dataset_coordinates: Mapping[str, tuple[float, float]] = field(
        default_factory=dict
    )
    dataset_names: Mapping[str, str] = field(default_factory=dict)
    alternative_connections: tuple[RouteSegment, ...] = ()
    alternative_routes: tuple[AlternativeRoute, ...] = ()


def prepare_route_map_data(
    graph: nx.MultiDiGraph,
    nodes: Sequence[str],
    edge_ids: Sequence[str],
    modes: Sequence[str],
    objective: str = "cost",
    max_alternative_routes: int = 5,
) -> RouteMapData:
    """Resolve route coordinates and exact keyed edges without reconstructing paths."""
    route_nodes = tuple(str(node) for node in nodes)
    if len(route_nodes) < 2:
        raise RouteMapError("A route must contain a source and destination.")
    if len(edge_ids) != len(route_nodes) - 1:
        raise RouteMapError("The route edge count does not match the city sequence.")
    if len(modes) != len(edge_ids):
        raise RouteMapError("The route mode count does not match the edge sequence.")

    coordinates: dict[str, tuple[float, float]] = {}
    names: dict[str, str] = {}
    for node in route_nodes:
        if node not in graph:
            raise RouteMapError(f"Route city {node!r} is missing from the graph.")
        attributes = graph.nodes[node]
        try:
            coordinates[node] = (
                float(attributes["latitude"]),
                float(attributes["longitude"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RouteMapError(f"Route city {node!r} has no valid coordinates.") from exc
        names[node] = str(attributes.get("city_name", node))

    dataset_coordinates: dict[str, tuple[float, float]] = {}
    dataset_names: dict[str, str] = {}
    for node, attributes in graph.nodes(data=True):
        city_id = str(node)
        try:
            dataset_coordinates[city_id] = (
                float(attributes["latitude"]),
                float(attributes["longitude"]),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RouteMapError(f"Dataset city {city_id!r} has no valid coordinates.") from exc
        dataset_names[city_id] = str(attributes.get("city_name", city_id))

    segments: list[RouteSegment] = []
    for source, destination, edge_id, mode in zip(
        route_nodes, route_nodes[1:], edge_ids, modes
    ):
        edge_key = str(edge_id)
        edge_data = graph.get_edge_data(source, destination, edge_id)
        if edge_data is None:
            matching_edges = [
                data
                for key, data in (graph.get_edge_data(source, destination) or {}).items()
                if str(key) == edge_key
            ]
            edge_data = matching_edges[0] if len(matching_edges) == 1 else None
        if edge_data is None:
            raise RouteMapError(
                f"Selected edge {edge_key!r} is missing for {source} -> {destination}."
            )
        if str(edge_data.get("mode")) != str(mode):
            raise RouteMapError(f"Selected edge {edge_key!r} has a mode mismatch.")
        segments.append(
            RouteSegment(source, destination, edge_key, str(mode), dict(edge_data))
        )

    return RouteMapData(
        route_nodes,
        coordinates,
        names,
        tuple(segments),
        dataset_coordinates,
        dataset_names,
        eligible_alternative_connections(graph, route_nodes[0], route_nodes[-1]),
        generate_alternative_routes(
            graph,
            route_nodes[0],
            route_nodes[-1],
            objective,
            edge_ids,
            max_alternative_routes,
        ),
    )


def create_route_map(
    route_data: RouteMapData,
    selected_alternative_route_id: str | None = None,
) -> folium.Map:
    """Create an interactive schematic map from already-resolved route data."""
    route_map = folium.Map(location=INDIA_CENTER, zoom_start=5, tiles="OpenStreetMap")
    bounds = [route_data.city_coordinates[node] for node in route_data.nodes]
    alternative_layer = folium.FeatureGroup(
        name="Show alternative connections",
        overlay=True,
        show=True,
    ).add_to(route_map)

    for connection in route_data.alternative_connections:
        source_name = route_data.dataset_names[connection.source]
        destination_name = route_data.dataset_names[connection.destination]
        tooltip_rows = [
            f"<b>From city:</b> {escape(source_name)}",
            f"<b>To city:</b> {escape(destination_name)}",
        ]
        for attribute, label in EDGE_ATTRIBUTES:
            value = (
                connection.attributes.get("connection_id", connection.edge_id)
                if attribute == "connection_id"
                else connection.attributes.get(attribute)
            )
            if value is not None:
                tooltip_rows.append(f"<b>{label}:</b> {escape(str(value))}")
        folium.PolyLine(
            [
                route_data.dataset_coordinates[connection.source],
                route_data.dataset_coordinates[connection.destination],
            ],
            color="#4a4a4a",
            weight=1,
            opacity=0.35,
            tooltip=folium.Tooltip("<br>".join(tooltip_rows)),
        ).add_to(alternative_layer)

    for route in route_data.alternative_routes:
        route_rows = [
            f"<b>{escape(route.route_id)}</b>",
            f"<b>Cities:</b> {' → '.join(escape(route_data.dataset_names[node]) for node in route.nodes)}",
            f"<b>Cost:</b> {route.cost:g}",
            f"<b>Travel time:</b> {route.travel_time:g}",
            f"<b>Emissions:</b> {route.emissions:g}",
            f"<b>Distance:</b> {route.distance:g}",
            f"<b>Connections:</b> {len(route.segments)}",
            f"<b>Modes:</b> {' → '.join(escape(segment.mode) for segment in route.segments)}",
        ]
        for index, segment in enumerate(route.segments, start=1):
            route_rows.extend(
                [
                    f"<br><b>Connection {index}:</b> "
                    f"{escape(route_data.dataset_names[segment.source])} → "
                    f"{escape(route_data.dataset_names[segment.destination])}",
                    f"Mode: {escape(segment.mode)} | "
                    f"Connection ID: {escape(str(segment.attributes.get('connection_id', segment.edge_id)))} | "
                    f"Edge key: {escape(segment.edge_id)}",
                ]
            )
            for attribute, label in EDGE_ATTRIBUTES[2:]:
                value = segment.attributes.get(attribute)
                if value is not None:
                    route_rows.append(f"{label}: {escape(str(value))}")
        route_line = folium.PolyLine(
            route.coordinates,
            color="#38BDF8"
            if route.route_id == selected_alternative_route_id
            else "#4a4a4a",
            weight=6 if route.route_id == selected_alternative_route_id else 2,
            opacity=1.0 if route.route_id == selected_alternative_route_id else 0.18,
            popup=folium.Popup("<br>".join(route_rows), max_width=360),
        )
        route_line.options["route_id"] = route.route_id
        route_line.add_to(
            route_map
            if route.route_id == selected_alternative_route_id
            else alternative_layer
        )

    for node, coordinates in route_data.dataset_coordinates.items():
        if node in route_data.nodes:
            continue
        folium.CircleMarker(
            coordinates,
            radius=4,
            color="black",
            fill=True,
            fill_color="black",
            fill_opacity=0.9,
            tooltip=route_data.dataset_names[node],
        ).add_to(route_map)

    for segment in route_data.segments:
        style = MODE_STYLES.get(segment.mode.lower(), {"color": "gray", "dash_array": ""})
        popup_rows = [
            f"<b>From city:</b> {escape(route_data.city_names[segment.source])}",
            f"<b>To city:</b> {escape(route_data.city_names[segment.destination])}",
        ]
        for attribute, label in EDGE_ATTRIBUTES:
            value = segment.edge_id if attribute == "connection_id" else segment.attributes.get(attribute)
            if value is not None:
                popup_rows.append(f"<b>{label}:</b> {escape(str(value))}")
        folium.PolyLine(
            [
                route_data.city_coordinates[segment.source],
                route_data.city_coordinates[segment.destination],
            ],
            color=style["color"],
            weight=5,
            dash_array=style["dash_array"] or None,
            popup=folium.Popup("<br>".join(popup_rows), max_width=350),
        ).add_to(route_map)

    for index, node in enumerate(route_data.nodes):
        if index == 0:
            color, label = "green", "Source"
        elif index == len(route_data.nodes) - 1:
            color, label = "red", "Destination"
        else:
            color, label = "blue", "Intermediate city"
        city_name = escape(route_data.city_names[node])
        popup = folium.Popup(
            f"<b>{label}</b><br>City: {city_name}<br>City ID: {escape(node)}",
            max_width=300,
        )
        folium.Marker(
            route_data.city_coordinates[node],
            popup=popup,
            tooltip=f"{label}: {route_data.city_names[node]}",
            icon=folium.Icon(color=color, icon="info-sign"),
        ).add_to(route_map)

    legend = """
    <div style="position: fixed; bottom: 30px; left: 30px; z-index: 9999;
                background: #ffffff; color: #000000; padding: 12px 14px;
                border: 1px solid #b0b0b0; border-radius: 4px;
                line-height: 1.6; min-width: 180px;
                box-shadow: 0 1px 4px rgba(0, 0, 0, 0.25);">
      <div style="color: #000000; font-weight: 700; margin-bottom: 4px;">
        Route legend
      </div>
      <div style="color: #000000;"><span style="color: green;">&#9679;</span> Source</div>
      <div style="color: #000000;"><span style="color: red;">&#9679;</span> Destination</div>
      <div style="color: #000000;"><span style="color: blue;">&#9679;</span> Intermediate city</div>
      <div style="color: #000000; margin-top: 4px;"><span style="color: blue;">&#9473;</span> Road</div>
      <div style="color: #000000;"><span style="color: red;">- -</span> Rail</div>
      <div style="color: #000000;"><span style="color: purple;">&#183; &#183;</span> Air</div>
      <div style="color: #000000;"><span style="color: green;">- &#183; -</span> Waterways</div>
    </div>
    """
    route_map.get_root().html.add_child(folium.Element(legend))
    route_map.get_root().html.add_child(
        folium.Element(
            f"""
            <script>
            (function attachAlternativeRouteHandlers() {{
                function getMap() {{
                    if (window.map) return window.map;
                    return null;
                }}
                function visit(layer, callback) {{
                    if (layer.eachLayer) {{
                        layer.eachLayer(function (child) {{ visit(child, callback); }});
                    }} else {{
                        callback(layer);
                    }}
                }}
                function applySelection(map, routeId) {{
                    map.eachLayer(function (layer) {{
                        visit(layer, function (candidate) {{
                            if (candidate.options && candidate.options.route_id) {{
                                var selected = candidate.options.route_id === routeId;
                                candidate.setStyle({{
                                    color: selected ? '#38BDF8' : '#4a4a4a',
                                    weight: selected ? 6 : 2,
                                    opacity: selected ? 1.0 : 0.18
                                }});
                            }}
                        }});
                    }});
                }}
                var interval = setInterval(function () {{
                    var map = getMap();
                    if (!map) return;
                    var attached = 0;
                    map.eachLayer(function (layer) {{
                        visit(layer, function (candidate) {{
                            if (candidate.options && candidate.options.route_id) {{
                                attached += 1;
                                if (!candidate.__alternativeRouteHandlerAttached) {{
                                    candidate.__alternativeRouteHandlerAttached = true;
                                    candidate.on('click', function () {{
                                        applySelection(map, candidate.options.route_id);
                                    }});
                                }}
                            }}
                        }});
                    }});
                    if (attached >= 5) clearInterval(interval);
                }}, 100);
            }})();
            </script>
            """
        )
    )
    folium.LayerControl(collapsed=False).add_to(route_map)
    route_map.fit_bounds(bounds, padding=(20, 20))
    return route_map
