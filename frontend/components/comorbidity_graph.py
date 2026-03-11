"""NetworkX graph → Plotly visualization component."""

import networkx as nx
import plotly.graph_objects as go
import streamlit as st


def render_comorbidity_graph(network: dict) -> None:
    nodes = network.get("nodes", [])
    edges = network.get("edges", [])

    if not nodes:
        st.info("No comorbidity data available.")
        return

    G = nx.Graph()
    for node in nodes:
        G.add_node(node["icd9_code"], label=node.get("label", node["icd9_code"]), is_dangerous=node.get("is_dangerous", False))
    for edge in edges:
        G.add_edge(edge["source"], edge["target"], weight=edge.get("weight", 1), is_dangerous=edge.get("is_dangerous", False))

    pos = nx.spring_layout(G, seed=42, k=2.0)

    # Edges
    edge_traces = []
    for u, v, data in G.edges(data=True):
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        color = "#FF4B4B" if data.get("is_dangerous") else "#CCCCCC"
        width = 3 if data.get("is_dangerous") else 1

        edge_traces.append(go.Scatter(
            x=[x0, x1, None],
            y=[y0, y1, None],
            mode="lines",
            line={"width": width, "color": color},
            hoverinfo="none",
            showlegend=False,
        ))

    # Nodes
    node_x = []
    node_y = []
    node_text = []
    node_colors = []
    node_sizes = []

    for node_id in G.nodes:
        x, y = pos[node_id]
        node_x.append(x)
        node_y.append(y)
        label = G.nodes[node_id].get("label", node_id)
        is_dangerous = G.nodes[node_id].get("is_dangerous", False)
        degree = G.degree(node_id)
        node_text.append(f"{label}<br>ICD9: {node_id}<br>Connections: {degree}")
        node_colors.append("#FF4B4B" if is_dangerous else "#4B9BFF")
        node_sizes.append(max(20, 10 + degree * 5))

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=[G.nodes[n].get("label", n) for n in G.nodes],
        textposition="top center",
        textfont={"size": 10},
        hovertext=node_text,
        hoverinfo="text",
        marker={
            "size": node_sizes,
            "color": node_colors,
            "line": {"width": 1, "color": "#333333"},
        },
        showlegend=False,
    )

    fig = go.Figure(
        data=[*edge_traces, node_trace],
        layout=go.Layout(
            title="Comorbidity Network",
            showlegend=False,
            hovermode="closest",
            xaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
            yaxis={"showgrid": False, "zeroline": False, "showticklabels": False},
            margin={"l": 20, "r": 20, "t": 40, "b": 20},
            height=500,
        ),
    )

    st.plotly_chart(fig, use_container_width=True)

    # Dangerous edges legend
    dangerous = network.get("dangerous_edges", [])
    if dangerous:
        st.markdown("**Dangerous co-occurrences:**")
        for edge in dangerous:
            desc = edge.get("description") or f"{edge['source']} + {edge['target']}"
            st.markdown(f"- {desc}")

    # Clusters
    clusters = network.get("clusters", [])
    if clusters:
        st.markdown("**Disease clusters:**")
        for cluster in clusters:
            risk = f" — {cluster['risk_note']}" if cluster.get("risk_note") else ""
            st.markdown(f"- {cluster['name']}{risk}")
