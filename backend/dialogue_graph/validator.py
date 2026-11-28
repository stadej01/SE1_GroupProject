import re
import json
"""Structural checks for the temporary parser. Expressions are not evaluated."""

class GraphValidationError(ValueError):
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        super().__init__("Markdown contains errors; no graph was generated.")

def validate_graph_integrity(ast):
    diagnostics = list(ast.get("diagnostics", []))
    # US-34: Validate variable initial values
    for variable in ast.get("variables", []):
        name = variable["name"]
        var_type = variable["type"]
        value = variable["initial_value"]

        valid = False

        if var_type == "integer":
            valid = re.fullmatch(r"[+-]?[0-9]+", value) is not None

        if var_type == "boolean":
            valid = value.lower() in ("true", "false")

        if var_type == "string":
            try:
                valid = isinstance(json.loads(value), str)
            except (json.JSONDecodeError, TypeError):
                valid = False

        if not valid:
            diagnostics.append({
                "severity": "error",
                "line": variable["source_line"],
                "node_id": variable.get("node_id"),
                "message": f"Variable '{name}' has invalid {var_type} value '{value}'."
            })
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
             # US-34 AC5: Validate choice effect types
            for effect in choice.get("effects", []):
                variable = None

                # Find a matching global variable
                for var in ast.get("variables", []):
                    if var["name"] == effect["var"] and var["scope"] == "global":
                        variable = var

                # A matching local variable takes priority
                for var in ast.get("variables", []):
                    if (var["name"] == effect["var"]
                        and var["scope"] == "local"
                        and var.get("node_id") == node["id"]):
                        variable = var

                if variable is None:
                    diagnostics.append({
                        "severity": "error",
                        "line": choice["source_line"],
                        "node_id": node["id"],
                        "message": f"Choice '{choice['text']}' references undeclared variable '{effect['var']}'."
                    })
                    continue

                if effect["op"] == "subtract" and variable["type"] != "integer":
                    diagnostics.append({
                        "severity": "error",
                        "line": choice["source_line"],
                        "node_id": node["id"],
                        "message": (
                            f"Choice '{choice['text']}' cannot subtract from "
                            f"{variable['type']} variable '{effect['var']}'. "
                            f"Effect is on line {effect['source_line']}; "
                            "subtraction requires an integer."
                        )
                    })
    start_nodes = ast.get("start_nodes", [])
    if not start_nodes:
        diagnostics.append({"severity": "warning",
            "message": "Starting nodes have not been allocated. Select one or more starting nodes before validating or playtesting the dialogue."})
    else:
        start_lines = ast.get("start_lines", [])
        for index, start in enumerate(start_nodes):
            if start not in seen:
                line = start_lines[index] if index < len(start_lines) else None
                diagnostics.append({"severity": "error", "line": line,
                    "node_id": start, "message": f"Starting node {start} does not exist in this document."})
    end_nodes = ast.get("end_nodes", [])
    end_lines = ast.get("end_lines", [])
    for index, end in enumerate(end_nodes):
        if end not in seen:
            line = end_lines[index] if index < len(end_lines) else None
            diagnostics.append({"severity": "error", "line": line,
                "node_id": end, "message": f"End node {end} does not exist in this document."})
    return diagnostics

def check_continuity(ast):
    """Return structural and branching issues without blocking graph creation."""
    issues = validate_graph_integrity(ast)
    nodes = ast["nodes"]
    node_ids = {node["id"] for node in nodes}
    end_nodes = set(ast.get("end_nodes", []))
    adjacency = {}

    for node in nodes:
        outgoing = [
            *[item for item in node["sequence"] if item["type"] == "jump"],
            *node["choices"],
        ]
        adjacency[node["id"]] = [
            (item["target"], item.get("source_line"))
            for item in outgoing
            if item["target"] in node_ids
        ]

        if outgoing and node["id"] in end_nodes:
            issues.append({
                "severity": "warning",
                "line": node["source_end_line"],
                "node_id": node["id"],
                "message": f'Node {node["id"]} is marked as an end node but still has outgoing choices or jumps.',
            })
        elif not outgoing and node["id"] not in end_nodes:
            issues.append({
                "severity": "warning",
                "line": node["source_end_line"],
                "node_id": node["id"],
                "message": (
                    f'Node {node["id"]} has no outgoing choices or jumps and '
                    "is not marked as an end node."
                ),
            })

        if outgoing and all(item.get("condition") for item in outgoing):
            issues.append({
                "severity": "warning",
                "line": node["source_line"],
                "node_id": node["id"],
                "message": (
                    f'Node {node["id"]} has only conditional exits and no '
                    "unconditional fallback. Some logic states may have no route."
                ),
            })

    state = {}
    cycle_keys = set()
    for start in (node["id"] for node in nodes):
        if state.get(start, 0):
            continue

        state[start] = 1
        path = [start]
        active_index = {start: 0}
        stack = [(start, 0)]

        while stack:
            node_id, edge_index = stack[-1]
            edges = adjacency.get(node_id, [])
            if edge_index == len(edges):
                stack.pop()
                path.pop()
                active_index.pop(node_id, None)
                state[node_id] = 2
                continue

            target, source_line = edges[edge_index]
            stack[-1] = (node_id, edge_index + 1)
            target_state = state.get(target, 0)
            if target_state == 0:
                state[target] = 1
                active_index[target] = len(path)
                path.append(target)
                stack.append((target, 0))
            elif target_state == 1:
                cycle = path[active_index[target]:]
                cycle_key = min(
                    tuple(cycle[index:] + cycle[:index])
                    for index in range(len(cycle))
                )
                if cycle_key not in cycle_keys:
                    cycle_keys.add(cycle_key)
                    issues.append({
                        "severity": "warning",
                        "line": source_line,
                        "node_id": target,
                        "message": f'Loop detected: {" -> ".join([*cycle, target])}.',
                    })

    return {"status": "clean" if not issues else "issues", "issues": issues}
