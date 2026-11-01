from backend.graph import build_graph

# Load the 10-city dataset
G = build_graph("datasets/processed/dataset_10")

# Basic graph information
print("\nGRAPH INFORMATION")
print("-------------------------")
print("Graph type:", type(G))
print("Number of cities:", G.number_of_nodes())
print("Number of connections:", G.number_of_edges())

# Display all cities
print("\nCITIES")
for node, data in G.nodes(data=True):
    print(node, data)

# Display first 10 transportation connections
print("\nTRANSPORT CONNECTIONS")
for u, v, key, data in list(G.edges(keys=True, data=True))[:10]:
    print(
        f"{u} -> {v} | "
        f"Key: {key} | "
        f"Mode: {data.get('mode')} | "
        f"Distance: {data.get('distance_km')} | "
        f"Cost: {data.get('cost')} | "
        f"Time: {data.get('travel_time')} | "
        f"Emissions: {data.get('emissions')}"
    )

# Check parallel connections
print("\nPARALLEL CONNECTIONS")
for u, v in G.edges():
    edges = G.get_edge_data(u, v)

    if len(edges) > 1:
        print(f"\n{u} -> {v}")

        for key, data in edges.items():
            print(
                f"  {key}: "
                f"{data.get('mode')}"
            )