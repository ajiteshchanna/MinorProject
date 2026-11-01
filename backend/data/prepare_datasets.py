"""Create deterministic Phase 1 transportation datasets.

City coordinates are manually curated reference data. Transport costs, times,
emissions and connections are simulated for reproducible development and are
labelled accordingly in every generated record.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Iterable

CITY_FIELDS = [
    "city_id",
    "city_name",
    "country",
    "latitude",
    "longitude",
    "coordinate_source",
    "waterway_corridor",
]
CONNECTION_FIELDS = [
    "connection_id",
    "source_city_id",
    "destination_city_id",
    "mode",
    "distance_km",
    "cost",
    "travel_time_hours",
    "carbon_emissions_kg",
    "attribute_source",
    "waterway_validated",
]

CITY_DATA = [
    ("C01", "Ahmedabad", 23.0225, 72.5714, ""),
    ("C02", "Amritsar", 31.6340, 74.8723, ""),
    ("C03", "Bengaluru", 12.9716, 77.5946, ""),
    ("C04", "Bhopal", 23.2599, 77.4126, ""),
    ("C05", "Bhubaneswar", 20.2961, 85.8245, "east_coast"),
    ("C06", "Chandigarh", 30.7333, 76.7794, ""),
    ("C07", "Chennai", 13.0827, 80.2707, "east_coast"),
    ("C08", "Coimbatore", 11.0168, 76.9558, ""),
    ("C09", "Dehradun", 30.3165, 78.0322, ""),
    ("C10", "Delhi", 28.6139, 77.2090, ""),
    ("C11", "Guwahati", 26.1445, 91.7362, ""),
    ("C12", "Goa", 15.2993, 74.1240, "west_coast"),
    ("C13", "Gurugram", 28.4595, 77.0266, ""),
    ("C14", "Gwalior", 26.2183, 78.1828, ""),
    ("C15", "Hyderabad", 17.3850, 78.4867, ""),
    ("C16", "Indore", 22.7196, 75.8577, ""),
    ("C17", "Jaipur", 26.9124, 75.7873, ""),
    ("C18", "Jammu", 32.7266, 74.8570, ""),
    ("C19", "Jamshedpur", 22.8046, 86.2029, ""),
    ("C20", "Jodhpur", 26.2389, 73.0243, ""),
    ("C21", "Kanpur", 26.4499, 80.3319, ""),
    ("C22", "Kochi", 9.9312, 76.2673, "west_coast"),
    ("C23", "Kolkata", 22.5726, 88.3639, "east_coast"),
    ("C24", "Kota", 25.2138, 75.8648, ""),
    ("C25", "Lucknow", 26.8467, 80.9462, ""),
    ("C26", "Ludhiana", 30.9010, 75.8573, ""),
    ("C27", "Madurai", 9.9252, 78.1198, ""),
    ("C28", "Mangaluru", 12.9141, 74.8560, "west_coast"),
    ("C29", "Meerut", 28.9845, 77.7064, ""),
    ("C30", "Mumbai", 19.0760, 72.8777, "west_coast"),
    ("C31", "Mysuru", 12.2958, 76.6394, ""),
    ("C32", "Nagpur", 21.1458, 79.0882, ""),
    ("C33", "Nashik", 19.9975, 73.7898, ""),
    ("C34", "Noida", 28.5355, 77.3910, ""),
    ("C35", "Patna", 25.5941, 85.1376, ""),
    ("C36", "Prayagraj", 25.4358, 81.8463, ""),
    ("C37", "Pune", 18.5204, 73.8567, ""),
    ("C38", "Raipur", 21.2514, 81.6296, ""),
    ("C39", "Rajkot", 22.3039, 70.8022, ""),
    ("C40", "Ranchi", 23.3441, 85.3096, ""),
    ("C41", "Shimla", 31.1048, 77.1734, ""),
    ("C42", "Siliguri", 26.7271, 88.3953, ""),
    ("C43", "Srinagar", 34.0837, 74.7973, ""),
    ("C44", "Surat", 21.1702, 72.8311, "west_coast"),
    ("C45", "Thiruvananthapuram", 8.5241, 76.9366, ""),
    ("C46", "Thrissur", 10.5276, 76.2144, ""),
    ("C47", "Tiruchirappalli", 10.7905, 78.7047, ""),
    ("C48", "Udaipur", 24.5854, 73.7125, ""),
    ("C49", "Vadodara", 22.3072, 73.1812, ""),
    ("C50", "Varanasi", 25.3176, 82.9739, ""),
    ("C51", "Vijayawada", 16.5062, 80.6480, "east_coast"),
    ("C52", "Visakhapatnam", 17.6868, 83.2185, "east_coast"),
    ("C53", "Agra", 27.1767, 78.0081, ""),
    ("C54", "Aurangabad", 19.8762, 75.3433, ""),
    ("C55", "Bareilly", 28.3670, 79.4304, ""),
    ("C56", "Dhanbad", 23.7957, 86.4304, ""),
    ("C57", "Durgapur", 23.5204, 87.3119, ""),
    ("C58", "Kozhikode", 11.2588, 75.7804, "west_coast"),
    ("C59", "Puducherry", 11.9416, 79.8083, "east_coast"),
    ("C60", "Jabalpur", 23.1815, 79.9864, ""),
]

# Only these explicitly documented corridors may receive waterways.
WATERWAY_CORRIDORS = {
    frozenset({"C30", "C44"}),  # Mumbai-Surat coastal corridor
    frozenset({"C07", "C52"}),  # Chennai-Visakhapatnam coastal corridor
    frozenset({"C52", "C23"}),  # Visakhapatnam-Kolkata coastal corridor
    frozenset({"C22", "C28"}),  # Kochi-Mangaluru coastal corridor
    frozenset({"C23", "C05"}),  # Kolkata-Bhubaneswar coastal corridor
}

MODES = ("road", "rail", "air", "waterway")
DATASET_SIZES = (10, 20, 30, 40, 50, 60)


def _haversine_km(first: tuple[float, float], second: tuple[float, float]) -> float:
    radius_km = 6371.0
    lat1, lon1 = map(math.radians, first)
    lat2, lon2 = map(math.radians, second)
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(value))


def _cities() -> list[dict[str, object]]:
    return [
        {
            "city_id": city_id,
            "city_name": name,
            "country": "India",
            "latitude": latitude,
            "longitude": longitude,
            "coordinate_source": "manually_curated_reference",
            "waterway_corridor": corridor,
        }
        for city_id, name, latitude, longitude, corridor in CITY_DATA
    ]


def _connection(
    source: dict[str, object], destination: dict[str, object], mode: str
) -> dict[str, object]:
    source_id = str(source["city_id"])
    destination_id = str(destination["city_id"])
    distance = _haversine_km(
        (float(source["latitude"]), float(source["longitude"])),
        (float(destination["latitude"]), float(destination["longitude"])),
    )
    factors = {
        "road": (1.18, 8.0, 0.120),
        "rail": (0.95, 10.0, 0.045),
        "air": (1.65, 2.0, 0.255),
        "waterway": (0.60, 16.0, 0.030),
    }
    cost_factor, speed_factor, emission_factor = factors[mode]
    return {
        "connection_id": f"{source_id}_{destination_id}_{mode}",
        "source_city_id": source_id,
        "destination_city_id": destination_id,
        "mode": mode,
        "distance_km": round(distance, 2),
        "cost": round(distance * cost_factor, 2),
        "travel_time_hours": round(distance / (speed_factor * 10), 2),
        "carbon_emissions_kg": round(distance * emission_factor, 2),
        "attribute_source": "simulated_for_development",
        "waterway_validated": str(mode != "waterway" or frozenset({source_id, destination_id}) in WATERWAY_CORRIDORS).lower(),
    }


def _connections(cities: list[dict[str, object]]) -> list[dict[str, object]]:
    connections: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()

    def add_pair(first: dict[str, object], second: dict[str, object], modes: Iterable[str]) -> None:
        for mode in modes:
            for source, destination in ((first, second), (second, first)):
                key = (str(source["city_id"]), str(destination["city_id"]), mode)
                if key not in seen:
                    connections.append(_connection(source, destination, mode))
                    seen.add(key)

    for index, city in enumerate(cities):
        prior = cities[:index]
        if not prior:
            continue
        nearest = min(
            prior,
            key=lambda candidate: _haversine_km(
                (float(city["latitude"]), float(city["longitude"])),
                (float(candidate["latitude"]), float(candidate["longitude"])),
            ),
        )
        add_pair(city, nearest, ("road", "rail", "air"))
        if index >= 2:
            add_pair(city, cities[index - 2], ("road", "air"))

    city_by_id = {str(city["city_id"]): city for city in cities}
    for pair in WATERWAY_CORRIDORS:
        if pair.issubset(city_by_id):
            first, second = (city_by_id[city_id] for city_id in sorted(pair))
            add_pair(first, second, ("waterway",))
    return connections


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def generate_datasets(output_dir: Path) -> list[Path]:
    """Generate the master data and six deterministic processed datasets."""
    output_dir = output_dir.resolve()
    raw_dir = output_dir / "raw"
    processed_dir = output_dir / "processed"
    cities = _cities()
    _write_csv(raw_dir / "cities_master.csv", cities, CITY_FIELDS)
    _write_csv(raw_dir / "connections_master.csv", _connections(cities), CONNECTION_FIELDS)

    generated: list[Path] = []
    for size in DATASET_SIZES:
        dataset_dir = processed_dir / f"dataset_{size}"
        selected_cities = cities[:size]
        selected_ids = {str(city["city_id"]) for city in selected_cities}
        connections = [
            connection
            for connection in _connections(selected_cities)
            if str(connection["source_city_id"]) in selected_ids
            and str(connection["destination_city_id"]) in selected_ids
        ]
        _write_csv(dataset_dir / "cities.csv", selected_cities, CITY_FIELDS)
        _write_csv(dataset_dir / "connections.csv", connections, CONNECTION_FIELDS)
        metadata = {
            "dataset_name": f"dataset_{size}",
            "city_count": size,
            "coordinate_source": "manually_curated_reference",
            "transport_attribute_source": "simulated_for_development",
            "waterway_policy": "Only explicitly documented coastal corridors are included.",
            "waterway_corridors": sorted(
                "-".join(sorted(pair))
                for pair in WATERWAY_CORRIDORS
                if pair.issubset(selected_ids)
            ),
        }
        (dataset_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
        generated.append(dataset_dir)
    return generated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "datasets",
        help="Directory containing raw/ and processed/ output folders.",
    )
    args = parser.parse_args()
    generated = generate_datasets(args.output_dir)
    print(f"Generated master data and {len(generated)} processed datasets in {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
