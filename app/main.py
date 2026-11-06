"""Interactive Streamlit dashboard for route optimization experiments."""

from __future__ import annotations

import json
from html import escape
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
from app.components.route_map import (
    RouteMapError,
    create_network_map,
    create_route_map,
    prepare_route_map_data,
)
from backend.experiment_manager import (
    ExperimentManager,
    ExperimentResult,
    experiment_name,
)
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
OBJECTIVE_UNITS = {"cost": "dataset units", "time": "hours", "emissions": "kg CO₂"}
ALGORITHM_LABELS = {
    "dijkstra": "Dijkstra",
    "astar": "A*",
    "nsga2": "NSGA-II",
    "simulated_annealing": "Simulated Annealing",
    "aco": "Ant Colony Optimization",
}
# One stable colour per algorithm so every chart reads the same way.
ALGORITHM_COLORS = {
    "dijkstra": "#1f3a5f",
    "astar": "#0f766e",
    "nsga2": "#c2882b",
    "simulated_annealing": "#a4343a",
    "aco": "#6b5b95",
}
MODE_COLORS = {
    "road": "#3b6ea5",
    "rail": "#b4443c",
    "air": "#7a5c9e",
    "water": "#3f8f6b",
    "waterway": "#3f8f6b",
    "waterways": "#3f8f6b",
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
    "aco_ants": """
**What it controls**
Number of ants constructing candidate routes during each Ant Colony Optimization iteration.

**Why it matters**
More ants provide more route samples for pheromone updates, but increase computation and memory use.

**Recommended values**
- **5–10:** Quick functional testing.
- **20–50:** Preliminary optimization experiments.
- **50–100:** More extensive search when resources permit.
""",
    "aco_iterations": """
**What it controls**
Number of pheromone-update iterations performed by Ant Colony Optimization.

**Why it matters**
Each iteration constructs ant routes, evaporates pheromone and reinforces promising edges.

**Recommended values**
- **10–30:** Quick functional testing.
- **50–100:** Preliminary optimization experiments.
- **100–500:** More extensive search when resources permit.
""",
}


# --------------------------------------------------------------------------- #
# Styling helpers
# --------------------------------------------------------------------------- #
DASHBOARD_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root {
  --ink: #111827; --body: #374151; --muted: #6b7280; --line: #e5e7eb; --line-soft: #f0f1f3;
  --card: #ffffff; --bg: #f7f8fa; --accent: #1f3a5f;
}
html, body, [class*="css"], .stApp, button, input, textarea, select {
  font-family: 'Inter', -apple-system, 'Segoe UI', sans-serif !important;
  -webkit-font-smoothing: antialiased;
}
.stApp { background: var(--bg); color: var(--body); }
.block-container { padding: 2rem 2.5rem 4rem; max-width: 1440px; }
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }
h1, h2, h3, h4, h5 { color: var(--ink); letter-spacing: -0.01em; font-weight: 600; }

.page-head { display: flex; justify-content: space-between; align-items: flex-end;
  border-bottom: 1px solid var(--line); padding-bottom: 18px; margin-bottom: 6px; gap: 24px; }
.eyebrow { font-size: .72rem; font-weight: 600; letter-spacing: .12em; text-transform: uppercase;
  color: var(--muted); margin-bottom: 6px; }
.page-head h1 { font-size: 1.7rem; font-weight: 650; margin: 0; padding: 0; line-height: 1.2; color: var(--ink); }
.page-head p { margin: 6px 0 0; color: var(--muted); font-size: .92rem; max-width: 720px; }
.meta { text-align: right; font-size: .78rem; color: var(--muted); line-height: 1.7; white-space: nowrap; }
.meta b { color: var(--ink); font-weight: 600; }

.strip { display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; background: var(--card);
  border: 1px solid var(--line); border-radius: 10px; margin: 14px 0 6px; overflow: hidden; }
.stat { padding: 16px 20px; border-right: 1px solid var(--line); }
.stat:last-child { border-right: none; }
.stat .label { color: var(--muted); font-size: .72rem; font-weight: 500; letter-spacing: .04em;
  text-transform: uppercase; }
.stat .value { color: var(--ink); font-size: 1.5rem; font-weight: 600; margin-top: 4px;
  font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }
.stat .sub { color: var(--muted); font-size: .76rem; margin-top: 2px; }

.section-title { font-size: .95rem; font-weight: 600; color: var(--ink); margin: 30px 0 2px; }
.section-sub { color: var(--muted); font-size: .84rem; margin-bottom: 12px; }

.algo-card { background: var(--card); border: 1px solid var(--line); border-radius: 10px;
  padding: 18px 20px; height: 100%; }
.algo-card h4 { margin: 0 0 2px; font-size: .98rem; display: flex; align-items: center; gap: 8px; }
.dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.algo-card .tag { display: block; font-size: .74rem; color: var(--muted); margin-bottom: 10px; }
.algo-card li { font-size: .84rem; color: var(--body); margin-bottom: 4px; line-height: 1.5; }
.algo-card ul { padding-left: 1.05rem; margin: 0; }
.note { border: 1px solid var(--line); border-left: 3px solid var(--accent); background: var(--card);
  padding: 12px 16px; font-size: .86rem; color: var(--body); margin: 14px 0; border-radius: 0 8px 8px 0; }
.note b { color: var(--ink); }

div[data-baseweb="tab-list"] { gap: 28px; border-bottom: 1px solid var(--line); }
button[data-baseweb="tab"] { padding: 10px 0; background: transparent; font-size: .9rem;
  font-weight: 500; color: var(--muted); }
button[data-baseweb="tab"][aria-selected="true"] { color: var(--ink); font-weight: 600; }
div[data-baseweb="tab-highlight"] { background: var(--ink); height: 2px; }
div[data-baseweb="tab-border"] { display: none; }


/* Primary navigation (radio rendered as an underline tab bar) */
div[data-testid="stRadio"] { width: 100%; border-bottom: 1px solid var(--line); }
div[data-testid="stRadio"] [role="radiogroup"] { gap: 28px; }
div[data-testid="stRadio"] [role="radiogroup"] > label { padding: 10px 0 11px; margin: 0; cursor: pointer;
  border-bottom: 2px solid transparent; margin-bottom: -1px; }
div[data-testid="stRadio"] [role="radiogroup"] > label > div:first-child { display: none; }
div[data-testid="stRadio"] [role="radiogroup"] > label p { font-size: .9rem; font-weight: 500; color: var(--muted); }
div[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) { border-bottom-color: var(--ink); }
div[data-testid="stRadio"] [role="radiogroup"] > label:has(input:checked) p { color: var(--ink); font-weight: 600; }
div[data-testid="stRadio"] [role="radiogroup"] > label:hover p { color: var(--ink); }

section[data-testid="stSidebar"] { background: var(--card); border-right: 1px solid var(--line); }
.side-title { font-size: .72rem; font-weight: 600; letter-spacing: .12em; text-transform: uppercase;
  color: var(--muted); margin-bottom: 14px; }
[data-testid="stWidgetLabel"] p { font-size: .8rem !important; font-weight: 500 !important; color: var(--body) !important; }
div[data-baseweb="select"] > div, div[data-baseweb="input"] > div { border-radius: 8px; border-color: var(--line); background: #fff; }
.stButton > button[kind="primary"] {
  border-radius: 8px; font-weight: 600; background: var(--ink); border: 1px solid var(--ink); color: #fff; }
.stButton > button[kind="primary"]:hover { background: #000; border-color: #000; color: #fff; }
.stDownloadButton > button { border-radius: 8px; background: #fff; color: var(--ink);
  border: 1px solid var(--line); font-weight: 500; }
.stDownloadButton > button:hover { border-color: var(--ink); color: var(--ink); }

div[data-testid="stDataFrame"] { border: 1px solid var(--line); border-radius: 10px; overflow: hidden; background: #fff; }
div[data-testid="stPlotlyChart"] { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 8px 6px; }
iframe[title="streamlit_folium.st_folium"] { border-radius: 10px; border: 1px solid var(--line); }
div[data-testid="stExpander"] { border: 1px solid var(--line); border-radius: 10px; background: #fff; }
</style>
"""


def _kpi(label: str, value: object, sub: str = "", tone: str = "") -> str:
    sub_html = f'<div class="sub">{escape(sub)}</div>' if sub else ""
    return (
        f'<div class="stat"><div class="label">{escape(label)}</div>'
        f'<div class="value">{escape(str(value))}</div>{sub_html}</div>'
    )


def _kpi_row(items: list[tuple[str, object, str, str]]) -> None:
    cells = "".join(_kpi(*item) for item in items)
    st.markdown(f'<div class="strip">{cells}</div>', unsafe_allow_html=True)


def _section(title: str, subtitle: str = "") -> None:
    st.markdown(f'<div class="section-title">{escape(title)}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="section-sub">{escape(subtitle)}</div>', unsafe_allow_html=True)


def _style_figure(fig, height: int = 420):
    """Apply one consistent, clean look to every Plotly chart."""
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=10, r=10, t=46, b=10),
        font=dict(family="Inter, Segoe UI, sans-serif", size=12, color="#374151"),
        title=dict(font=dict(size=14, color="#111827"), x=0.01),
        legend=dict(orientation="h", yanchor="top", y=-0.28, xanchor="left", x=0, title=None),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(gridcolor="#f0f1f3", zerolinecolor="#e5e7eb", linecolor="#e5e7eb")
    fig.update_yaxes(gridcolor="#f0f1f3", zerolinecolor="#e5e7eb", linecolor="#e5e7eb")
    fig.for_each_annotation(lambda note: note.update(text=note.text.split("=")[-1]))
    return fig


def _with_labels(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    if "algorithm" in frame:
        frame["algorithm_label"] = frame["algorithm"].map(ALGORITHM_LABELS).fillna(frame["algorithm"])
    if "objective" in frame:
        frame["objective_label"] = frame["objective"].map(OBJECTIVE_LABELS).fillna(frame["objective"])
    return frame


LABEL_COLORS = {ALGORITHM_LABELS[key]: color for key, color in ALGORITHM_COLORS.items()}
ALGORITHM_ORDER = list(ALGORITHM_LABELS.values())


def _dataset_size(name: str) -> int | None:
    digits = "".join(ch for ch in name if ch.isdigit())
    return int(digits) if digits else None


# --------------------------------------------------------------------------- #
# Data helpers
# --------------------------------------------------------------------------- #
def available_datasets() -> list[str]:
    """Return processed datasets that contain the required graph files."""
    if not DATASETS_ROOT.is_dir():
        return []
    return sorted(
        (
            directory.name
            for directory in DATASETS_ROOT.iterdir()
            if directory.is_dir()
            and (directory / "cities.csv").is_file()
            and (directory / "connections.csv").is_file()
        ),
        key=lambda name: (_dataset_size(name) or 0, name),
    )


@st.cache_resource(show_spinner=False)
def _cached_graph(dataset: str):
    return load_graph(DATASETS_ROOT / dataset)


def city_options(dataset: str) -> dict[str, str]:
    """Load city IDs and names for the currently selected preview dataset."""
    graph = _cached_graph(dataset)
    return {
        str(node): str(graph.nodes[node]["city_name"])
        for node in sorted(graph.nodes)
    }


def _algorithm_kwargs(
    population_size: int,
    generations: int,
    iterations: int,
    aco_ants: int,
    aco_iterations: int,
) -> dict[str, dict[str, int]]:
    return {
        "nsga2": {
            "population_size": population_size,
            "generations": generations,
        },
        "simulated_annealing": {"iterations": iterations},
        "aco": {"ants": aco_ants, "iterations": aco_iterations},
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
    if "algorithm" in formatted:
        formatted["algorithm"] = formatted["algorithm"].map(ALGORITHM_LABELS).fillna(formatted["algorithm"])
    return formatted


@st.cache_data(show_spinner=False)
def _load_saved_records(signature: tuple[tuple[str, float], ...]) -> pd.DataFrame:
    """Concatenate every saved experiment's records (cache keyed by file mtimes)."""
    frames = []
    for name, _mtime in signature:
        try:
            payload = json.loads((RESULTS_ROOT / name).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        records = payload.get("records")
        if isinstance(records, list) and records:
            frame = pd.DataFrame(records)
            frame["experiment_id"] = payload.get("experiment_id", name)
            frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def saved_records() -> pd.DataFrame:
    if not RESULTS_ROOT.is_dir():
        return pd.DataFrame()
    signature = tuple(
        (path.name, path.stat().st_mtime) for path in sorted(RESULTS_ROOT.glob("*.json"))
    )
    return _load_saved_records(signature)


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


def _leaderboard(table: pd.DataFrame) -> pd.DataFrame:
    """Per objective/algorithm summary of valid measured rows."""
    rows = table.copy()
    rows["valid"] = rows["valid"].fillna(False).astype(bool)
    valid = rows.loc[rows["valid"]]
    if valid.empty:
        return pd.DataFrame()
    grouped = valid.groupby(["objective", "algorithm"], as_index=False).agg(
        runs=("run", "count"),
        mean_objective=("objective_value", "mean"),
        mean_gap=("optimality_gap", "mean"),
        mean_time=("execution_time_ms", "mean"),
        mean_memory=("peak_memory_bytes", "mean"),
    )
    grouped["objective"] = grouped["objective"].map(OBJECTIVE_LABELS)
    grouped["algorithm"] = grouped["algorithm"].map(ALGORITHM_LABELS)
    return grouped


# --------------------------------------------------------------------------- #
# Overview tab
# --------------------------------------------------------------------------- #
def _dataset_summary(dataset: str) -> dict[str, object]:
    graph = _cached_graph(dataset)
    modes: dict[str, int] = {}
    for _u, _v, data in graph.edges(data=True):
        mode = str(data.get("mode", "unknown")).lower()
        modes[mode] = modes.get(mode, 0) + 1
    return {"graph": graph, "cities": graph.number_of_nodes(),
            "connections": graph.number_of_edges(), "modes": modes}


def _show_network_overview(dataset: str) -> None:
    summary = _dataset_summary(dataset)
    _section(
        f"Transportation network · {dataset}",
        "Every city and connection in the selected dataset, drawn on India. "
        "Coordinates are curated reference data; connection attributes are simulated.",
    )
    map_col, mode_col = st.columns([2.1, 1])
    with map_col:
        st_folium(
            create_network_map(summary["graph"]),
            height=700,
            use_container_width=True,
            returned_objects=[],
            center=(21.5, 80.5),
            zoom=4.75,
            key=f"network_map_{dataset}",
        )
    with mode_col:
        modes = summary["modes"]
        mode_frame = pd.DataFrame(
            {"Mode": [m.title() for m in modes], "Connections": list(modes.values()),
             "key": list(modes)}
        )
        fig = px.pie(
            mode_frame, names="Mode", values="Connections", hole=0.62,
            color="key", color_discrete_map=MODE_COLORS,
            title="Connections by transport mode",
        )
        fig.update_traces(textinfo="percent+label", textposition="outside", showlegend=False)
        st.plotly_chart(_style_figure(fig, 330), use_container_width=True)
        st.markdown(
            '<div class="note"><b>Provenance.</b> City coordinates: '
            "<b>manually curated reference</b>. Cost, time and emissions: "
            "<b>simulated for development</b> — not live schedules or measurements.</div>",
            unsafe_allow_html=True,
        )


def _show_run_overview(result: ExperimentResult) -> None:
    comparison = result.comparison
    valid = comparison["valid"].fillna(False).astype(bool)
    board = _leaderboard(comparison)
    exact_matches = int((comparison.loc[valid, "optimality_gap"].fillna(1) == 0).sum()) if valid.any() else 0
    fastest = "—"
    lowest_gap = "—"
    if not board.empty:
        by_algo = board.groupby("algorithm").agg(t=("mean_time", "mean"), g=("mean_gap", "mean"))
        fastest = by_algo["t"].idxmin()
        lowest_gap = by_algo["g"].idxmin()
    _kpi_row([
        ("Algorithm executions", f"{result.algorithm_execution_count:,}",
         f"{result.combination_count} dataset × objective combos", ""),
        ("Valid routes", f"{valid.mean() * 100:.0f}%", f"{int(valid.sum())} of {len(comparison)} runs", "good"),
        ("Matched reference", f"{exact_matches}", "runs with 0% optimality gap", "cyan"),
        ("Fastest (mean)", fastest, "lowest mean execution time", "warn"),
        ("Closest to optimum", lowest_gap, "lowest mean optimality gap", "rose"),
    ])

    _section("Algorithm leaderboard",
             "Mean over valid measured repetitions. Gap is measured against the objective-specific "
             "Dijkstra reference route.")
    if board.empty:
        st.info("No valid measured runs to summarise.")
    else:
        st.dataframe(
            board.rename(columns={
                "objective": "Objective", "algorithm": "Algorithm", "runs": "Runs",
                "mean_objective": "Mean objective", "mean_gap": "Optimality gap (%)",
                "mean_time": "Exec. time (ms)", "mean_memory": "Peak memory (B)",
            }),
            use_container_width=True, hide_index=True,
            column_config={
                "Mean objective": st.column_config.NumberColumn(format="%.2f"),
                "Optimality gap (%)": st.column_config.ProgressColumn(
                    format="%.2f%%", min_value=0.0,
                    max_value=float(max(board["mean_gap"].max(), 1.0))),
                "Exec. time (ms)": st.column_config.NumberColumn(format="%.3f"),
                "Peak memory (B)": st.column_config.NumberColumn(format="%,.0f"),
            },
        )

    _section("Optimized routes", "City sequence and transport modes chosen by each algorithm.")
    route_rows = []
    for record in result.records:
        route_rows.append({
            "Objective": OBJECTIVE_LABELS[str(record["objective"])],
            "Algorithm": ALGORITHM_LABELS.get(str(record["algorithm"]), record["algorithm"]),
            "Run": record["run"],
            "Valid": bool(record.get("valid")),
            "Route": " → ".join(record["nodes"]),
            "Modes": " → ".join(record["modes"]),
        })
    st.dataframe(pd.DataFrame(route_rows), use_container_width=True, hide_index=True)
    with st.expander("Full per-run measurements"):
        st.dataframe(_format_comparison(comparison), use_container_width=True, hide_index=True)
    st.download_button(
        "Download CSV results",
        comparison.to_csv(index=False),
        file_name=f"{result.experiment_id}.csv",
        mime="text/csv",
    )


def _show_benchmark_evidence() -> None:
    """Aggregate every saved experiment so research evidence is visible without re-running."""
    records = saved_records()
    if records.empty:
        return
    valid = records.loc[records["valid"].fillna(False).astype(bool)].copy()
    valid["optimality_gap"] = pd.to_numeric(valid["optimality_gap"], errors="coerce")
    valid["execution_time_ms"] = pd.to_numeric(valid["execution_time_ms"], errors="coerce")
    valid = _with_labels(valid)
    valid["city_count"] = valid["dataset"].map(lambda name: _dataset_size(str(name)))
    experiments = records["experiment_id"].nunique()

    _section("Benchmark evidence from saved experiments",
             "Aggregated from every experiment stored in experiments/results — independent of the current run.")
    _kpi_row([
        ("Saved experiments", f"{experiments}", "JSON + CSV artefacts", ""),
        ("Measured executions", f"{len(records):,}", "all algorithms, all runs", "cyan"),
        ("Dataset sizes covered", f"{valid['city_count'].nunique()}",
         "of 6 generated networks", "good"),
        ("Exact-match rate", f"{(valid['optimality_gap'].fillna(1) == 0).mean() * 100:.0f}%",
         "valid runs equal to the reference optimum", "rose"),
    ])
    st.write("")
    left, right = st.columns(2)
    gap = valid.groupby(["algorithm_label", "objective_label"], as_index=False).agg(
        gap=("optimality_gap", "mean"))
    fig = px.bar(
        gap, x="objective_label", y="gap", color="algorithm_label", barmode="group",
        color_discrete_map=LABEL_COLORS, category_orders={"algorithm_label": ALGORITHM_ORDER},
        labels={"gap": "Mean optimality gap (%)", "objective_label": "", "algorithm_label": ""},
        title="Mean optimality gap by objective",
    )
    left.plotly_chart(_style_figure(fig, 380), use_container_width=True)
    timing = valid.groupby(["algorithm_label", "objective_label"], as_index=False).agg(
        time=("execution_time_ms", "mean"))
    fig = px.bar(
        timing, x="objective_label", y="time", color="algorithm_label", barmode="group",
        color_discrete_map=LABEL_COLORS, category_orders={"algorithm_label": ALGORITHM_ORDER},
        labels={"time": "Mean execution time (ms, log)", "objective_label": "", "algorithm_label": ""},
        title="Mean execution time by objective",
    ).update_yaxes(type="log")
    right.plotly_chart(_style_figure(fig, 380), use_container_width=True)

    scaling = valid.dropna(subset=["city_count"]).groupby(
        ["city_count", "algorithm_label"], as_index=False
    ).agg(time=("execution_time_ms", "mean"), gap=("optimality_gap", "mean"))
    if scaling["city_count"].nunique() > 1:
        left, right = st.columns(2)
        fig = px.line(
            scaling, x="city_count", y="time", color="algorithm_label", markers=True,
            color_discrete_map=LABEL_COLORS, category_orders={"algorithm_label": ALGORITHM_ORDER},
            labels={"city_count": "Number of cities", "time": "Mean execution time (ms)",
                    "algorithm_label": ""},
            title="Runtime versus network size",
        )
        left.plotly_chart(_style_figure(fig, 380), use_container_width=True)
        fig = px.line(
            scaling, x="city_count", y="gap", color="algorithm_label", markers=True,
            color_discrete_map=LABEL_COLORS, category_orders={"algorithm_label": ALGORITHM_ORDER},
            labels={"city_count": "Number of cities", "gap": "Mean optimality gap (%)",
                    "algorithm_label": ""},
            title="Solution quality versus network size",
        )
        right.plotly_chart(_style_figure(fig, 380), use_container_width=True)
    st.caption("Descriptive measurements for this implementation and these configurations; "
               "not a general claim about algorithm superiority or national-scale networks.")


# --------------------------------------------------------------------------- #
# Comparison tab
# --------------------------------------------------------------------------- #
def _show_chart_heading(title: str, what: str, why: str) -> None:
    title_column, info_column = st.columns([0.94, 0.06])
    with title_column:
        st.markdown(f"##### {title}")
    with info_column:
        with st.popover("ⓘ"):
            st.markdown("**What does this graph show?**")
            st.write(what)
            st.markdown("**Why does it matter?**")
            st.write(why)


def _show_charts(result: ExperimentResult) -> None:
    table = result.comparison
    objective_data = objective_statistics(table)
    resource_data = resource_statistics(table)
    gap_data = optimality_gap_statistics(table)
    if objective_data.empty:
        st.info("No valid measured objective values are available for comparison.")
        return
    quality_tab, resource_tab, convergence_tab, scaling_tab = st.tabs(
        ["Solution quality", "Resources", "Convergence", "Scalability"]
    )

    with quality_tab:
        objective_data = _with_labels(objective_data)
        _show_chart_heading(
            "Mean Objective Value",
            "Average objective values achieved by each algorithm in the selected experiment.",
            "All objectives are minimised, so lower is better. It compares solution quality for "
            "cost, travel time or carbon emissions.",
        )
        fig = px.bar(
            objective_data, x="algorithm_label", y="mean_objective_value", color="algorithm_label",
            error_y="objective_stddev", facet_col="objective_label", facet_row="dataset",
            color_discrete_map=LABEL_COLORS, category_orders={"algorithm_label": ALGORITHM_ORDER},
            labels={"algorithm_label": "", "mean_objective_value": "Mean objective value"},
            custom_data=["algorithm", "dataset", "objective", "mean_objective_value",
                         "objective_stddev", "valid_measured_runs"],
        ).update_traces(
            hovertemplate=(
                "Algorithm: %{customdata[0]}<br>Dataset: %{customdata[1]}<br>"
                "Objective: %{customdata[2]}<br>Mean: %{customdata[3]:.6g}<br>"
                "Std. dev.: %{customdata[4]:.6g}<br>"
                "Valid measured runs: %{customdata[5]}<extra></extra>"
            )
        ).update_yaxes(matches=None).update_xaxes(showticklabels=False)
        st.plotly_chart(_style_figure(fig, 360 * max(1, objective_data["dataset"].nunique())),
                        use_container_width=True)
        st.caption("Error bars show ±1 standard deviation from valid measured repetitions. "
                   "A single measured run has no reliable variability estimate.")
        if not gap_data.empty:
            gap_data = _with_labels(gap_data)
            _show_chart_heading(
                "Optimality Gap Comparison",
                "Each algorithm's solution compared with the project's reference shortest-path optimum.",
                "Lower gaps indicate closer solutions; zero means the reference optimum was achieved.",
            )
            fig = px.bar(
                gap_data, x="algorithm_label", y="mean_optimality_gap", color="algorithm_label",
                error_y="optimality_gap_stddev", facet_col="objective_label", facet_row="dataset",
                color_discrete_map=LABEL_COLORS, category_orders={"algorithm_label": ALGORITHM_ORDER},
                labels={"algorithm_label": "", "mean_optimality_gap": "Optimality gap (%)"},
                custom_data=["algorithm", "dataset", "objective", "mean_objective_value",
                             "mean_optimality_gap", "measured_runs"],
            ).update_traces(
                hovertemplate=(
                    "Algorithm: %{customdata[0]}<br>Dataset: %{customdata[1]}<br>"
                    "Objective: %{customdata[2]}<br>Obtained mean: %{customdata[3]:.6g}"
                    "<br>Gap: %{customdata[4]:.6g}%<br>Measured runs: %{customdata[5]}"
                    "<extra></extra>"
                )
            ).update_xaxes(showticklabels=False)
            st.plotly_chart(_style_figure(fig, 360 * max(1, gap_data["dataset"].nunique())),
                            use_container_width=True)
            st.caption("Comparison against the project's reference shortest-path optimum, "
                       "not an absolute real-world transportation optimum.")

    with resource_tab:
        _show_chart_heading(
            "Mean Execution Time versus Peak Memory",
            "Computational resources required by each algorithm: execution time against peak memory.",
            "Shows which algorithms run faster, use less memory and have different resource "
            "requirements as networks grow.",
        )
        fig = px.scatter(
            _with_labels(resource_data), x="mean_execution_time_ms", y="mean_peak_memory_bytes",
            color="algorithm_label", symbol="objective_label",
            error_x="execution_time_stddev", error_y="peak_memory_stddev",
            color_discrete_map=LABEL_COLORS, category_orders={"algorithm_label": ALGORITHM_ORDER},
            labels={"mean_execution_time_ms": "Mean execution time (ms)",
                    "mean_peak_memory_bytes": "Python-traced peak memory (bytes)"},
            custom_data=["algorithm", "dataset", "objective", "mean_execution_time_ms",
                         "execution_time_stddev", "mean_peak_memory_bytes",
                         "peak_memory_stddev", "measured_runs"],
        ).update_layout(yaxis_type=memory_axis_type(table)).update_traces(
            marker=dict(size=13, line=dict(width=1, color="#ffffff")),
            hovertemplate=(
                "Algorithm: %{customdata[0]}<br>Dataset: %{customdata[1]}<br>"
                "Objective: %{customdata[2]}<br>Mean time: %{customdata[3]:.6g} ms"
                "<br>Time std. dev.: %{customdata[4]:.6g} ms<br>"
                "Mean memory: %{customdata[5]:.6g} bytes<br>"
                "Memory std. dev.: %{customdata[6]:.6g} bytes<br>"
                "Measured runs: %{customdata[7]}<extra></extra>"
            ),
        )
        st.plotly_chart(_style_figure(fig, 460), use_container_width=True)
        if memory_axis_type(table) == "log":
            st.caption("Memory is on a logarithmic scale so algorithms with very different "
                       "memory needs remain comparable.")
        else:
            st.caption("Memory uses a linear scale because zero or non-positive measured values "
                       "are present; values are Python-traced peak memory, not total system RAM.")

    with convergence_tab:
        convergence = convergence_rows(table)
        if convergence.empty:
            st.info("Convergence histories exist only for NSGA-II and Simulated Annealing.")
        else:
            convergence = _with_labels(convergence)
            _show_chart_heading(
                "Best-so-far Convergence",
                "How the best objective value found by an algorithm changes during its search.",
                "Shows how quickly an algorithm improves and whether progress stalls — most "
                "useful for NSGA-II and Simulated Annealing.",
            )
            fig = px.line(
                convergence, x="step", y="best_so_far", color="algorithm_label",
                facet_row="objective_label", facet_col="dataset", line_dash="run", markers=True,
                color_discrete_map=LABEL_COLORS,
                labels={"step": "Generation / Iteration", "best_so_far": "Best-so-far objective"},
                custom_data=["algorithm", "dataset", "objective", "run", "step",
                             "step_type", "best_so_far"],
            ).update_traces(
                hovertemplate=(
                    "Algorithm: %{customdata[0]}<br>Dataset: %{customdata[1]}<br>"
                    "Objective: %{customdata[2]}<br>Run: %{customdata[3]}<br>"
                    "%{customdata[5]}: %{customdata[4]}<br>"
                    "Best-so-far: %{customdata[6]:.6g}<extra></extra>"
                )
            ).update_yaxes(matches=None)
            st.plotly_chart(
                _style_figure(fig, 320 * max(1, convergence["objective"].nunique())),
                use_container_width=True,
            )
            st.caption("Dijkstra and A* are single-pass searches and therefore have no convergence series.")

    with scaling_tab:
        _show_scalability(result)


def _show_scalability(result: ExperimentResult) -> None:
    _show_chart_heading(
        "Algorithm Performance Across Dataset Sizes",
        "How a selected performance metric changes as the network grows from 10 to 60 cities.",
        "Helps understand solution quality and computational requirements on larger networks. "
        "Comparisons are meaningful only when experiment configurations are sufficiently consistent.",
    )
    metric_col, objective_col = st.columns(2)
    metric = metric_col.selectbox(
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
    objective = objective_col.selectbox(
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
    data = _with_labels(data)
    axis_title = {
        "execution_time": "Mean execution time (ms)",
        "memory": "Mean Python-traced peak memory (bytes)",
        "optimality_gap": "Mean optimality gap (%)",
    }.get(metric, f"Mean {OBJECTIVE_LABELS[objective].lower()} (native dataset units)")
    fig = px.line(
        data, x="city_count", y="value", color="algorithm_label", markers=True,
        color_discrete_map=LABEL_COLORS, category_orders={"algorithm_label": ALGORITHM_ORDER},
        custom_data=["algorithm", "dataset", "measured_runs", "value"],
        labels={"city_count": "Number of cities", "value": axis_title},
    ).update_traces(
        hovertemplate=(
            "Algorithm: %{customdata[0]}<br>Dataset: %{customdata[1]}<br>"
            "Value: %{customdata[3]:.6g}<br>Measured runs: %{customdata[2]}"
            "<extra></extra>"
        )
    )
    st.plotly_chart(_style_figure(fig, 440), use_container_width=True)
    st.caption("Missing datasets remain missing; six dataset sizes alone do not establish scalability.")


# --------------------------------------------------------------------------- #
# Route map tab
# --------------------------------------------------------------------------- #
def _show_route_visualization(
    result: ExperimentResult,
    source: str,
    destination: str,
    route_context: tuple[object, ...],
) -> None:
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
    select_col, objective_col, _ = st.columns([1, 1, 2])
    selected_algorithm = select_col.selectbox(
        "Algorithm",
        available_algorithms,
        format_func=ALGORITHM_LABELS.__getitem__,
        key="route_map_algorithm_selector",
    )
    objectives_for_algorithm = tuple(
        dict.fromkeys(
            str(record.get("objective"))
            for record in result.records
            if record.get("algorithm") == selected_algorithm and record.get("valid")
            and record.get("source") == source and record.get("destination") == destination
        )
    )
    if not objectives_for_algorithm:
        st.warning(
            f"No valid {ALGORITHM_LABELS[selected_algorithm]} route is available "
            "for the selected source and destination."
        )
        return
    selected_objective = objective_col.selectbox(
        "Objective",
        objectives_for_algorithm,
        format_func=lambda key: OBJECTIVE_LABELS.get(key, key),
        key="route_map_objective_selector",
    )
    records = [
        record
        for record in result.records
        if record.get("algorithm") == selected_algorithm
        and record.get("valid")
        and record.get("source") == source
        and record.get("destination") == destination
        and str(record.get("objective")) == selected_objective
    ]
    record = records[0]

    dataset = record.get("dataset")
    if not isinstance(dataset, str):
        st.error("The selected route does not identify a dataset.")
        return
    try:
        graph = _cached_graph(dataset)
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

    segments = route_data.segments
    metrics = {
        "distance": sum(float(s.attributes["distance_km"]) for s in segments),
        "cost": sum(float(s.attributes["cost"]) for s in segments),
        "time": sum(float(s.attributes["travel_time_hours"]) for s in segments),
        "emissions": sum(float(s.attributes["carbon_emissions_kg"]) for s in segments),
    }
    start_name = route_data.city_names[route_data.nodes[0]]
    end_name = route_data.city_names[route_data.nodes[-1]]
    st.markdown(
        f"### {escape(start_name)} → {escape(end_name)}"
        f"<span style='color:#64748b;font-size:.9rem;font-weight:400'> &nbsp;·&nbsp; "
        f"{ALGORITHM_LABELS[selected_algorithm]} &nbsp;·&nbsp; {dataset} ({len(graph.nodes)} cities) "
        f"&nbsp;·&nbsp; optimised for {OBJECTIVE_LABELS.get(selected_objective, selected_objective).lower()}</span>",
        unsafe_allow_html=True,
    )
    _kpi_row([
        ("Total cost", f"{metrics['cost']:,.0f}", "dataset units", ""),
        ("Travel time", f"{metrics['time']:,.1f} h", "door-to-door in dataset", "cyan"),
        ("Emissions", f"{metrics['emissions']:,.1f} kg", "CO₂ equivalent", "good"),
        ("Distance", f"{metrics['distance']:,.0f} km", f"{len(segments)} connection{'s' if len(segments) != 1 else ''}", "warn"),
    ])
    st.write("")
    map_col, detail_col = st.columns([2.2, 1])
    with map_col:
        st_folium(route_map, height=620, use_container_width=True, returned_objects=[],
                  key=f"route_map_{dataset}_{selected_algorithm}_{selected_objective}")
        st.caption("Map is restricted to India. Click a route segment to inspect its exact "
                   "connection details.")
    with detail_col:
        mode_distance: dict[str, float] = {}
        for segment in segments:
            mode = segment.mode.lower()
            mode_distance[mode] = mode_distance.get(mode, 0.0) + float(segment.attributes["distance_km"])
        mode_frame = pd.DataFrame({"Mode": [m.title() for m in mode_distance],
                                   "Distance (km)": list(mode_distance.values()),
                                   "key": list(mode_distance)})
        fig = px.pie(mode_frame, names="Mode", values="Distance (km)", hole=0.6,
                     color="key", color_discrete_map=MODE_COLORS,
                     title="Distance by transport mode")
        fig.update_traces(textinfo="percent+label", showlegend=False)
        st.plotly_chart(_style_figure(fig, 300), use_container_width=True)
        st.markdown("**Route stops**")
        st.markdown(
            " → ".join(route_data.city_names[node] for node in route_data.nodes)
        )
        st.caption(f"{len(set(route_data.nodes))} unique cities · {len(mode_distance)} transport mode(s)")

    _section("Segment breakdown")
    st.dataframe(
        pd.DataFrame([
            {
                "#": index,
                "From": route_data.city_names[segment.source],
                "To": route_data.city_names[segment.destination],
                "Mode": segment.mode.title(),
                "Connection": segment.edge_id,
                "Distance (km)": float(segment.attributes["distance_km"]),
                "Cost": float(segment.attributes["cost"]),
                "Time (h)": float(segment.attributes["travel_time_hours"]),
                "Emissions (kg)": float(segment.attributes["carbon_emissions_kg"]),
            }
            for index, segment in enumerate(segments, start=1)
        ]),
        use_container_width=True, hide_index=True,
        column_config={
            "Distance (km)": st.column_config.NumberColumn(format="%.1f"),
            "Cost": st.column_config.NumberColumn(format="%.2f"),
            "Time (h)": st.column_config.NumberColumn(format="%.2f"),
            "Emissions (kg)": st.column_config.NumberColumn(format="%.2f"),
        },
    )


# --------------------------------------------------------------------------- #
# Research tab
# --------------------------------------------------------------------------- #
ALGORITHM_CARDS = (
    ("Dijkstra", "Exact · deterministic", "dijkstra",
     ("Label-setting shortest path on the keyed multigraph.",
      "Optimal for non-negative additive edge weights — used as the <b>reference optimum</b>.",
      "≈ O((n + m) log n)")),
    ("A* Search", "Exact if heuristic admissible", "astar",
     ("Dijkstra guided by a geographic lower-bound heuristic f(v) = g(v) + h(v, r).",
      "Explores fewer nodes when the heuristic is informative.",
      "Admissibility of the coordinate heuristic is an open item (§13.4).")),
    ("NSGA-II", "Evolutionary · stochastic", "nsga2",
     ("pymoo NSGA-II configured with <b>one</b> objective over integer waypoint genes.",
      "Segments between waypoints are expanded with weighted Dijkstra.",
      "≈ O(N · G · C) — population × generations × decode cost")),
    ("Simulated Annealing", "Metaheuristic · stochastic", "simulated_annealing",
     ("Seeded waypoint route; neighbour = replace one waypoint.",
      "Accepts worse moves with probability exp(−Δ/T), geometric cooling.",
      "≈ O(K · C) — iterations × candidate cost")),
    ("Ant Colony Optimization", "Swarm metaheuristic · stochastic", "aco",
     ("Ants build cycle-free routes guided by pheromone trails and edge desirability.",
      "Pheromone evaporates each iteration and is reinforced on promising edges.",
      "≈ O(I · A · C) — iterations × ants × route construction")),
)

REFERENCE_RESULTS = pd.DataFrame(
    [
        ("Cost", "Dijkstra", 1449.07, 0.00, 0.132, "C01 → C02 → C06 → C09 → C10"),
        ("Cost", "A*", 1449.07, 0.00, 0.115, "C01 → C02 → C06 → C09 → C10"),
        ("Cost", "NSGA-II", 3373.34, 132.79, 30.704, "C01 → C02 → C04 → C06 → C09 → C10"),
        ("Cost", "Simulated Annealing", 1449.07, 0.00, 5.509, "C01 → C02 → C06 → C09 → C10"),
        ("Time", "Dijkstra", 15.25, 0.00, 0.115, "C01 → C02 → C06 → C09 → C10"),
        ("Time", "A*", 15.25, 0.00, 0.113, "C01 → C02 → C06 → C09 → C10"),
        ("Time", "NSGA-II", 35.65, 133.77, 29.497, "C01 → C02 → C04 → C06 → C09 → C10"),
        ("Time", "Simulated Annealing", 15.25, 0.00, 5.129, "C01 → C02 → C06 → C09 → C10"),
        ("Emissions", "Dijkstra", 68.64, 0.00, 0.124, "C01 → C02 → C06 → C09 → C10"),
        ("Emissions", "A*", 68.64, 0.00, 0.114, "C01 → C02 → C06 → C09 → C10"),
        ("Emissions", "NSGA-II", 68.64, 0.00, 28.791, "C01 → C02 → C06 → C09 → C10"),
        ("Emissions", "Simulated Annealing", 68.64, 0.00, 7.726, "C01 → C02 → C06 → C09 → C10"),
    ],
    columns=["Objective", "Algorithm", "Objective value", "Gap (%)", "Time (ms)", "Route"],
)

LIMITATIONS = (
    ("Synthetic transport attributes",
     "Distance derives from curated coordinates, but cost, time and emissions come from fixed "
     "mode factors. Results show algorithmic behaviour on a controlled benchmark, not operational advice."),
    ("Independent objectives",
     "Cost, time and emissions are optimised separately. The system cannot answer trade-off "
     "questions; a Pareto front or justified scalarisation is future work."),
    ("Waypoint feasibility overhead",
     "Waypoint candidates must be gene-unique and decode to a simple path. Some evaluations are "
     "spent on candidates later rejected because shortest segments overlap."),
    ("A* heuristic assumptions",
     "The heuristic uses raw latitude/longitude differences with objective-specific constants; a "
     "formal admissibility proof must account for units, longitude scaling and mode factors."),
    ("Metaheuristic optimality",
     "NSGA-II (single objective) and Simulated Annealing depend on seed, budget, temperature and "
     "cooling rate and carry no deterministic optimality guarantee."),
    ("Benchmark scope",
     "At most 60 cities from a controlled topology. Report runtime/memory as measurements for this "
     "implementation, not as claims about national-scale networks."),
)


def _show_research(config_counts: tuple[int, int, int] | None) -> None:
    st.markdown(
        '<div class="note"><b>Scope.</b> This is a <b>classical</b> optimisation system. '
        "Quantum and hybrid optimisation are future extensions — none is implemented or claimed here. "
        "Objectives are optimised one at a time, not as a combined Pareto study.</div>",
        unsafe_allow_html=True,
    )
    _section("Research problem",
             "Given a directed multimodal network, an origin, a destination and one scalar objective, "
             "find a feasible route whose accumulated objective value is as small as possible.")
    left, right = st.columns(2)
    with left:
        st.markdown("**Network model** — NetworkX `MultiDiGraph`: cities are vertices; each "
                    "road/rail/air/waterway connection is a keyed, directed edge carrying "
                    "distance, cost, time and emissions.")
        st.latex(r"G=(V,E),\quad e\in E:\ (d_e,\;c_e,\;t_e,\;g_e,\;\text{mode}_e)")
        st.latex(r"\min_{P:\,s\to r}\; F_o(P)=\sum_{e\in P} w_o(e),\qquad o\in\{c,t,g\}")
    with right:
        st.markdown("**Distance & feasibility** — great-circle distance from curated coordinates; "
                    "routes must be simple (cycle-free) and use real, keyed edges.")
        st.latex(r"d=2R\arcsin\sqrt{\sin^2\tfrac{\Delta\varphi}{2}+\cos\varphi_1\cos\varphi_2\sin^2\tfrac{\Delta\lambda}{2}}")
        st.latex(r"v_i\neq v_j\ \ \forall i\neq j")

    _section("Implemented algorithms")
    columns = st.columns(len(ALGORITHM_CARDS))
    for column, (name, tag, key, points) in zip(columns, ALGORITHM_CARDS):
        items = "".join(f"<li>{point}</li>" for point in points)
        column.markdown(
            f'<div class="algo-card"><h4><span class="dot" style="background:{ALGORITHM_COLORS[key]}"></span>'
            f'{name}</h4><span class="tag">{tag}</span><ul>{items}</ul></div>',
            unsafe_allow_html=True,
        )

    _section("Evaluation methodology",
             "Every algorithm result is validated independently of the optimiser that produced it.")
    left, right = st.columns(2)
    with left:
        st.markdown(
            "- **Reference solution:** objective-specific Dijkstra route\n"
            "- **Validity:** route rebuilt from exact edge IDs; cost/time/emissions recalculated\n"
            "- **Resources:** wall-clock time (ms) and peak Python-traced memory (bytes)\n"
            "- **Repeatability:** seeded stochastic algorithms; one unrecorded warm-up per "
            "algorithm × dataset × objective\n"
            "- **Statistics:** mean, median and standard deviation over repetitions"
        )
    with right:
        st.latex(r"\mathrm{gap}(P)=\max\!\left(0,\frac{F_o(P)-F_o(P^{\mathrm{ref}})}{F_o(P^{\mathrm{ref}})}\times100\right)")
        st.latex(r"N_{\text{measured}}=a\,d\,o\,r\quad(a=\text{algorithms})")
        if config_counts:
            d, o, r = config_counts
            st.caption(f"Current sidebar selection: {len(ALGORITHM_LABELS)} × {d} dataset(s) × {o} objective(s) × {r} "
                       f"repetition(s) = **{len(ALGORITHM_LABELS) * d * o * r}** measured executions.")

    _section("Reference results (paper §8.6)",
             "dataset_10 · C01 → C10 · 1 repetition · NSGA-II pop 10 × 3 generations · SA 30 iterations.")
    st.dataframe(
        REFERENCE_RESULTS, use_container_width=True, hide_index=True,
        column_config={
            "Objective value": st.column_config.NumberColumn(format="%.2f"),
            "Gap (%)": st.column_config.ProgressColumn(format="%.2f%%", min_value=0.0, max_value=140.0),
            "Time (ms)": st.column_config.NumberColumn(format="%.3f"),
        },
    )
    st.caption("Dijkstra and A* match the reference for all objectives; Simulated Annealing does too "
               "under this seed/budget. NSGA-II shows a positive gap for cost and time under its small "
               "budget. These observations describe this configuration only.")

    _section("Limitations & threats to validity")
    left, right = st.columns(2)
    for index, (title, text) in enumerate(LIMITATIONS):
        with (left if index % 2 == 0 else right):
            with st.expander(title):
                st.write(text)

    _section("Planned research extensions")
    st.markdown(
        "- Confidence intervals and rejected-candidate rates for stochastic algorithms\n"
        "- Transfer penalties, capacity and time-window constraints; real schedule data\n"
        "- Vector objectives with a Pareto front (true multi-objective NSGA-II)\n"
        "- Quantum / hybrid optimisation (e.g. QAOA-style formulations) as a comparison baseline"
    )


# --------------------------------------------------------------------------- #
# History tab
# --------------------------------------------------------------------------- #
def _show_history() -> None:
    history = sorted(RESULTS_ROOT.glob("*.json"), reverse=True) if RESULTS_ROOT.is_dir() else []
    if not history:
        st.info("No saved experiments yet.")
        return
    rows = []
    for path in history:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        configuration = payload.get("configuration") or {}
        rows.append({
            "Experiment": _history_label(path),
            "Created": payload.get("created_at"),
            "Datasets": ", ".join(configuration.get("datasets", [])),
            "Objectives": ", ".join(configuration.get("objectives", [])),
            "Route": f"{configuration.get('source')} → {configuration.get('destination')}",
            "Repeats": configuration.get("repeats"),
            "Executions": payload.get("algorithm_execution_count"),
        })
    _section("Saved experiments", f"{len(rows)} experiments stored under experiments/results.")
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    selected = st.selectbox("Inspect experiment", history, format_func=_history_label)
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
        },
        expanded=False,
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


# --------------------------------------------------------------------------- #
# Page
# --------------------------------------------------------------------------- #
def _clear_route_state() -> None:
    for key in ("route_map_record", "route_map_context", "route_map_algorithm",
                "route_map_experiment_id"):
        st.session_state.pop(key, None)


def _hero(dataset_label: str, summary: dict[str, object] | None) -> None:
    meta = ""
    if summary:
        meta = (f"Dataset <b>{escape(dataset_label)}</b><br>{summary['cities']} cities · "
                f"{summary['connections']} connections")
    st.markdown(
        '<div class="page-head"><div>'
        '<div class="eyebrow">Route optimisation research</div>'
        "<h1>Multimodal Transportation Route Optimisation</h1>"
        "<p>Benchmarking Dijkstra, A*, NSGA-II, Simulated Annealing and Ant Colony Optimization across road, rail, air and "
        "waterway connections between Indian cities.</p></div>"
        f'<div class="meta">{meta}</div></div>',
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(
        page_title="Multimodal Route Optimization",
        page_icon="🧭",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(DASHBOARD_CSS, unsafe_allow_html=True)

    datasets = available_datasets()
    if not datasets:
        st.error(f"No processed datasets found under {DATASETS_ROOT}.")
        return

    with st.sidebar:
        st.markdown('<div class="side-title">Experiment setup</div>', unsafe_allow_html=True)
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
        if not selected_datasets:
            st.warning("Select at least one dataset.")
            return
        city_labels = city_options(selected_datasets[0])
        cities = list(city_labels)
        source = st.selectbox("Source city", cities, index=0, format_func=city_labels.__getitem__)
        destination_options = [city for city in cities if city != source]
        destination = st.selectbox(
            "Destination city", destination_options, index=0, format_func=city_labels.__getitem__
        )
        with st.expander("Algorithm parameters", expanded=False):
            repeats = st.number_input(
                "Measured repetitions", min_value=1, max_value=20, value=1,
                help=PARAMETER_HELP["repeats"],
            )
            population_size = st.number_input(
                "NSGA-II population", min_value=2, max_value=500, value=10,
                help=PARAMETER_HELP["population"],
            )
            generations = st.number_input(
                "NSGA-II generations", min_value=1, max_value=500, value=3,
                help=PARAMETER_HELP["generations"],
            )
            iterations = st.number_input(
                "Simulated Annealing iterations", min_value=1, max_value=5000, value=30,
                help=PARAMETER_HELP["iterations"],
            )
            aco_ants = st.number_input(
                "ACO ants",
                min_value=1,
                max_value=200,
                value=10,
                help=PARAMETER_HELP["aco_ants"],
            )
            aco_iterations = st.number_input(
                "ACO iterations",
                min_value=1,
                max_value=500,
                value=30,
                help=PARAMETER_HELP["aco_iterations"],
            )
        planned = len(ALGORITHM_LABELS) * len(selected_datasets) * len(selected_objectives) * int(repeats)
        st.caption(f"Planned: **{planned}** measured executions "
                   f"({len(ALGORITHM_LABELS)} algorithms × {len(selected_datasets)} × {len(selected_objectives)} × {int(repeats)}).")
        run_clicked = st.button(
            "Run experiment", type="primary", use_container_width=True,
            disabled=not selected_objectives,
        )

    route_context = (
        tuple(selected_datasets),
        tuple(selected_objectives),
        source,
        destination,
    )
    if st.session_state.get("route_map_context") not in (None, route_context):
        _clear_route_state()

    _hero(selected_datasets[0], _dataset_summary(selected_datasets[0]))

    if run_clicked:
        _clear_route_state()
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
                        int(population_size),
                        int(generations),
                        int(iterations),
                        int(aco_ants),
                        int(aco_iterations),
                    ),
                )
                status.update(label="Experiment completed", state="complete", expanded=False)
            st.session_state["latest_result"] = result
            st.toast(f"Completed {result.algorithm_execution_count} measured executions.")
        except ValueError as exc:
            st.error(str(exc))

    result = st.session_state.get("latest_result")
    has_result = isinstance(result, ExperimentResult)

    # Only the active view is rendered, so Leaflet maps always measure a visible container.
    view = st.radio(
        "View",
        ["Overview", "Route map", "Algorithm comparison", "Research", "History"],
        horizontal=True,
        label_visibility="collapsed",
        key="active_view",
    )
    if view == "Overview":
        if has_result:
            st.caption(f"Experiment {result.experiment_id}"
                       + (f" · {result.experiment_name}" if result.experiment_name else ""))
            _show_run_overview(result)
        else:
            st.markdown(
                '<div class="note">No experiment run yet in this session. Choose a setup '
                "in the sidebar and press <b>Run experiment</b>. Meanwhile, explore the network and "
                "the benchmark evidence already saved from earlier runs.</div>",
                unsafe_allow_html=True,
            )
        _show_network_overview(selected_datasets[0])
        _show_benchmark_evidence()
    elif view == "Route map":
        if has_result:
            _show_route_visualization(result, source, destination, route_context)
        else:
            st.info("Run an experiment to see optimised routes on the India map.")
    elif view == "Algorithm comparison":
        if has_result:
            _show_charts(result)
        else:
            st.info("Run an experiment to compare solution quality, resources, convergence and scalability.")
    elif view == "Research":
        _show_research((len(selected_datasets), len(selected_objectives), int(repeats)))
    else:
        _show_history()


if __name__ == "__main__":
    main()
