"""Interactive Streamlit dashboard for route optimization experiments."""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

from backend.experiment_manager import ExperimentManager, ExperimentResult
from backend.graph import load_graph

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASETS_ROOT = PROJECT_ROOT / "datasets" / "processed"
RESULTS_ROOT = PROJECT_ROOT / "experiments" / "results"
OBJECTIVES = ("cost", "time", "emissions")
OBJECTIVE_LABELS = {
    "cost": "Cost",
    "time": "Travel time",
    "emissions": "Carbon emissions",
}


def available_datasets() -> list[str]:
    """Return processed datasets that contain the required graph files."""
    if not DATASETS_ROOT.is_dir():
        return []
    return sorted(
        directory.name
        for directory in DATASETS_ROOT.iterdir()
        if directory.is_dir()
        and (directory / "cities.csv").is_file()
        and (directory / "connections.csv").is_file()
    )


def city_options(dataset: str) -> list[str]:
    """Load city IDs only for the currently selected preview dataset."""
    graph = load_graph(DATASETS_ROOT / dataset)
    return sorted(str(node) for node in graph.nodes)


def _algorithm_kwargs(population_size: int, generations: int, iterations: int) -> dict[str, dict[str, int]]:
    return {
        "nsga2": {
            "population_size": population_size,
            "generations": generations,
        },
        "simulated_annealing": {"iterations": iterations},
    }


def _format_comparison(table: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "dataset",
        "objective",
        "algorithm",
        "run",
        "valid",
        "cost",
        "time",
        "emissions",
        "objective_value",
        "optimality_gap",
        "execution_time_ms",
        "peak_memory_bytes",
    ]
    available = [column for column in columns if column in table]
    formatted = table[available].copy()
    if "objective" in formatted:
        formatted["objective"] = formatted["objective"].map(OBJECTIVE_LABELS)
    return formatted


def _show_routes(result: ExperimentResult) -> None:
    st.subheader("Optimized routes")
    route_rows = []
    for record in result.records:
        route_rows.append(
            {
                "dataset": record["dataset"],
                "objective": OBJECTIVE_LABELS[str(record["objective"])],
                "algorithm": record["algorithm"],
                "run": record["run"],
                "route": " -> ".join(record["nodes"]),
                "modes": " -> ".join(record["modes"]),
            }
        )
    st.dataframe(pd.DataFrame(route_rows), use_container_width=True, hide_index=True)


def _show_charts(result: ExperimentResult) -> None:
    table = result.comparison
    st.subheader("Comparisons")
    chart_data = (
        table.groupby(["dataset", "objective", "algorithm"], as_index=False)
        .agg(
            objective_value=("objective_value", "mean"),
            execution_time_ms=("execution_time_ms", "mean"),
            peak_memory_bytes=("peak_memory_bytes", "mean"),
        )
    )
    chart_data["objective"] = chart_data["objective"].map(OBJECTIVE_LABELS)
    st.plotly_chart(
        px.bar(
            chart_data,
            x="algorithm",
            y="objective_value",
            color="algorithm",
            facet_col="objective",
            facet_row="dataset",
            title="Mean objective value",
        ),
        use_container_width=True,
    )
    st.caption("Objective values use the selected objective's native units.")
    st.plotly_chart(
        px.scatter(
            chart_data,
            x="execution_time_ms",
            y="peak_memory_bytes",
            color="algorithm",
            symbol="objective",
            hover_data=["dataset"],
            title="Mean execution time versus peak memory",
        ),
        use_container_width=True,
    )
    st.caption("Execution time is milliseconds; memory is peak bytes measured by tracemalloc.")
    convergence_rows = []
    for record in result.records:
        for step, value in enumerate(record["convergence"], start=1):
            convergence_rows.append(
                {
                    "dataset": record["dataset"],
                    "objective": OBJECTIVE_LABELS[str(record["objective"])],
                    "algorithm": record["algorithm"],
                    "run": record["run"],
                    "step": step,
                    "best_so_far": value,
                }
            )
    if convergence_rows:
        st.plotly_chart(
            px.line(
                pd.DataFrame(convergence_rows),
                x="step",
                y="best_so_far",
                color="algorithm",
                facet_row="objective",
                facet_col="dataset",
                line_dash="run",
                markers=True,
                title="Best-so-far convergence",
            ),
            use_container_width=True,
        )
        st.caption("Dijkstra and A* are single-pass searches and therefore have no convergence series.")


def _show_history() -> None:
    st.subheader("Experiment history")
    history = sorted(RESULTS_ROOT.glob("*.json"), reverse=True) if RESULTS_ROOT.is_dir() else []
    if not history:
        st.info("No saved experiments yet.")
        return
    selected = st.selectbox("Saved experiment", history, format_func=lambda path: path.stem)
    try:
        payload = json.loads(selected.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        st.error(f"Unable to read saved experiment: {exc}")
        return
    st.json(
        {
            "experiment_id": payload.get("experiment_id"),
            "created_at": payload.get("created_at"),
            "configuration": payload.get("configuration"),
            "combination_count": payload.get("combination_count"),
            "algorithm_execution_count": payload.get("algorithm_execution_count"),
        }
    )


def main() -> None:
    st.set_page_config(
        page_title="Multimodal Route Optimization",
        page_icon="🚆",
        layout="wide",
    )
    st.title("Multimodal Transportation Route Optimization")
    st.caption("Run measured classical optimization experiments across selected datasets and objectives.")

    datasets = available_datasets()
    if not datasets:
        st.error(f"No processed datasets found under {DATASETS_ROOT}.")
        return

    with st.sidebar:
        st.header("Experiment setup")
        selected_datasets = st.multiselect(
            "Datasets",
            datasets,
            default=[datasets[0]],
            help="Only selected datasets are loaded and executed.",
        )
        selected_objectives = st.multiselect(
            "Objectives",
            OBJECTIVES,
            default=["cost"],
            format_func=lambda objective: OBJECTIVE_LABELS[objective],
        )
        repeats = st.number_input("Measured repetitions", min_value=1, max_value=20, value=1)
        population_size = st.number_input("NSGA-II population", min_value=2, max_value=500, value=10)
        generations = st.number_input("NSGA-II generations", min_value=1, max_value=500, value=3)
        iterations = st.number_input("Simulated Annealing iterations", min_value=1, max_value=5000, value=30)

    if not selected_datasets:
        st.warning("Select at least one dataset.")
        return
    cities = city_options(selected_datasets[0])
    source = st.selectbox("Source city", cities, index=0)
    destination_options = [city for city in cities if city != source]
    destination = st.selectbox("Destination city", destination_options, index=0)

    run_clicked = st.button("Run Experiment", type="primary", disabled=not selected_objectives)
    if run_clicked:
        manager = ExperimentManager(DATASETS_ROOT, RESULTS_ROOT)
        try:
            with st.status("Running selected experiments...", expanded=True) as status:
                st.write(
                    f"Scheduling {len(selected_datasets) * len(selected_objectives)} "
                    "dataset-objective combinations."
                )
                result = manager.run(
                    selected_datasets,
                    selected_objectives,
                    source,
                    destination,
                    repeats=int(repeats),
                    algorithm_kwargs=_algorithm_kwargs(
                        int(population_size), int(generations), int(iterations)
                    ),
                )
                status.update(label="Experiment completed", state="complete")
            st.session_state["latest_result"] = result
            st.success(
                f"Completed {result.algorithm_execution_count} measured algorithm executions."
            )
        except ValueError as exc:
            st.error(str(exc))

    result = st.session_state.get("latest_result")
    if isinstance(result, ExperimentResult):
        st.subheader(f"Experiment {result.experiment_id}")
        st.dataframe(_format_comparison(result.comparison), use_container_width=True, hide_index=True)
        _show_routes(result)
        _show_charts(result)
        st.download_button(
            "Download CSV results",
            result.comparison.to_csv(index=False),
            file_name=f"{result.experiment_id}.csv",
            mime="text/csv",
        )
    _show_history()


if __name__ == "__main__":
    main()
