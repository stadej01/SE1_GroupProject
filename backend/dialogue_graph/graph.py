
"""Convert a validated AST into React Flow graph data."""

from .validator import GraphValidationError, validate_graph_integrity


def _preview(node):
    """Return the first dialogue line as a node preview."""
    for item in node["sequence"]:
        if item["type"] == "dialogue":
            return f'{item["speaker"]}: {item["text"]}'
    return ""


def build_graph(ast):
    """Build nodes and edges from a validated Markdown AST."""
    diagnostics = validate_graph_integrity(ast)

    if any(item["severity"] == "error" for item in diagnostics):
        raise GraphValidationError(diagnostics)

    start_nodes = ast.get("start_nodes", [])
    nodes = []

    for node in ast["nodes"]:
        nodes.append({
            "id": node["id"],
            "category": node["metadata"].get("category"),
            "color": node["metadata"].get("color"),
            "preview": _preview(node),
            "metadata": node["metadata"],
            "dialogue_lines": [
                {
                    "speaker": i["speaker"],
                    "text": i["text"],
                    "source_line": i["source_line"]
                }
                for i in node["sequence"]
                if i["type"] == "dialogue"
            ],
            "source_line": node["source_line"],
            "source_end_line": node["source_end_line"]
        })

    edges = []

    for node in ast["nodes"]:
        # Jumps automatically transition to another node.
        jumps = [
            i for i in node["sequence"]
            if i["type"] == "jump"
        ]

        # Identify the last content line in the node.
        last_line = max(
            (
                i["source_line"]
                for i in node["sequence"] + node["choices"]
            ),
            default=None
        )

        for kind, items in (
            ("jump", jumps),
            ("choice", node["choices"])
        ):
            for index, item in enumerate(items):
                edges.append({
                    # Stable IDs prevent unnecessary edge remounting.
                    "id": f'{node["id"]}:{kind}:{index}',
                    "source": node["id"],
                    "target": item["target"],
                    "kind": kind,
                    "label": item.get("text"),
                    "condition": item["condition"],
                    "source_line": item["source_line"],

                    # A jump at the end of a node uses a solid line.
                    "ends_node": (
                        kind == "jump"
                        and item["source_line"] == last_line
                    ),
                })

    return {
        "snapshot_id": ast["snapshot_id"],
        "start_nodes": start_nodes,
        "start": start_nodes[0] if start_nodes else None,
        "nodes": nodes,
        "edges": edges,
        "diagnostics": diagnostics
    }
