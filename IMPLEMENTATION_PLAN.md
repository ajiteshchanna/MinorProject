# Implementation Plan

## Project Overview

This project, **Multimodal Transportation Route Optimization using Classical and Quantum Computing**, will first deliver a classical optimization system for routes between cities connected by road, rail, air and waterways.

The classical system will optimize the following objectives independently:

- Minimum transportation cost
- Minimum travel time
- Minimum carbon emissions

The evaluation dashboard reports means and standard deviations from valid
measured repetitions, compares solutions with the project's objective-specific
reference shortest path, distinguishes NSGA-II generations from Simulated
Annealing iterations, and provides cross-dataset performance plots when saved
experiments use comparable endpoints and settings. These visualizations do
not claim real-world scalability from dataset size alone; quantum and hybrid
optimization remain future work.

The application will compare Dijkstra's Algorithm, A* Search, NSGA-II and Simulated Annealing. Cost, time and emissions will remain separate objectives; they will not be combined into a weighted score. Quantum and hybrid optimization are explicitly outside the scope of this roadmap and will be considered only after the classical system is complete.

## Technology Stack

- **Frontend:** Streamlit
- **Backend:** Python
- **Graph processing:** NetworkX `MultiDiGraph`
- **Data processing:** Pandas and NumPy
- **Evolutionary optimization:** pymoo (NSGA-II)
- **Visualization:** Plotly
- **Route map visualization:** Folium, Streamlit-Folium and OpenStreetMap tiles
- **Testing:** pytest
- **Memory benchmarking:** psutil and/or tracemalloc
- **Initial result storage:** CSV and JSON

Streamlit will communicate directly with the Python backend. A separate FastAPI service is not required for the initial version.

## Initial Directory Structure

The workspace is currently empty, so the following structure will be established incrementally:

```text
Multimodal-Transportation-Optimization/
├── app/
│   ├── main.py
│   ├── pages/
│   └── components/
├── backend/
│   ├── experiment_manager.py
│   ├── config.py
│   ├── data/
│   ├── objectives/
│   ├── algorithms/
│   ├── evaluation/
│   └── results/
├── datasets/
│   ├── raw/
│   └── processed/
├── experiments/
│   ├── configurations/
│   └── saved_results/
├── tests/
├── notebooks/
├── requirements.txt
├── README.md
└── .gitignore
```

Planned modules should remain focused and independently testable. The structure may be adjusted only when implementation details require it, without introducing unnecessary services or abstractions.

## Implementation Phases

### Phase 1: Project Setup and Dataset Preparation

**Objective:** Establish the Python environment and prepare six validated transportation datasets.

**Tasks:**

- Set up the Python environment and install the required dependencies.
- Establish the project directory structure and basic configuration.
- Prepare a master city dataset and transportation connection dataset.
- Create datasets containing 10, 20, 30, 40, 50 and 60 cities.
- Include city coordinates and connections across available transport modes.
- Include distance, cost, travel time and carbon emissions as edge attributes.
- Validate geographical plausibility, especially for waterways.
- Clearly label real sourced information separately from simulated attributes.

**Expected deliverable:** A clean, validated collection of six datasets with documented sources and attributes.

**Runnable checkpoint:** Run a dataset inspection script that loads each dataset and reports its cities, edges, transport modes and basic network statistics. Resolve validation errors before continuing.

### Phase 2: Multimodal Graph Construction

**Objective:** Convert each prepared dataset into a usable multimodal transportation graph.

**Tasks:**

- Implement graph construction with NetworkX `MultiDiGraph`.
- Represent cities as nodes and transportation connections as directed edges.
- Support parallel edges for different modes between the same cities.
- Store distance, cost, time, emissions and mode on each edge.
- Implement connectivity checks and source-destination validation.
- Preserve edge identities so the selected mode can be reconstructed for every route leg.

**Expected deliverable:** A reusable graph-building module for all six datasets.

**Runnable checkpoint:** Load a selected dataset, construct and visualize its graph, and verify that parallel modes and their individual attributes are preserved.

### Phase 3: Classical Optimization Algorithm Implementation

**Objective:** Implement four classical algorithms behind a common optimization interface.

**Tasks:**

- Implement Dijkstra's Algorithm for scalar shortest paths.
- Implement A* Search with an admissible heuristic for the selected objective.
- Implement NSGA-II with a discrete route representation and single-objective fitness for the selected primary comparison objective.
- Implement Simulated Annealing with feasible route-based neighborhood operations.
- Allow every algorithm to optimize cost, time or emissions independently.
- Pass the same graph, source, destination and objective to every algorithm.
- Return a standardized result containing the route, modes, objective value and algorithm metadata.

**Expected deliverable:** Four independently testable optimization implementations.

**Runnable checkpoint:** Execute every algorithm on a small known network and verify the returned route, selected modes, feasibility and objective value.

### Phase 4: Evaluation and Benchmarking Engine

**Objective:** Provide a consistent framework for validating and comparing algorithm results.

**Tasks:**

- Implement common route validation.
- Recalculate total cost, time and emissions for every returned route.
- Measure execution time and memory consumption.
- Record nodes explored or function evaluations where applicable.
- Calculate optimality gaps against valid reference solutions.
- Track convergence information for NSGA-II and Simulated Annealing.
- Support repeated independent runs for stochastic algorithms.
- Generate standardized comparison tables.

**Expected deliverable:** A reusable evaluation and benchmarking engine.

**Runnable checkpoint:** Run all four algorithms on the same dataset and objective, validate their solutions, and produce a comparative results table using only measured values.

### Phase 5: User-Controlled Experiment Manager and Results Storage

**Objective:** Orchestrate only the dataset-objective combinations explicitly selected by the user.

**Tasks:**

- Accept one or more selected datasets and objectives.
- Generate combinations dynamically from those selections.
- Execute all four algorithms for each selected combination.
- Guarantee that unselected datasets and objectives are never loaded or executed.
- Load only data required for the current experiment.
- Store experiment configuration and algorithm results in CSV/JSON.
- Keep results separate for every dataset-objective combination.
- Handle invalid selections and disconnected source-destination pairs explicitly.

For `d` selected datasets and `o` selected objectives, the execution manager must schedule exactly `d × o` combinations and `4 × d × o` algorithm executions, subject to valid input and configured repeated-run behavior.

**Expected deliverable:** A working experiment execution engine with persistent result storage.

**Runnable checkpoint:** Run configurations such as 10 cities + Cost and 10/20 cities + Cost/Time. Verify the exact combinations, algorithm execution count, and saved result grouping.

### Phase 6: Frontend and Interactive Dashboard Development

**Objective:** Build the user-facing Streamlit application around the completed backend pipeline.

**Status:** Complete, including the validated interactive schematic India route map.

**Tasks:**

- Create an experiment setup interface.
- Provide multi-selection for the six datasets.
- Provide multi-selection for Cost, Time and Emissions.
- Provide source and destination city selectors.
- Add a Run Experiment button; do not execute experiments automatically.
- Display execution progress and status.
- Display optimized routes and transportation modes.
- Present cost, time and emissions for every algorithm.
- Provide comparative tables and Plotly visualizations.
- Add an experiment history view for saved experiments.
- Show a human-readable experiment name separately from the unique persisted
  experiment ID, while retaining backward compatibility with older JSON
  records.
- Add an interactive India route map for one selected algorithm at a time.

#### Interactive India Route Map

**Objective:** Show the selected algorithm's optimized multimodal route on an
interactive map using the city coordinates already stored in the selected
dataset.

**Scope and workflow:**

- After an experiment completes, select Dijkstra, A*, NSGA-II or Simulated
  Annealing in the Route Visualization section.
- Select **View Route on Map** to render that algorithm's existing result; no
  optimization is executed again.
- Resolve each route leg using its preserved NetworkX `MultiDiGraph` edge key,
  transport mode and edge attributes, so parallel transport edges are not
  replaced by an arbitrary connection.
- Display source, destination and intermediate city markers, connection
  popups, a legend and automatically fitted route bounds.
- Use Folium with Streamlit-Folium and OpenStreetMap tiles.
- Keep the map legend readable with explicit high-contrast black text, a white
  background, grey border and spacing that separates marker and line entries.

Transport modes use these map conventions:

| Mode | Colour | Line style |
|---|---|---|
| Road | Blue | Solid |
| Rail | Red | Dashed |
| Air | Purple | Dotted |
| Waterways | Green | Dash-dot |

The map displays one selected algorithm's route at a time. Connections are
schematic straight city-to-city lines based on dataset coordinates; they are
not actual road routes, railway tracks, flight paths or navigable waterways.

The experiment setup also provides detailed Markdown help on the four numeric
parameters. Each native Streamlit information tooltip explains what the
parameter controls, why it matters, recommended quick-test and benchmarking
values, when a higher value is useful, and its computational trade-off.

New saved experiments use names such as `Exp_D10_AHM_AMR`, derived from the
selected dataset size and actual city names. The timestamp/UUID-based
`experiment_id` remains the stable CSV/JSON filename identity. Existing
records without an `experiment_name` continue to load and receive a
dashboard-only fallback label.

**Expected deliverable:** A functional interactive dashboard connected to the experiment manager.

**Runnable checkpoint:** Launch Streamlit, select one dataset, one objective and valid source/destination cities, run the experiment, and inspect the displayed results and visualizations.

### Phase 7: Integration, Testing and Finalization

**Objective:** Make the classical application reliable, reproducible and ready for demonstration.

**Tasks:**

- Perform integration testing across all six datasets.
- Test all three objectives and all four algorithms.
- Verify route feasibility, objective calculations and output consistency.
- Test disconnected networks, invalid inputs and other edge cases.
- Verify selection logic and exact execution behavior.
- Review runtime and memory measurements.
- Improve visualization clarity and user experience.
- Finalize the README, documentation and actual experimental results.

**Expected deliverable:** A fully integrated and tested classical multimodal transportation optimization application.

**Runnable checkpoint:** Demonstrate multiple user-selected experiments end to end, showing valid routes, algorithm comparisons and saved results.

## Completion Criteria

The classical implementation is complete when:

1. Six validated datasets for 10–60 cities can be loaded.
2. Each dataset can be represented as a multimodal `MultiDiGraph` with reconstructable edge modes.
3. All four algorithms optimize cost, time and emissions independently through a common interface.
4. Routes are validated and benchmarked using measured execution and memory data.
5. The experiment manager executes only explicitly selected dataset-objective combinations.
6. Streamlit supports configuration, execution, result comparison, experiment
   history and one-algorithm-at-a-time schematic route-map visualization.
7. Automated tests and end-to-end demonstrations pass across the supported datasets and objectives.
8. Documentation and stored results describe actual executions only; no experimental metrics are invented.

## How to Use the Runnable Checkpoints

Each checkpoint is a gate for its phase, not a replacement for automated tests. After completing a phase, run its specified script, test command or demonstration, inspect the output against the stated acceptance conditions, and fix failures before starting the next phase. Keep checkpoint outputs reproducible through documented inputs and configurations so later phases can rely on verified datasets, graphs, algorithms and execution behavior.
