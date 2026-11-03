import math

import pandas as pd

from app.comparison import (
    convergence_rows,
    memory_axis_type,
    objective_statistics,
    optimality_gap_statistics,
    scalability_statistics,
)


def _table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"dataset": "dataset_10", "objective": "cost", "algorithm": "sa",
             "run": 1, "valid": True, "objective_value": 10, "optimality_gap": 0,
             "execution_time_ms": 2, "peak_memory_bytes": 100,
             "convergence": [5, 4]},
            {"dataset": "dataset_10", "objective": "cost", "algorithm": "sa",
             "run": 2, "valid": True, "objective_value": 14, "optimality_gap": 40,
             "execution_time_ms": 4, "peak_memory_bytes": 200,
             "convergence": [6, 4]},
            {"dataset": "dataset_10", "objective": "cost", "algorithm": "sa",
             "run": 3, "valid": False, "objective_value": 100, "optimality_gap": 900,
             "execution_time_ms": 9, "peak_memory_bytes": 900,
             "convergence": [9]},
        ]
    )


def test_objective_statistics_use_valid_individual_runs_and_single_run_is_nan() -> None:
    stats = objective_statistics(_table()).iloc[0]
    assert stats["mean_objective_value"] == 12
    assert stats["valid_measured_runs"] == 2
    assert math.isclose(stats["objective_stddev"], math.sqrt(8))


def test_gap_and_memory_safeguards() -> None:
    gaps = optimality_gap_statistics(_table()).iloc[0]
    assert gaps["mean_optimality_gap"] == 20
    assert memory_axis_type(_table()) == "log"
    zero_memory = _table().copy()
    zero_memory.loc[0, "peak_memory_bytes"] = 0
    assert memory_axis_type(zero_memory) == "linear"


def test_convergence_has_algorithm_specific_step_types_and_scalability() -> None:
    convergence = convergence_rows(_table())
    assert set(convergence["step_type"]) == {"Iteration"}
    scalability = scalability_statistics([_table()], "cost", "objective")
    assert list(scalability["city_count"]) == [10]
