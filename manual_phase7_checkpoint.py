"""Run the Phase 7 integration checkpoint across every supported dataset."""

from pathlib import Path

from backend.algorithms import optimize
from backend.evaluation import validate_route
from backend.graph import load_graph

DATASETS_ROOT = Path("datasets/processed")
DATASET_NAMES = tuple(f"dataset_{size}" for size in (10, 20, 30, 40, 50, 60))
OBJECTIVES = ("cost", "time", "emissions")
ALGORITHMS = ("dijkstra", "astar", "nsga2", "simulated_annealing", "aco")


def main() -> None:
    executions = 0
    for dataset_name in DATASET_NAMES:
        graph = load_graph(DATASETS_ROOT / dataset_name)
        for objective in OBJECTIVES:
            values = {}
            for algorithm in ALGORITHMS:
                kwargs = (
                    {"population_size": 4, "generations": 1}
                    if algorithm == "nsga2"
                    else {"iterations": 5}
                    if algorithm == "simulated_annealing"
                    else {"ants": 3, "iterations": 3}
                    if algorithm == "aco"
                    else {}
                )
                result = optimize(
                    algorithm, graph, "C01", "C10", objective, **kwargs
                )
                validation = validate_route(graph, result)
                if not validation.valid:
                    raise AssertionError(
                        f"{dataset_name}/{objective}/{algorithm}: "
                        f"{validation.errors}"
                    )
                values[algorithm] = validation.metrics[objective]
                executions += 1
            print(
                f"{dataset_name} | {objective} | "
                + ", ".join(f"{name}={value:.2f}" for name, value in values.items())
            )
    print(f"\nValidated executions: {executions}")
    print("PHASE 7 CHECKPOINT COMPLETED")


if __name__ == "__main__":
    main()
