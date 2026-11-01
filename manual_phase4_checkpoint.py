
from pathlib import Path

from backend.graph import load_graph
from backend.evaluation import (
    FUNCTION_EVALUATION_NOTE,
    ITERATIVE_CONVERGENCE_NOTE,
    aggregate_statistics,
    benchmark,
    comparison_table,
)

# Load the 10-city transportation network
graph = load_graph(Path("datasets/processed/dataset_10"))

source = "C01"
destination = "C10"

algorithms = [
    "dijkstra",
    "astar",
    "nsga2",
    "simulated_annealing",
]

objectives = ["cost", "time", "emissions"]

algorithm_kwargs = {
    "nsga2": {
        "population_size": 10,
        "generations": 3,
    },
    "simulated_annealing": {
        "iterations": 30,
    },
}

for objective in objectives:

    print("\n" + "=" * 75)
    print(f"OBJECTIVE: {objective.upper()}")
    print("=" * 75)

    records = benchmark(
        graph,
        source,
        destination,
        objective,
        repeats=3,
        algorithm_kwargs=algorithm_kwargs,
    )

    table = comparison_table(records)

    columns = [
        "algorithm",
        "run",
        "valid",
        "objective_value",
        "optimality_gap",
        "execution_time_ms",
        "peak_memory_bytes",
        "function_evaluations",
        "execution_time_mean_ms",
        "execution_time_median_ms",
        "execution_time_stddev_ms",
        "peak_memory_mean_bytes",
        "peak_memory_median_bytes",
        "peak_memory_stddev_bytes",
    ]

    print(table[columns].to_string(index=False))

    print("\nCONVERGENCE INFORMATION")

    for _, row in table.iterrows():
        print(
            row["algorithm"],
            "Run:", row["run"],
            "Convergence points:", len(row["convergence"])
        )
    print("\nAGGREGATE STATISTICS")
    print(aggregate_statistics(records).to_string(index=False))

print("\nNOTES")
print(ITERATIVE_CONVERGENCE_NOTE)
print(FUNCTION_EVALUATION_NOTE)

print("\nPHASE 4 CHECKPOINT COMPLETED")
