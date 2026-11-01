import csv
import json
from pathlib import Path

from backend.data.prepare_datasets import (
    CITY_FIELDS,
    CONNECTION_FIELDS,
    DATASET_SIZES,
    WATERWAY_CORRIDORS,
    generate_datasets,
)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_generates_all_required_dataset_sizes(tmp_path: Path) -> None:
    generated = generate_datasets(tmp_path)
    assert [path.name for path in generated] == [f"dataset_{size}" for size in DATASET_SIZES]
    for size in DATASET_SIZES:
        dataset_dir = tmp_path / "processed" / f"dataset_{size}"
        cities = _rows(dataset_dir / "cities.csv")
        connections = _rows(dataset_dir / "connections.csv")
        assert len(cities) == size
        assert len(connections) > 0
        assert set(cities[0]) == set(CITY_FIELDS)
        assert set(connections[0]) == set(CONNECTION_FIELDS)


def test_connections_have_valid_attributes_and_waterway_policy(tmp_path: Path) -> None:
    generate_datasets(tmp_path)
    for size in DATASET_SIZES:
        dataset_dir = tmp_path / "processed" / f"dataset_{size}"
        city_ids = {row["city_id"] for row in _rows(dataset_dir / "cities.csv")}
        for connection in _rows(dataset_dir / "connections.csv"):
            assert connection["source_city_id"] in city_ids
            assert connection["destination_city_id"] in city_ids
            assert float(connection["distance_km"]) > 0
            assert float(connection["cost"]) > 0
            assert float(connection["travel_time_hours"]) > 0
            assert float(connection["carbon_emissions_kg"]) > 0
            if connection["mode"] == "waterway":
                assert frozenset(
                    {connection["source_city_id"], connection["destination_city_id"]}
                ) in WATERWAY_CORRIDORS
                assert connection["waterway_validated"] == "true"


def test_metadata_distinguishes_reference_and_simulated_data(tmp_path: Path) -> None:
    generate_datasets(tmp_path)
    metadata = json.loads(
        (tmp_path / "processed" / "dataset_60" / "metadata.json").read_text(
            encoding="utf-8"
        )
    )
    assert metadata["coordinate_source"] == "manually_curated_reference"
    assert metadata["transport_attribute_source"] == "simulated_for_development"
