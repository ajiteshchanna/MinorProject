"""Run the Phase 5 user-controlled experiment checkpoint."""

from pathlib import Path

from backend.experiment_manager import ExperimentManager


def main() -> None:
    manager = ExperimentManager(
        datasets_root=Path("datasets/processed"),
        results_root=Path("experiments/results"),
    )
    result = manager.run(
        ("dataset_10", "dataset_20"),
        ("cost", "time"),
        "C01",
        "C10",
        repeats=1,
        algorithm_kwargs={
            "nsga2": {"population_size": 10, "generations": 3},
            "simulated_annealing": {"iterations": 30},
        },
    )
    print(f"Experiment: {result.experiment_id}")
    print(f"Combinations: {result.combination_count}")
    print(f"Algorithm executions: {result.algorithm_execution_count}")
    print(f"CSV: {result.csv_path}")
    print(f"JSON: {result.json_path}")
    print(
        result.comparison[
            ["dataset", "objective", "algorithm", "run", "valid", "objective_value"]
        ].to_string(index=False)
    )
    print("PHASE 5 CHECKPOINT COMPLETED")


if __name__ == "__main__":
    main()
