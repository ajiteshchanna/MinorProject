"""Run the Phase 2 graph construction checkpoint."""

from __future__ import annotations

import argparse
from pathlib import Path

from .data.prepare_datasets import DATASET_SIZES
from .graph import connectivity_report, load_graph, parallel_mode_pairs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--datasets-dir",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "datasets" / "processed",
    )
    parser.add_argument("--dataset-size", type=int, choices=DATASET_SIZES)
    args = parser.parse_args()
    sizes = (args.dataset_size,) if args.dataset_size else DATASET_SIZES

    for size in sizes:
        graph = load_graph(args.datasets_dir / f"dataset_{size}")
        connectivity = connectivity_report(graph)
        parallel_pairs = parallel_mode_pairs(graph)
        print(
            f"dataset_{size}: nodes={graph.number_of_nodes()}, "
            f"edges={graph.number_of_edges()}, "
            f"weakly_connected={connectivity['weakly_connected']}, "
            f"strongly_connected={connectivity['strongly_connected']}, "
            f"parallel_mode_pairs={len(parallel_pairs)}"
        )
        if parallel_pairs:
            sample_pair, modes = next(iter(sorted(parallel_pairs.items())))
            print(f"  sample parallel pair {sample_pair[0]} -> {sample_pair[1]}: {', '.join(modes)}")


if __name__ == "__main__":
    main()
