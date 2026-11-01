import json
from pathlib import Path

import pytest

from backend.experiment_manager import ExperimentManager


DATASETS = Path(__file__).parents[1] / "datasets" / "processed"


def test_runs_only_selected_dataset_objective_combinations_and_persists(tmp_path: Path) -> None:
    result = ExperimentManager(DATASETS, tmp_path).run(
        ("dataset_10", "dataset_20"),
        ("cost", "time"),
        "C01",
        "C10",
        repeats=1,
        algorithm_kwargs={
            "nsga2": {"population_size": 10, "generations": 2},
            "simulated_annealing": {"iterations": 5},
        },
    )

    assert result.combination_count == 4
    assert result.algorithm_execution_count == 16
    assert set(result.comparison["dataset"]) == {"dataset_10", "dataset_20"}
    assert set(result.comparison["objective"]) == {"cost", "time"}
    assert result.csv_path is not None and result.csv_path.is_file()
    assert result.json_path is not None and result.json_path.is_file()
    payload = json.loads(result.json_path.read_text(encoding="utf-8"))
    assert payload["combination_count"] == 4
    assert payload["algorithm_execution_count"] == 16


def test_rejects_unselected_or_invalid_inputs_without_running(tmp_path: Path) -> None:
    manager = ExperimentManager(DATASETS, tmp_path)

    with pytest.raises(ValueError, match="Unknown dataset selection"):
        manager.run(("dataset_999",), ("cost",), "C01", "C10", persist=False)
    with pytest.raises(ValueError, match="Unsupported objective"):
        manager.run(("dataset_10",), ("distance",), "C01", "C10", persist=False)
    with pytest.raises(ValueError, match="different"):
        manager.run(("dataset_10",), ("cost",), "C01", "C01", persist=False)


def test_reports_disconnected_source_destination(tmp_path: Path) -> None:
    manager = ExperimentManager(DATASETS, tmp_path)

    with pytest.raises(ValueError, match="No route"):
        manager.run(("dataset_10",), ("cost",), "C01", "missing", persist=False)
