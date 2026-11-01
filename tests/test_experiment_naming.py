import json
from pathlib import Path

from backend.experiment_manager import ExperimentManager, experiment_name


DATASETS = Path(__file__).parents[1] / "datasets" / "processed"


def test_experiment_name_uses_dataset_size_and_city_names() -> None:
    assert experiment_name(DATASETS, ("dataset_10",), "C01", "C02") == "Exp_D10_AHM_AMR"
    assert experiment_name(DATASETS, ("dataset_30",), "C10", "C30") == "Exp_D30_DEL_MUM"


def test_duplicate_experiments_keep_unique_ids_and_get_name_suffix(tmp_path: Path) -> None:
    manager = ExperimentManager(DATASETS, tmp_path)
    kwargs = {
        "nsga2": {"population_size": 2, "generations": 1},
        "simulated_annealing": {"iterations": 1},
    }
    first = manager.run(("dataset_10",), ("cost",), "C01", "C02", algorithm_kwargs=kwargs)
    second = manager.run(("dataset_10",), ("cost",), "C01", "C02", algorithm_kwargs=kwargs)

    assert first.experiment_id != second.experiment_id
    assert first.experiment_name == "Exp_D10_AHM_AMR"
    assert second.experiment_name.startswith("Exp_D10_AHM_AMR_")
    first_payload = json.loads(first.json_path.read_text(encoding="utf-8"))
    second_payload = json.loads(second.json_path.read_text(encoding="utf-8"))
    assert first_payload["experiment_id"] != second_payload["experiment_id"]
    assert first_payload["experiment_name"] == first.experiment_name
    assert second_payload["experiment_name"] == second.experiment_name


def test_old_record_without_name_remains_readable(tmp_path: Path) -> None:
    payload = {
        "experiment_id": "experiment-legacy",
        "configuration": {
            "datasets": ["dataset_10"],
            "source": "C01",
            "destination": "C02",
        },
    }
    path = tmp_path / "experiment-legacy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8"))["experiment_id"] == "experiment-legacy"
