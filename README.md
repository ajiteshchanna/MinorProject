# Multimodal Transportation Route Optimization

This project compares four classical route optimizers on directed multimodal
transportation graphs:

- Dijkstra
- A* Search
- NSGA-II with a discrete waypoint representation
- Simulated Annealing

Cost, travel time, and carbon emissions are optimized independently. The
transport attributes are simulated development data; city coordinates are
manually curated reference data. See [datasets/README.md](datasets/README.md).

## Setup

```powershell
python -m pip install -r requirements.txt
```

## Tests and checkpoints

Run the complete automated suite:

```powershell
python -m pytest -q
```

Run the Phase 7 integration checkpoint across all six datasets, three
objectives, and four algorithms:

```powershell
python manual_phase7_checkpoint.py
```

The checkpoint validates 72 measured algorithm executions using the selected
lightweight development parameters. It reports values produced at runtime and
does not store invented metrics.

## Dashboard

Launch the Streamlit dashboard:

```powershell
streamlit run app/main.py
```

The dashboard requires explicit dataset and objective selections and does not
run experiments automatically. Results are saved as CSV and JSON files under
`experiments/results/`. These generated result files are experiment artifacts
and should be retained only when the corresponding run is intentionally
recorded.

## Backend usage

The Phase 5 manager can be used without Streamlit:

```python
from backend.experiment_manager import ExperimentManager

result = ExperimentManager().run(
    datasets=("dataset_10",),
    objectives=("cost", "time"),
    source="C01",
    destination="C10",
    repeats=3,
)
```

The Phase 4 evaluation layer validates exact edge identities, recalculates all
route metrics, measures execution time and peak memory, reports optimality gaps,
and records convergence for iterative algorithms. Dijkstra and A* have no
iterative convergence history because they are single-pass searches.
