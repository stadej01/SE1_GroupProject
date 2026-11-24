import json
"""Compile a validated AST into the JSON export.

The export holds narrative data only. Editor data such as source line numbers,
node positions, and review comments is left out.
"""

from datetime import datetime, timezone

from .validator import GraphValidationError, validate_graph_integrity

SCHEMA_VERSION = "1.0"

def _sequence_item(item, variables, node_id):
    """Copy one dialogue line, jump, or mutation without its editor-only line number."""

    if item["type"] == "dialogue":
        return {
            "type": "dialogue",
            "speaker": item["speaker"],
            "text": item["text"],
            "line_id": item["line_id"]
        }

    if item["type"] == "jump":
        return {
            "type": "jump",
            "target": item["target"],
            "condition": item["condition"]
        }

    if item["type"] == "mutation":
        result = {
            "type": "mutation",
            "op": item["op"],
            "var": item["var"],
            "expr": item["expr"]
        }

        scope = None

        for variable in variables:
            if variable["name"] != item["var"]:
                continue

            if variable["scope"] == "global":
                scope = "global"

            if variable["scope"] == "local" and variable.get("node_id") == node_id:
                scope = "local"
                break

        if scope is not None:
            result["scope"] = scope

        return result
    raise ValueError(f'Unknown sequence item type {item["type"]!r}.')


def _choice(choice):
    return {
        "text": choice["text"], 
        "target": choice["target"],
        "condition": choice["condition"], 
        "line_id": choice["line_id"]
    }

def _variable(variable):
    raw = variable["initial_value"]

    if variable["type"] == "boolean":
        value = raw.lower() == "true"
    elif variable["type"] == "integer":
        value = int(raw)
    elif variable["type"] == "string":
        value = json.loads(raw)
    else:
        value = raw

    result = {
        "name": variable["name"],
        "type": variable["type"],
        "scope": variable["scope"],
        "initial_value": value
    }

    if variable["scope"] == "local":
        result["node_id"] = variable["node_id"]

    return result

def compile_to_json(ast):
    """Return the export for a valid AST.

    Raises GraphValidationError with every diagnostic when any of them is an
    error. Warnings do not block the export.
    """
    diagnostics = validate_graph_integrity(ast)
    if any(item["severity"] == "error" for item in diagnostics):
        raise GraphValidationError(diagnostics)

    export = {
        "schema_version": SCHEMA_VERSION,
        "snapshot_id": ast["snapshot_id"],
        "start_nodes": list(ast.get("start_nodes", [])),
        "variables": [_variable(var) for var in ast.get("variables", [])],
        "nodes": [
            {
                "id": node["id"],
                "metadata": dict(node["metadata"]),
                "sequence": [
                    _sequence_item(item, ast.get("variables", []), node["id"])
                    for item in node["sequence"]
                    ],
                "choices": [_choice(choice) for choice in node["choices"]],
            }
            for node in ast["nodes"]
        ],
    }
    warnings = [item for item in diagnostics if item["severity"] == "warning"]
    return export, warnings


def error_log(diagnostics, snapshot_id, detected_at=None):
    """Build the failed-export report: message, time stamp, and source of each failure.

    Every entry keeps the parser's message, severity, line, and node_id, and gains
    the time of the export attempt and the Markdown snapshot that was checked.
    """
    detected_at = detected_at or datetime.now(timezone.utc)
    stamp = detected_at.isoformat().replace("+00:00", "Z")
    return {
        "ok": False,
        "detected_at": stamp,
        "snapshot_id": snapshot_id,
        "diagnostics": [
            {
                "severity": item["severity"],
                "message": item["message"],
                "line": item.get("line"),
                "node_id": item.get("node_id"),
                "snapshot_id": snapshot_id,
                "detected_at": stamp,
            }
            for item in diagnostics
        ],
    }
