"""Interactive Streamlit dashboard for route optimization experiments."""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

from app.comparison import (
    convergence_rows,
    memory_axis_type,
    objective_statistics,
    optimality_gap_statistics,
    resource_statistics,
    scalability_statistics,
)
from backend.experiment_manager import (
    ExperimentManager,
    ExperimentResult,
    experiment_name,
)
from backend.graph import load_graph
from app.components.route_map import (
    RouteMapError,
    create_route_map,
    prepare_route_map_data,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATASETS_ROOT = PROJECT_ROOT / "datasets" / "processed"
RESULTS_ROOT = PROJECT_ROOT / "experiments" / "results"
OBJECTIVES = ("cost", "time", "emissions")
OBJECTIVE_LABELS = {
    "cost": "Cost",
    "time": "Travel time",
    "emissions": "Carbon emissions",
}
ALGORITHM_LABELS = {
    "dijkstra": "Dijkstra",
    "astar": "A*",
    "nsga2": "NSGA-II",
    "simulated_annealing": "Simulated Annealing",
}
PARAMETER_HELP = {
    "repeats": """
**What it controls**
Number of independent executions of each algorithm for the same experiment configuration.

**Why it matters**
Repeated executions help assess consistency and calculate mean, median and standard deviation for execution time and memory consumption.

**Recommended values**
- **1 repetition:** Quick functional testing; fastest option, but does not establish reliable benchmark statistics.
- **3–5 repetitions:** Preliminary comparisons during development.
- **10 repetitions:** Recommended starting point for experimental benchmarking.
- **20–30 repetitions:** More reliable statistical comparisons when computational resources permit.

**When to increase it**
Increase repetitions when measuring stochastic algorithm performance or when execution-time variability is high.

**Computational trade-off**
More repetitions increase total experiment execution time.
""",
    "population": """
**What it controls**
Number of candidate solutions maintained in each NSGA-II population.

**Why it matters**
Population size influences the diversity of candidate solutions and how extensively the algorithm explores the search space.

**Recommended values**
- **10–20:** Quick functional testing and small experiments.
- **30–50:** Preliminary optimization experiments.
- **50–100:** Recommended starting range for more serious benchmarking.
- **100–200:** Larger search populations when computational resources permit.

**When to increase it**
Increase population size when the search space is large or the algorithm is struggling to discover diverse and high-quality solutions.

**Computational trade-off**
Larger populations generally increase evaluation cost and memory consumption.
""",
    "generations": """
**What it controls**
Number of evolutionary cycles performed by NSGA-II.

**Why it matters**
Each generation provides opportunities for selection, crossover and mutation to improve the candidate population.

**Recommended values**
- **3–5:** Quick functional testing.
- **20–50:** Preliminary optimization experiments.
- **100:** Recommended starting point for serious benchmarking.
- **200–500:** More extensive optimization experiments when computational resources permit.

**When to increase it**
Increase generations when solution quality is still improving and the algorithm has not sufficiently converged.

**Computational trade-off**
More generations increase execution time. More generations do not guarantee a better result in every run.
""",
    "iterations": """
**What it controls**
Number of neighbourhood-search iterations performed by Simulated Annealing.

**Why it matters**
Each iteration explores a neighbouring candidate solution and decides whether to accept it based on the objective and current temperature.

**Recommended values**
- **30–50:** Quick functional testing.
- **100–300:** Preliminary optimization experiments.
- **500–1,000:** Recommended starting range for more serious benchmarking.
- **2,000–5,000:** Extensive search when computational resources permit.

**When to increase it**
Increase iterations when the algorithm needs more opportunities to explore the search space or when the solution is still improving.

**Computational trade-off**
More iterations increase execution time and do not guarantee a globally optimal solution.
""",
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


def city_options(dataset: str) -> dict[str, str]:
    """Load city IDs and names for the currently selected preview dataset."""
    graph = load_graph(DATASETS_ROOT / dataset)
    return {
        str(node): str(graph.nodes[node]["city_name"])
        for node in sorted(graph.nodes)
    }


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


def _show_chart_heading(title: str, what: str, why: str) -> None:
    title_column, info_column = st.columns([0.94, 0.06])
    with title_column:
        st.markdown(f"#### {title}")
    with info_column:
        with st.popover("ⓘ"):
            st.markdown("**What does this graph show?**")
            st.write(what)
            st.markdown("**Why does it matter?**")
            st.write(why)


def _show_charts(result: ExperimentResult) -> None:
    table = result.comparison
    st.subheader("Comparisons")
    objective_data = objective_statistics(table)
    resource_data = resource_statistics(table)
    gap_data = optimality_gap_statistics(table)
    if objective_data.empty:
        st.info("No valid measured objective values are available for comparison.")
        return
    objective_data["objective_label"] = objective_data["objective"].map(OBJECTIVE_LABELS)
    _show_chart_heading(
        "Mean Objective Value",
        "This graph compares the average objective values achieved by different "
        "optimization algorithms across the selected experiment.",
        "Since the objectives are minimization problems, a lower objective value "
        "indicates a better solution. It helps compare solution quality for "
        "transportation cost, travel time or carbon emissions.",
    )
    st.plotly_chart(
        px.bar(
            objective_data,
            x="algorithm",
            y="mean_objective_value",
            color="algorithm",
            error_y="objective_stddev",
            facet_col="objective_label",
            facet_row="dataset",
            custom_data=["algorithm", "dataset", "objective", "mean_objective_value",
                         "objective_stddev", "valid_measured_runs"],
            title="Mean objective value",
        ).update_traces(
            hovertemplate=(
                "Algorithm: %{customdata[0]}<br>Dataset: %{customdata[1]}<br>"
                "Objective: %{customdata[2]}<br>Mean: %{customdata[3]:.6g}<br>"
                "Std. dev.: %{customdata[4]:.6g}<br>"
                "Valid measured runs: %{customdata[5]}<extra></extra>"
            )
        ),
        use_container_width=True,
    )
    st.caption("Error bars show ±1 standard deviation from valid measured repetitions. "
               "A single measured run has no reliable variability estimate.")
    _show_chart_heading(
        "Mean Execution Time versus Peak Memory",
        "This graph compares the computational resources required by different "
        "optimization algorithms. It displays execution time against peak memory "
        "consumption.",
        "It helps identify which algorithms execute faster, use less memory and "
        "have different resource requirements as transportation networks grow.",
    )
    st.plotly_chart(
        px.scatter(
            resource_data.assign(objective_label=lambda frame: frame["objective"].map(OBJECTIVE_LABELS)),
            x="mean_execution_time_ms",
            y="mean_peak_memory_bytes",
            color="algorithm", symbol="objective_label",
            error_x="execution_time_stddev", error_y="peak_memory_stddev",
            custom_data=["algorithm", "dataset", "objective", "mean_execution_time_ms",
                         "execution_time_stddev", "mean_peak_memory_bytes",
                         "peak_memory_stddev", "measured_runs"],
            title="Mean execution time versus peak memory",
        ).update_layout(yaxis_title="Python-traced peak memory (bytes)",
                        yaxis_type=memory_axis_type(table)).update_traces(
            hovertemplate=(
                "Algorithm: %{customdata[0]}<br>Dataset: %{customdata[1]}<br>"
                "Objective: %{customdata[2]}<br>Mean time: %{customdata[3]:.6g} ms"
                "<br>Time std. dev.: %{customdata[4]:.6g} ms<br>"
                "Mean memory: %{customdata[5]:.6g} bytes<br>"
                "Memory std. dev.: %{customdata[6]:.6g} bytes<br>"
                "Measured runs: %{customdata[7]}<extra></extra>"
            )
        ),
        use_container_width=True,
    )
    if memory_axis_type(table) == "log":
        st.caption("Memory is displayed on a logarithmic scale to make differences between "
                   "algorithms with substantially different memory requirements easier to compare.")
    else:
        st.caption("Memory uses a linear scale because zero or non-positive measured values "
                   "are present; values are Python-traced peak memory, not total system RAM.")
    if not gap_data.empty:
        gap_data["objective_label"] = gap_data["objective"].map(OBJECTIVE_LABELS)
        _show_chart_heading(
            "Optimality Gap Comparison",
            "It compares each algorithm's solution with the project's reference shortest-path optimum.",
            "Lower gaps indicate closer solutions; zero means the reference optimum was achieved.",
        )
        st.plotly_chart(
            px.bar(
                gap_data, x="algorithm", y="mean_optimality_gap", color="algorithm",
                error_y="optimality_gap_stddev", facet_col="objective_label",
                facet_row="dataset", custom_data=["algorithm", "dataset", "objective",
                                                   "mean_objective_value", "mean_optimality_gap",
                                                   "measured_runs"],
                title="Optimality Gap Comparison",
            ).add_hline(y=0, line_dash="dash", line_color="white").update_layout(
                yaxis_title="Optimality gap (%)"
            ).update_traces(
                hovertemplate=(
                    "Algorithm: %{customdata[0]}<br>Dataset: %{customdata[1]}<br>"
                    "Objective: %{customdata[2]}<br>Obtained mean: %{customdata[3]:.6g}"
                    "<br>Gap: %{customdata[4]:.6g}%<br>Measured runs: %{customdata[5]}"
                    "<extra></extra>"
                )
            ),
            use_container_width=True,
        )
        st.caption("Comparison against the project's reference shortest-path optimum, "
                   "not an absolute real-world transportation optimum.")
    convergence = convergence_rows(table)
    if not convergence.empty:
        convergence["objective_label"] = convergence["objective"].map(OBJECTIVE_LABELS)
        _show_chart_heading(
            "Best-so-far Convergence",
            "This graph illustrates how the best objective value discovered by an "
            "optimization algorithm changes during its search process.",
            "It shows how quickly an algorithm improves, whether progress slows "
            "down and whether further improvement becomes limited. This is "
            "particularly useful for NSGA-II and Simulated Annealing.",
        )
        st.plotly_chart(
            px.line(
                convergence,
                x="step",
                y="best_so_far",
                color="algorithm",
                facet_row="objective_label",
                facet_col="dataset",
                line_dash="run",
                markers=True,
                custom_data=["algorithm", "dataset", "objective", "run", "step",
                             "step_type", "best_so_far"],
                title="Best-so-far convergence",
            ).update_layout(xaxis_title="Generation / Iteration").update_traces(
                hovertemplate=(
                    "Algorithm: %{customdata[0]}<br>Dataset: %{customdata[1]}<br>"
                    "Objective: %{customdata[2]}<br>Run: %{customdata[3]}<br>"
                    "%{customdata[5]}: %{customdata[4]}<br>"
                    "Best-so-far: %{customdata[6]:.6g}<extra></extra>"
                )
            ),
            use_container_width=True,
        )
        st.caption("Dijkstra and A* are single-pass searches and therefore have no convergence series.")
    _show_scalability(result)


def _saved_comparable_tables(result: ExperimentResult) -> list[pd.DataFrame]:
    """Load current and historical records with the same endpoint policy."""
    tables = [result.comparison]
    if not RESULTS_ROOT.is_dir():
        return tables
    for path in RESULTS_ROOT.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        configuration = payload.get("configuration")
        records = payload.get("records")
        if not isinstance(configuration, dict) or not isinstance(records, list):
            continue
        if (
            configuration.get("source") == result.config.source
            and configuration.get("destination") == result.config.destination
            and configuration.get("repeats") == result.config.repeats
        ):
            historical = pd.DataFrame(records)
            if not historical.empty:
                tables.append(historical)
    return tables


def _show_scalability(result: ExperimentResult) -> None:
    _show_chart_heading(
        "Algorithm Performance Across Dataset Sizes",
        "It displays how a selected performance metric changes as the network grows from 10 to 60 cities.",
        "It helps understand solution quality and computational requirements on larger networks. "
        "Comparisons are meaningful only when experiment configurations are sufficiently consistent.",
    )
    metric = st.selectbox(
        "Scalability metric",
        ("objective", "execution_time", "memory", "optimality_gap"),
        format_func={
            "objective": "Mean objective value",
            "execution_time": "Mean execution time",
            "memory": "Mean peak memory",
            "optimality_gap": "Mean optimality gap",
        }.__getitem__,
        key="scalability_metric",
    )
    objective = st.selectbox(
        "Scalability objective",
        OBJECTIVES,
        format_func=OBJECTIVE_LABELS.__getitem__,
        key="scalability_objective",
    )
    data = scalability_statistics(
        _saved_comparable_tables(result), objective, metric
    )
    if data.empty:
        st.info("No comparable saved benchmark records are available for this objective. "
                "Run the same source/destination configuration across multiple dataset sizes.")
        return
    fig = px.line(
        data,
        x="city_count",
        y="value",
        color="algorithm",
        markers=True,
        custom_data=["algorithm", "dataset", "measured_runs", "value"],
        labels={"city_count": "Number of cities", "value": metric},
        title="Algorithm Performance Across Dataset Sizes",
    ).update_traces(
        hovertemplate=(
            "Algorithm: %{customdata[0]}<br>Dataset: %{customdata[1]}<br>"
            "Value: %{customdata[3]:.6g}<br>Measured runs: %{customdata[2]}"
            "<extra></extra>"
        )
    )
    if metric == "execution_time":
        fig.update_yaxes(title="Mean execution time (ms)")
    elif metric == "memory":
        fig.update_yaxes(title="Mean Python-traced peak memory (bytes)")
    elif metric == "optimality_gap":
        fig.update_yaxes(title="Mean optimality gap (%)")
    else:
        fig.update_yaxes(title=f"Mean {OBJECTIVE_LABELS[objective].lower()} "
                              "(native dataset units)")
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Missing datasets remain missing; six dataset sizes alone do not establish "
               "scalability.")


def _show_route_visualization(
    result: ExperimentResult,
    source: str,
    destination: str,
    route_context: tuple[object, ...],
) -> None:
    st.subheader("Route Visualization")
    available_algorithms = tuple(
        algorithm
        for algorithm in ALGORITHM_LABELS
        if any(
            record.get("algorithm") == algorithm and record.get("valid")
            for record in result.records
        )
    )
    if not available_algorithms:
        st.info("No valid algorithm routes are available for this experiment.")
        return
    selected_algorithm = st.selectbox(
        "Algorithm",
        available_algorithms,
        format_func=ALGORITHM_LABELS.__getitem__,
        key="route_map_algorithm_selector",
    )
    records = [
        record
        for record in result.records
        if record.get("algorithm") == selected_algorithm
        and record.get("valid")
        and record.get("source") == source
        and record.get("destination") == destination
    ]
    if not records:
        st.warning(
            f"No valid {ALGORITHM_LABELS[selected_algorithm]} route is available "
            "for the selected source and destination."
        )
        return
    record = records[0]

    dataset = record.get("dataset")
    if not isinstance(dataset, str):
        st.error("The selected route does not identify a dataset.")
        return
    try:
        graph = load_graph(DATASETS_ROOT / dataset)
        route_data = prepare_route_map_data(
            graph,
            record["nodes"],
            record["edge_ids"],
            record["modes"],
        )
        route_map = create_route_map(route_data)
    except (KeyError, TypeError, RouteMapError, ValueError) as exc:
        st.error(f"Unable to display the selected route: {exc}")
        return

    metrics = {
        "distance": sum(float(segment.attributes["distance_km"]) for segment in route_data.segments),
        "cost": sum(float(segment.attributes["cost"]) for segment in route_data.segments),
        "time": sum(float(segment.attributes["travel_time_hours"]) for segment in route_data.segments),
        "emissions": sum(
            float(segment.attributes["carbon_emissions_kg"])
            for segment in route_data.segments
        ),
    }
    objective = str(record.get("objective"))
    st.markdown("#### Optimized Route Summary")
    st.caption(
        f"{route_data.city_names[route_data.nodes[0]]} → "
        f"{route_data.city_names[route_data.nodes[-1]]} | "
        f"{ALGORITHM_LABELS[selected_algorithm]} | {dataset} "
        f"({len(graph.nodes)} cities) | Optimized objective: "
        f"{OBJECTIVE_LABELS.get(objective, objective)}"
    )
    metric_columns = st.columns(4)
    for column, label, value in (
        (metric_columns[0], "Total cost (dataset units)", metrics["cost"]),
        (metric_columns[1], "Travel time (hours)", metrics["time"]),
        (metric_columns[2], "Emissions (kg)", metrics["emissions"]),
        (metric_columns[3], "Distance (km)", metrics["distance"]),
    ):
        column.metric(label, f"{value:,.2f}")

    st.markdown("#### Interactive India Map")
    st.caption(
        f"Showing {ALGORITHM_LABELS[selected_algorithm]} for dataset {dataset} "
        f"and {OBJECTIVE_LABELS.get(objective, objective)}. Click a route segment "
        "to inspect its exact connection details."
    )
    st_folium(route_map, height=600, use_container_width=True, returned_objects=[])
    st.markdown("#### Route Breakdown")
    for index, segment in enumerate(route_data.segments, start=1):
        source_name = route_data.city_names[segment.source]
        destination_name = route_data.city_names[segment.destination]
        with st.container(border=True):
            st.markdown(
                f"**{index}. {source_name} → {destination_name}**  \n"
                f"`{segment.mode.title()}` · Connection `{segment.edge_id}`"
            )
            details = st.columns(4)
            details[0].write(f"Distance: {float(segment.attributes['distance_km']):,.2f} km")
            details[1].write(f"Cost: {float(segment.attributes['cost']):,.2f}")
            details[2].write(
                f"Time: {float(segment.attributes['travel_time_hours']):,.2f} hours"
            )
            details[3].write(
                f"Emissions: {float(segment.attributes['carbon_emissions_kg']):,.2f} kg"
            )
    st.markdown("#### Route Statistics")
    mode_counts: dict[str, int] = {}
    for segment in route_data.segments:
        mode = segment.mode.lower()
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
    stat_columns = st.columns(4)
    stat_columns[0].metric("Connections", len(route_data.segments))
    stat_columns[1].metric("Unique cities", len(set(route_data.nodes)))
    stat_columns[2].metric("Transport modes", len(mode_counts))
    stat_columns[3].metric("Total distance", f"{metrics['distance']:,.2f} km")
    st.write("Connections by transport mode")
    st.dataframe(
        pd.DataFrame(
            [
                {"Mode": mode.title(), "Connections": mode_counts.get(mode, 0)}
                for mode in ("road", "rail", "air", "water", "waterway", "waterways")
                if mode in mode_counts
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def _show_history() -> None:
    st.subheader("Experiment history")
    history = sorted(RESULTS_ROOT.glob("*.json"), reverse=True) if RESULTS_ROOT.is_dir() else []
    if not history:
        st.info("No saved experiments yet.")
        return
    selected = st.selectbox(
        "Saved experiment",
        history,
        format_func=_history_label,
    )
    try:
        payload = json.loads(selected.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        st.error(f"Unable to read saved experiment: {exc}")
        return
    st.json(
        {
            "experiment_id": payload.get("experiment_id"),
            "experiment_name": payload.get("experiment_name")
            or _fallback_history_label(payload),
            "created_at": payload.get("created_at"),
            "configuration": payload.get("configuration"),
            "combination_count": payload.get("combination_count"),
            "algorithm_execution_count": payload.get("algorithm_execution_count"),
        }
    )


def _fallback_history_label(payload: dict[str, object]) -> str:
    configuration = payload.get("configuration")
    if not isinstance(configuration, dict):
        return str(payload.get("experiment_id", "Saved experiment"))
    datasets = configuration.get("datasets")
    source = configuration.get("source")
    destination = configuration.get("destination")
    if (
        not isinstance(datasets, list)
        or not datasets
        or not all(isinstance(dataset, str) for dataset in datasets)
        or not isinstance(source, str)
        or not isinstance(destination, str)
    ):
        return str(payload.get("experiment_id", "Saved experiment"))
    try:
        return experiment_name(DATASETS_ROOT, datasets, source, destination)
    except (OSError, KeyError, TypeError, ValueError):
        return str(payload.get("experiment_id", "Saved experiment"))


def _history_label(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return path.stem
    saved_name = payload.get("experiment_name")
    return saved_name if isinstance(saved_name, str) and saved_name else _fallback_history_label(payload)


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
        repeats = st.number_input(
            "Measured repetitions",
            min_value=1,
            max_value=20,
            value=1,
            help=PARAMETER_HELP["repeats"],
        )
        population_size = st.number_input(
            "NSGA-II population",
            min_value=2,
            max_value=500,
            value=10,
            help=PARAMETER_HELP["population"],
        )
        generations = st.number_input(
            "NSGA-II generations",
            min_value=1,
            max_value=500,
            value=3,
            help=PARAMETER_HELP["generations"],
        )
        iterations = st.number_input(
            "Simulated Annealing iterations",
            min_value=1,
            max_value=5000,
            value=30,
            help=PARAMETER_HELP["iterations"],
        )

    if not selected_datasets:
        st.warning("Select at least one dataset.")
        return
    city_labels = city_options(selected_datasets[0])
    cities = list(city_labels)
    source = st.selectbox(
        "Source city",
        cities,
        index=0,
        format_func=city_labels.__getitem__,
    )
    destination_options = [city for city in cities if city != source]
    destination = st.selectbox(
        "Destination city",
        destination_options,
        index=0,
        format_func=city_labels.__getitem__,
    )
    route_context = (
        tuple(selected_datasets),
        tuple(selected_objectives),
        source,
        destination,
    )
    if st.session_state.get("route_map_context") not in (None, route_context):
        st.session_state.pop("route_map_record", None)
        st.session_state.pop("route_map_context", None)
        st.session_state.pop("route_map_algorithm", None)
        st.session_state.pop("route_map_experiment_id", None)

    run_clicked = st.button("Run Experiment", type="primary", disabled=not selected_objectives)
    if run_clicked:
        st.session_state.pop("route_map_record", None)
        st.session_state.pop("route_map_context", None)
        st.session_state.pop("route_map_algorithm", None)
        st.session_state.pop("route_map_experiment_id", None)
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
        _show_route_visualization(result, source, destination, route_context)
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
