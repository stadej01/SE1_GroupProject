"""Structural checks for the temporary parser. Expressions are not evaluated."""

class GraphValidationError(ValueError):
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        super().__init__("Markdown contains errors; no graph was generated.")

def validate_graph_integrity(ast):
    diagnostics = list(ast.get("diagnostics", []))
    seen = set()
    for node in ast["nodes"]:
        if node["id"] in seen:
            diagnostics.append({"severity": "error", "line": node["source_line"],
                "node_id": node["id"], "message": f'Duplicate node ID {node["id"]}.'})
        seen.add(node["id"])
    for node in ast["nodes"]:
        jumps = [item for item in node["sequence"] if item["type"] == "jump"]
        for item in [*jumps, *node["choices"]]:
            if item["target"] not in seen:
                diagnostics.append({"severity": "error", "line": item["source_line"],
                    "node_id": node["id"],
                    "message": f'Target node {item["target"]} does not exist in this document.'})
        for choice in node["choices"]:
            if not choice["text"].strip():
                diagnostics.append({"severity": "error", "line": choice["source_line"],
                    "node_id": node["id"], "message": "A choice must have nonblank text."})
    return diagnostics
