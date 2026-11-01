"""Create a Plotly visualization for a multimodal transportation graph."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import plotly.graph_objects as go

from .graph import load_graph

MODE_COLORS = {
    "road": "#1f77b4",
    "rail": "#2ca02c",
    "air": "#d62728",
    "waterway": "#17becf",
}


def create_graph_figure(graph: nx.MultiDiGraph) -> go.Figure:
    """Create a coordinate-based graph figure with one trace per mode."""
    node_positions = {
        node: (float(data["longitude"]), float(data["latitude"]))
        for node, data in graph.nodes(data=True)
    }
    traces: list[go.Scattergeo] = []
    for mode, color in MODE_COLORS.items():
        edge_longitudes: list[float | None] = []
        edge_latitudes: list[float | None] = []
        for source, destination, data in graph.edges(data=True):
            if data["mode"] != mode:
                continue
            source_lon, source_lat = node_positions[source]
            destination_lon, destination_lat = node_positions[destination]
            edge_longitudes.extend((source_lon, destination_lon, None))
            edge_latitudes.extend((source_lat, destination_lat, None))
        if edge_longitudes:
            traces.append(
                go.Scattergeo(
                    lon=edge_longitudes,
                    lat=edge_latitudes,
                    mode="lines",
                    line={"color": color, "width": 1},
                    name=mode.title(),
                )
            )
    traces.append(
        go.Scattergeo(
            lon=[position[0] for position in node_positions.values()],
            lat=[position[1] for position in node_positions.values()],
            text=[
                f"{node}: {graph.nodes[node]['city_name']}"
                for node in node_positions
            ],
            mode="markers",
            marker={"size": 7, "color": "#111111"},
            name="Cities",
        )
    )
    return go.Figure(
        data=traces,
        layout=go.Layout(
            title="Multimodal Transportation Network",
            geo={"scope": "asia", "showland": True, "landcolor": "#eeeeee"},
            legend={"title": {"text": "Transport mode"}},
        ),
    )


def export_graph_html(graph: nx.MultiDiGraph, output_path: Path) -> None:
    """Write an interactive graph visualization to an HTML file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    create_graph_figure(graph).write_html(output_path)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_dir", type=Path)
    parser.add_argument("output_path", type=Path)
    args = parser.parse_args()
    export_graph_html(load_graph(args.dataset_dir), args.output_path)
    print(f"Wrote graph visualization to {args.output_path.resolve()}")


if __name__ == "__main__":
    main()
