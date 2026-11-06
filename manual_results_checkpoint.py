"""Reproduce the sample results reported in RESEARCH_PAPER.md."""

from pathlib import Path

from backend.evaluation import benchmark
from backend.graph import load_graph


DATASET = Path("datasets/processed/dataset_10")
SOURCE = "C01"
DESTINATION = "C10"
OBJECTIVES = ("cost", "time", "emissions")
ALGORITHM_KWARGS = {
    "nsga2": {"population_size": 10, "generations": 3},
    "simulated_annealing": {"iterations": 30},
    "aco": {"ants": 10, "iterations": 30},
}


def main() -> None:
    graph = load_graph(DATASET)
    print(
        "dataset_10 | C01 -> C10 | repeats=1 | "
        "NSGA-II population=10 generations=3 | "
        "Simulated Annealing iterations=30"
    )
    print("objective,algorithm,value,gap_pct,time_ms,peak_memory_bytes,route")
    for objective in OBJECTIVES:
        records = benchmark(
            graph,
            SOURCE,
            DESTINATION,
            objective,
            repeats=1,
            algorithm_kwargs=ALGORITHM_KWARGS,
        )
        for record in records:
            print(
                f"{objective},{record.algorithm},{record.objective_value:.2f},"
                f"{record.optimality_gap:.2f},{record.execution_time_ms:.3f},"
                f"{record.peak_memory_bytes},{' -> '.join(record.nodes)}"
            )


if __name__ == "__main__":
    main()