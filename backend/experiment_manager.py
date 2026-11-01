"""User-controlled experiment orchestration and result persistence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable, Mapping
from uuid import uuid4

import pandas as pd

from .algorithms.common import validate_objective
from .evaluation import (
    BenchmarkRecord,
    benchmark,
)
from .graph import load_graph


@dataclass(frozen=True)
class ExperimentConfig:
    """Validated selections and execution settings for one experiment."""

    datasets: tuple[str, ...]
    objectives: tuple[str, ...]
    source: str
    destination: str
    repeats: int = 1


@dataclass(frozen=True)
class ExperimentResult:
    """Measured records and persisted paths for one experiment."""

    experiment_id: str
    config: ExperimentConfig
    records: tuple[dict[str, object], ...]
    comparison: pd.DataFrame
    experiment_name: str | None = None
    csv_path: Path | None = None
    json_path: Path | None = None

    @property
    def combination_count(self) -> int:
        return len(self.config.datasets) * len(self.config.objectives)

    @property
    def algorithm_execution_count(self) -> int:
        return len(self.records)


class ExperimentManager:
    """Execute only explicitly selected dataset/objective combinations."""

    def __init__(
        self,
        datasets_root: Path = Path("datasets/processed"),
        results_root: Path = Path("experiments/results"),
    ) -> None:
        self.datasets_root = Path(datasets_root)
        self.results_root = Path(results_root)

    def run(
        self,
        datasets: Iterable[str | Path],
        objectives: Iterable[str],
        source: str,
        destination: str,
        *,
        repeats: int = 1,
        algorithm_kwargs: Mapping[str, Mapping[str, object]] | None = None,
        persist: bool = True,
        experiment_id: str | None = None,
    ) -> ExperimentResult:
        config = self._validate_config(
            datasets, objectives, source, destination, repeats
        )
        selected_kwargs = algorithm_kwargs or {}
        records: list[dict[str, object]] = []

        for dataset in config.datasets:
            dataset_dir = self._resolve_dataset(dataset)
            graph = load_graph(dataset_dir)
            for objective in config.objectives:
                try:
                    measured = benchmark(
                        graph,
                        config.source,
                        config.destination,
                        objective,
                        repeats=config.repeats,
                        algorithm_kwargs=selected_kwargs,
                    )
                except (ValueError, KeyError) as exc:
                    raise ValueError(
                        f"Unable to run dataset {dataset!r} with objective "
                        f"{objective!r}: {exc}"
                    ) from exc
                records.extend(
                    _record_with_context(dataset, objective, record)
                    for record in measured
                )

        result = ExperimentResult(
            experiment_id=experiment_id or _new_experiment_id(),
            config=config,
            records=tuple(records),
            comparison=_comparison_with_context(records),
            experiment_name=_new_experiment_name(
                self.datasets_root,
                config.datasets,
                config.source,
                config.destination,
                self.results_root,
            ),
        )
        return self.save(result) if persist else result

    def save(self, result: ExperimentResult) -> ExperimentResult:
        """Persist configuration and measured rows as JSON and CSV."""
        self.results_root.mkdir(parents=True, exist_ok=True)
        csv_path = self.results_root / f"{result.experiment_id}.csv"
        json_path = self.results_root / f"{result.experiment_id}.json"
        table = result.comparison.copy()
        for column in ("convergence", "nodes", "edge_ids", "modes"):
            if column in table:
                table[column] = table[column].map(
                    lambda value: json.dumps(value, separators=(",", ":"))
                )
        table.to_csv(csv_path, index=False)
        payload = {
            "experiment_id": result.experiment_id,
            "experiment_name": result.experiment_name,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "configuration": {
                "datasets": list(result.config.datasets),
                "objectives": list(result.config.objectives),
                "source": result.config.source,
                "destination": result.config.destination,
                "repeats": result.config.repeats,
            },
            "combination_count": result.combination_count,
            "algorithm_execution_count": result.algorithm_execution_count,
            "records": [_jsonable_record(record) for record in result.records],
        }
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return ExperimentResult(
            result.experiment_id,
            result.config,
            result.records,
            result.comparison,
            result.experiment_name,
            csv_path,
            json_path,
        )

    def _validate_config(
        self,
        datasets: Iterable[str | Path],
        objectives: Iterable[str],
        source: str,
        destination: str,
        repeats: int,
    ) -> ExperimentConfig:
        selected_datasets = tuple(str(dataset) for dataset in datasets)
        selected_objectives = tuple(objectives)
        if not selected_datasets:
            raise ValueError("At least one dataset must be selected")
        if len(set(selected_datasets)) != len(selected_datasets):
            raise ValueError("Dataset selections must be unique")
        if not selected_objectives:
            raise ValueError("At least one objective must be selected")
        if len(set(selected_objectives)) != len(selected_objectives):
            raise ValueError("Objective selections must be unique")
        for objective in selected_objectives:
            validate_objective(objective)
        if not source or not destination or source == destination:
            raise ValueError("Source and destination must be different and non-empty")
        if repeats < 1:
            raise ValueError("repeats must be positive")
        for dataset in selected_datasets:
            self._resolve_dataset(dataset)
        return ExperimentConfig(
            selected_datasets,
            selected_objectives,
            source,
            destination,
            repeats,
        )

    def _resolve_dataset(self, dataset: str) -> Path:
        candidate = Path(dataset)
        if not candidate.is_absolute():
            candidate = self.datasets_root / candidate
        if not candidate.is_dir():
            raise ValueError(f"Unknown dataset selection: {dataset}")
        if not (candidate / "cities.csv").is_file() or not (
            candidate / "connections.csv"
        ).is_file():
            raise ValueError(f"Dataset is missing required files: {dataset}")
        return candidate


def run_experiment(
    datasets: Iterable[str | Path],
    objectives: Iterable[str],
    source: str,
    destination: str,
    *,
    datasets_root: Path = Path("datasets/processed"),
    results_root: Path = Path("experiments/results"),
    repeats: int = 1,
    algorithm_kwargs: Mapping[str, Mapping[str, object]] | None = None,
    persist: bool = True,
    experiment_id: str | None = None,
) -> ExperimentResult:
    """Convenience wrapper around :class:`ExperimentManager`."""
    return ExperimentManager(datasets_root, results_root).run(
        datasets,
        objectives,
        source,
        destination,
        repeats=repeats,
        algorithm_kwargs=algorithm_kwargs,
        persist=persist,
        experiment_id=experiment_id,
    )


def _record_with_context(
    dataset: str, objective: str, record: BenchmarkRecord
) -> dict[str, object]:
    row = record.as_dict()
    row["dataset"] = dataset
    row["objective"] = objective
    return row


def _comparison_with_context(records: Iterable[dict[str, object]]) -> pd.DataFrame:
    rows = list(records)
    if not rows:
        return pd.DataFrame()
    table = pd.DataFrame(rows)
    grouped = table.groupby(["dataset", "algorithm", "objective"], as_index=False)
    statistics = grouped.agg(
        execution_time_mean_ms=("execution_time_ms", "mean"),
        execution_time_median_ms=("execution_time_ms", "median"),
        execution_time_stddev_ms=("execution_time_ms", lambda values: values.std(ddof=0)),
        peak_memory_mean_bytes=("peak_memory_bytes", "mean"),
        peak_memory_median_bytes=("peak_memory_bytes", "median"),
        peak_memory_stddev_bytes=("peak_memory_bytes", lambda values: values.std(ddof=0)),
    )
    return table.merge(
        statistics, on=["dataset", "algorithm", "objective"], how="left"
    )


def _jsonable_record(record: Mapping[str, object]) -> dict[str, object]:
    return {
        key: list(value) if isinstance(value, tuple) else value
        for key, value in record.items()
    }


def _new_experiment_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"experiment-{timestamp}-{uuid4().hex[:8]}"


def _city_abbreviation(city_name: str) -> str:
    """Create a short readable abbreviation from a dataset city name."""
    letters = "".join(character for character in city_name.upper() if character.isalpha())
    return (letters[:3] or "CITY").upper()


def _distinct_city_abbreviations(source_name: str, destination_name: str) -> tuple[str, str]:
    source_letters = "".join(character for character in source_name.upper() if character.isalpha())
    destination_letters = "".join(
        character for character in destination_name.upper() if character.isalpha()
    )
    source_code = _city_abbreviation(source_name)
    destination_code = _city_abbreviation(destination_name)
    if source_code != destination_code:
        return source_code, destination_code
    for length in range(4, max(len(source_letters), len(destination_letters)) + 1):
        source_code = source_letters[:length] or "CITY"
        destination_code = destination_letters[:length] or "CITY"
        if source_code != destination_code:
            return source_code, destination_code
    return f"{source_code}_1", f"{destination_code}_2"


def experiment_name(
    datasets_root: Path,
    datasets: Iterable[str],
    source: str,
    destination: str,
) -> str:
    """Build the base human-readable name for an experiment configuration."""
    selected_dataset = next(iter(datasets), None)
    if selected_dataset is None:
        raise ValueError("At least one dataset is required to name an experiment")
    graph = load_graph(Path(datasets_root) / selected_dataset)
    try:
        source_name = str(graph.nodes[source]["city_name"])
        destination_name = str(graph.nodes[destination]["city_name"])
    except KeyError as exc:
        raise ValueError(f"Unable to name experiment for unknown city: {exc}") from exc
    source_code, destination_code = _distinct_city_abbreviations(
        source_name, destination_name
    )
    return f"Exp_D{graph.number_of_nodes()}_{source_code}_{destination_code}"


def _new_experiment_name(
    datasets_root: Path,
    datasets: Iterable[str],
    source: str,
    destination: str,
    results_root: Path,
) -> str:
    base_name = experiment_name(datasets_root, datasets, source, destination)
    existing_names: set[str] = set()
    if results_root.is_dir():
        for path in results_root.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            saved_name = payload.get("experiment_name")
            if isinstance(saved_name, str):
                existing_names.add(saved_name)
    if base_name not in existing_names:
        return base_name
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    return f"{base_name}_{timestamp}_{uuid4().hex[:6]}"
