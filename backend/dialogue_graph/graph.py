"""Validated AST -> React Flow transport contract; independent of Django."""
from .validator import GraphValidationError, validate_graph_integrity

def _preview(node):
    for item in node["sequence"]:
        if item["type"] == "dialogue":
            return f'{item["speaker"]}: {item["text"]}'
    return ""


def build_graph(ast):
    diagnostics = validate_graph_integrity(ast)
    if any(item["severity"] == "error" for item in diagnostics):
        raise GraphValidationError(diagnostics)
    nodes = []

    for node in ast["nodes"]:
        nodes.append({"id": node["id"],
                      "category": node["metadata"].get("category"),
                      "color": node["metadata"].get("color"),
                      "preview": _preview(node),
                      "metadata": node["metadata"],
                      "dialogue_lines": [{"speaker": i["speaker"], "text": i["text"], "source_line": i["source_line"]} for i in node["sequence"] if i["type"] == "dialogue"],
                      "source_line": node["source_line"],
                      "source_end_line": node["source_end_line"]})

    edges = []
    for node in ast["nodes"]:
        jumps = [i for i in node["sequence"] if i["type"] == "jump"]
        for kind, items in (("jump", jumps), ("choice", node["choices"])):
            for index, item in enumerate(items):
                edges.append({
                    # Deterministic: same Markdown -> same edge IDs, so React Flow
                    # doesn't remount edges on every sync.
                    "id": f'{node["id"]}:{kind}:{index}',
                    "source": node["id"],
                    "target": item["target"],
                    "kind": kind,
                    "label": item.get("text"),
                    "condition": item["condition"],
                    "source_line": item["source_line"],
                })

    return {"snapshot_id": ast["snapshot_id"], "start": nodes[0]["id"] if nodes else None,
            "nodes": nodes, "edges": edges, "diagnostics": diagnostics}
