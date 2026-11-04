"""Interactive schematic route maps for multimodal transportation routes."""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape
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


def prepare_route_map_data(
    graph: nx.MultiDiGraph,
    nodes: Sequence[str],
    edge_ids: Sequence[str],
    modes: Sequence[str],
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
    )


def create_route_map(route_data: RouteMapData) -> folium.Map:
    """Create an interactive schematic map from already-resolved route data."""
    route_map = folium.Map(location=INDIA_CENTER, zoom_start=5, tiles="OpenStreetMap")
    bounds = [route_data.city_coordinates[node] for node in route_data.nodes]

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
    route_map.fit_bounds(bounds, padding=(20, 20))
    return route_map
