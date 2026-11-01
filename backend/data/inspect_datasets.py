"""Inspect generated Phase 1 datasets and report basic network statistics."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .prepare_datasets import DATASET_SIZES


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def inspect_dataset(dataset_dir: Path) -> dict[str, object]:
    cities = _read_rows(dataset_dir / "cities.csv")
    connections = _read_rows(dataset_dir / "connections.csv")
    city_ids = {row["city_id"] for row in cities}
    adjacency = {city_id: set() for city_id in city_ids}
    for connection in connections:
        adjacency[connection["source_city_id"]].add(connection["destination_city_id"])
    reachable = set()
    frontier = [next(iter(city_ids))] if city_ids else []
    while frontier:
        city_id = frontier.pop()
        if city_id in reachable:
            continue
        reachable.add(city_id)
        frontier.extend(adjacency[city_id] - reachable)
    return {
        "dataset": dataset_dir.name,
        "cities": len(cities),
        "directed_edges": len(connections),
        "modes": sorted({row["mode"] for row in connections}),
        "connected_undirected": len(reachable) == len(city_ids),
        "waterway_edges": sum(row["mode"] == "waterway" for row in connections),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--datasets-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "datasets" / "processed",
    )
    args = parser.parse_args()
    for size in DATASET_SIZES:
        report = inspect_dataset(args.datasets_dir / f"dataset_{size}")
        print(
            f"{report['dataset']}: cities={report['cities']}, "
            f"edges={report['directed_edges']}, modes={','.join(report['modes'])}, "
            f"waterway_edges={report['waterway_edges']}, "
            f"connected={report['connected_undirected']}"
        )


if __name__ == "__main__":
    main()
