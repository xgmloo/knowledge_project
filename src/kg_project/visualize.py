from __future__ import annotations

from pathlib import Path

from pyvis.network import Network

from .models import Subgraph


def render_subgraph(subgraph: Subgraph, output_html: Path) -> Path:
    net = Network(height="800px", width="100%", bgcolor="#ffffff", font_color="black", directed=True)

    for node in subgraph.nodes:
        net.add_node(
            node["id"],
            label=node["name"],
            title=f"{node['name']} ({node.get('type', 'Concept')})",
            group=node.get("type", "Concept"),
        )

    for edge in subgraph.edges:
        net.add_edge(edge["source"], edge["target"], label=edge.get("type", "RELATED"))

    output_html.parent.mkdir(parents=True, exist_ok=True)
    net.write_html(str(output_html), notebook=False)
    return output_html
