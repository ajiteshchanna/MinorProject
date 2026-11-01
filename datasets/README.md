# Phase 1 Datasets

The dataset package contains:

- `raw/cities_master.csv`: 60 manually curated Indian city reference coordinates.
- `raw/connections_master.csv`: deterministic master connections.
- `processed/dataset_<N>/`: datasets containing exactly 10, 20, 30, 40, 50 or 60 cities.

Coordinates are labelled `manually_curated_reference` and should be verified against an authoritative geographic source before publication. Transport connections and the `cost`, `travel_time_hours` and `carbon_emissions_kg` values are labelled `simulated_for_development`; they are not claimed as real-world measurements.

Waterway edges are deliberately limited to the explicit corridors documented in each dataset's `metadata.json`. Every generated connection is directed, so each corridor has one record in each direction.

## Regenerate and Inspect

From the project root:

```text
python -m backend.data.prepare_datasets
python -m backend.data.inspect_datasets
python -m pytest -q
```

The generator is deterministic and writes the same schema and values on each run.
