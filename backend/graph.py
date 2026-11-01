"""Build and validate multimodal transportation graphs."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Mapping

import networkx as nx

CITY_REQUIRED_FIELDS = {
    "city_id",
    "city_name",
    "country",
    "latitude",
    "longitude",
}
EDGE_REQUIRED_FIELDS = {
    "connection_id",
    "source_city_id",
    "destination_city_id",
    "mode",
    "distance_km",
    "cost",
    "travel_time_hours",
    "carbon_emissions_kg",
}
OBJECTIVE_ATTRIBUTES = (
    "distance_km",
    "cost",
    "travel_time_hours",
    "carbon_emissions_kg",
)


class GraphDataError(ValueError):
    """Raised when dataset rows cannot form a valid transportation graph."""


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except OSError as exc:
        raise GraphDataError(f"Unable to read dataset file: {path}") from exc


def load_dataset(dataset_dir: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Load city and connection rows from a processed dataset directory."""
    cities = _read_csv(dataset_dir / "cities.csv")
    connections = _read_csv(dataset_dir / "connections.csv")
    return cities, connections


def _require_fields(row: Mapping[str, str], required: set[str], row_type: str) -> None:
    missing = sorted(field for field in required if not row.get(field))
    if missing:
        raise GraphDataError(f"{row_type} is missing required fields: {', '.join(missing)}")


def _numeric_attributes(row: Mapping[str, str], row_number: int) -> dict[str, float]:
    values: dict[str, float] = {}
    for field in OBJECTIVE_ATTRIBUTES:
        try:
            value = float(row[field])
        except (KeyError, TypeError, ValueError) as exc:
            raise GraphDataError(
                f"Connection row {row_number} has invalid {field}: {row.get(field)!r}"
            ) from exc
        if value <= 0:
            raise GraphDataError(
                f"Connection row {row_number} has non-positive {field}: {value}"
            )
        values[field] = value
    return values


def build_graph(
    cities: Iterable[Mapping[str, str]],
    connections: Iterable[Mapping[str, str]],
) -> nx.MultiDiGraph:
    """Build a validated directed multimodal graph.

    Each city is a node keyed by ``city_id``. Each connection is an edge keyed
    by ``connection_id`` so its transport mode and attributes remain recoverable.
    """
    city_rows = list(cities)
    connection_rows = list(connections)
    graph = nx.MultiDiGraph()
    city_ids: set[str] = set()

    for row_number, city in enumerate(city_rows, start=2):
        _require_fields(city, CITY_REQUIRED_FIELDS, f"City row {row_number}")
        city_id = city["city_id"]
        if city_id in city_ids:
            raise GraphDataError(f"Duplicate city_id: {city_id}")
        try:
            latitude = float(city["latitude"])
            longitude = float(city["longitude"])
        except (TypeError, ValueError) as exc:
            raise GraphDataError(f"City row {row_number} has invalid coordinates") from exc
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise GraphDataError(f"City row {row_number} has out-of-range coordinates")
        city_ids.add(city_id)
        graph.add_node(
            city_id,
            city_name=city["city_name"],
            country=city["country"],
            latitude=latitude,
            longitude=longitude,
            coordinate_source=city.get("coordinate_source", ""),
            waterway_corridor=city.get("waterway_corridor", ""),
        )

    connection_ids: set[str] = set()
    for row_number, connection in enumerate(connection_rows, start=2):
        _require_fields(connection, EDGE_REQUIRED_FIELDS, f"Connection row {row_number}")
        connection_id = connection["connection_id"]
        if connection_id in connection_ids:
            raise GraphDataError(f"Duplicate connection_id: {connection_id}")
        source = connection["source_city_id"]
        destination = connection["destination_city_id"]
        if source not in city_ids or destination not in city_ids:
            raise GraphDataError(
                f"Connection {connection_id} references an unknown city: "
                f"{source!r} -> {destination!r}"
            )
        if source == destination:
            raise GraphDataError(f"Connection {connection_id} is a self-loop")
        attributes = _numeric_attributes(connection, row_number)
        connection_ids.add(connection_id)
        graph.add_edge(
            source,
            destination,
            key=connection_id,
            connection_id=connection_id,
            mode=connection["mode"],
            **attributes,
            attribute_source=connection.get("attribute_source", ""),
            waterway_validated=connection.get("waterway_validated", ""),
        )
    return graph


def load_graph(dataset_dir: Path) -> nx.MultiDiGraph:
    """Load and build a graph from a processed dataset directory."""
    cities, connections = load_dataset(dataset_dir)
    return build_graph(cities, connections)


def connectivity_report(graph: nx.MultiDiGraph) -> dict[str, bool]:
    """Return weak and strong connectivity status for a directed graph."""
    if graph.number_of_nodes() == 0:
        return {"weakly_connected": False, "strongly_connected": False}
    return {
        "weakly_connected": nx.is_weakly_connected(graph),
        "strongly_connected": nx.is_strongly_connected(graph),
    }


def parallel_mode_pairs(graph: nx.MultiDiGraph) -> dict[tuple[str, str], tuple[str, ...]]:
    """Return source/destination pairs that have more than one transport mode."""
    pairs: dict[tuple[str, str], tuple[str, ...]] = {}
    for source, destination in graph.edges():
        modes = tuple(
            sorted(
                {
                    str(data["mode"])
                    for data in graph.get_edge_data(source, destination, default={}).values()
                }
            )
        )
        if len(modes) > 1:
            pairs[(source, destination)] = modes
    return pairs
