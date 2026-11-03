"""Validity-aware data preparation for the experiment comparison charts."""

from __future__ import annotations

from collections.abc import Iterable
import math
import re

import pandas as pd


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def measured_rows(table: pd.DataFrame) -> pd.DataFrame:
    """Return valid measured rows with finite numeric values only."""
    if table.empty:
        return table.copy()
    rows = table.copy()
    valid = rows.get("valid", pd.Series(True, index=rows.index)).fillna(False).astype(bool)
    rows = rows.loc[valid].copy()
    for column in ("objective_value", "optimality_gap", "execution_time_ms", "peak_memory_bytes"):
        if column in rows:
            rows[column] = _numeric(rows[column])
    return rows


def _std(values: pd.Series) -> float:
    values = values.dropna()
    return float(values.std(ddof=1)) if len(values) > 1 else float("nan")


def objective_statistics(table: pd.DataFrame) -> pd.DataFrame:
    """Aggregate objective values from individual valid measured repetitions."""
    rows = measured_rows(table)
    if rows.empty or "objective_value" not in rows:
        return pd.DataFrame()
    rows = rows.dropna(subset=["dataset", "objective", "algorithm", "objective_value"])
    return rows.groupby(["dataset", "objective", "algorithm"], as_index=False).agg(
        mean_objective_value=("objective_value", "mean"),
        objective_stddev=("objective_value", _std),
        valid_measured_runs=("objective_value", "count"),
    )


def resource_statistics(table: pd.DataFrame) -> pd.DataFrame:
    """Aggregate timing and Python-traced memory from individual measured runs."""
    rows = measured_rows(table)
    required = {"dataset", "objective", "algorithm", "execution_time_ms", "peak_memory_bytes"}
    if rows.empty or not required.issubset(rows.columns):
        return pd.DataFrame()
    return rows.dropna(subset=list(required)).groupby(
        ["dataset", "objective", "algorithm"], as_index=False
    ).agg(
        mean_execution_time_ms=("execution_time_ms", "mean"),
        execution_time_stddev=("execution_time_ms", _std),
        mean_peak_memory_bytes=("peak_memory_bytes", "mean"),
        peak_memory_stddev=("peak_memory_bytes", _std),
        measured_runs=("execution_time_ms", "count"),
    )


def optimality_gap_statistics(table: pd.DataFrame) -> pd.DataFrame:
    """Aggregate persisted per-run gaps; never infer a reference optimum."""
    rows = measured_rows(table)
    required = {"dataset", "objective", "algorithm", "objective_value", "optimality_gap"}
    if rows.empty or not required.issubset(rows.columns):
        return pd.DataFrame()
    rows = rows.dropna(subset=list(required))
    return rows.groupby(["dataset", "objective", "algorithm"], as_index=False).agg(
        mean_objective_value=("objective_value", "mean"),
        mean_optimality_gap=("optimality_gap", "mean"),
        optimality_gap_stddev=("optimality_gap", _std),
        measured_runs=("optimality_gap", "count"),
    )


def convergence_rows(table: pd.DataFrame) -> pd.DataFrame:
    """Expand stored histories with algorithm-specific step labels."""
    records: list[dict[str, object]] = []
    for row in table.to_dict("records"):
        if not bool(row.get("valid", True)):
            continue
        history = row.get("convergence", ())
        if not isinstance(history, (list, tuple)):
            continue
        algorithm = str(row.get("algorithm", ""))
        step_type = "Generation" if algorithm == "nsga2" else "Iteration"
        for step, value in enumerate(history, start=1):
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(numeric_value):
                records.append({
                    "dataset": row.get("dataset"),
                    "objective": row.get("objective"),
                    "algorithm": algorithm,
                    "run": row.get("run"),
                    "step": step,
                    "step_type": step_type,
                    "best_so_far": numeric_value,
                })
    return pd.DataFrame(records)


def memory_axis_type(table: pd.DataFrame) -> str:
    """Use log scale only when every displayed memory value is strictly positive."""
    values = measured_rows(table).get("peak_memory_bytes", pd.Series(dtype=float)).dropna()
    return "log" if not values.empty and bool((values > 0).all()) else "linear"


def dataset_size(dataset: object) -> float | None:
    match = re.search(r"(\d+)$", str(dataset))
    return float(match.group(1)) if match else None


def scalability_statistics(
    tables: Iterable[pd.DataFrame], objective: str, metric: str
) -> pd.DataFrame:
    """Combine saved tables only when their objective and endpoints agree."""
    frames = []
    for table in tables:
        rows = measured_rows(table)
        if rows.empty or "objective" not in rows or "dataset" not in rows:
            continue
        rows = rows.loc[rows["objective"].eq(objective)].copy()
        if rows.empty:
            continue
        rows["city_count"] = rows["dataset"].map(dataset_size)
        frames.append(rows)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True).dropna(subset=["city_count"])
    metrics = {
        "objective": "objective_value",
        "execution_time": "execution_time_ms",
        "memory": "peak_memory_bytes",
        "optimality_gap": "optimality_gap",
    }
    value_column = metrics[metric]
    if value_column not in combined:
        return pd.DataFrame()
    return combined.dropna(subset=[value_column]).groupby(
        ["city_count", "dataset", "algorithm"], as_index=False
    ).agg(value=(value_column, "mean"), measured_runs=(value_column, "count"))
