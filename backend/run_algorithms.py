"""Run the Phase 3 algorithm checkpoint."""

from __future__ import annotations

import argparse
from pathlib import Path

from .algorithms import optimize
from .graph import load_graph


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=Path("datasets/processed/dataset_10"))
    parser.add_argument("--source", default="C01")
    parser.add_argument("--destination", default="C10")
    parser.add_argument("--objective", choices=("cost", "time", "emissions"), default="cost")
    args = parser.parse_args()
    graph = load_graph(args.dataset_dir)
    for algorithm in ("dijkstra", "astar", "nsga2", "simulated_annealing", "aco"):
        kwargs = (
            {"population_size": 10, "generations": 3}
            if algorithm == "nsga2"
            else {"iterations": 30}
            if algorithm == "simulated_annealing"
            else {"ants": 5, "iterations": 10}
            if algorithm == "aco"
            else {}
        )
        result = optimize(
            algorithm, graph, args.source, args.destination, args.objective, **kwargs
        )
        print(
            f"{result.algorithm}: objective={result.objective_value:.2f}, "
            f"nodes={' -> '.join(result.nodes)}, modes={','.join(result.modes)}"
        )


if __name__ == "__main__":
    main()
