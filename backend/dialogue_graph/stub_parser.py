"""Stand-in for LarkParser.parse_markdown_to_ast (design doc 4.2, interface 1).

Line-based and stdlib-only so US-29 can be built and tested before the Lark
parser lands. It returns the same AST dict shape the Lark Transformer should
produce; when that's ready, swap the import in __init__.py and keep graph.py.
"""
import hashlib
import re

HEADER = re.compile(r"^#\s+(?P<id>\w+)\s*$")
COMMENT_ONLY = re.compile(r"^<!--(?P<body>.*?)-->\s*$")
META_PAIR = re.compile(r"^\s*(?P<k>[a-z_]+)\s*:\s*(?P<v>[\w-]+)\s*$")
FIELD = re.compile(r"^@(?P<key>[a-z_][a-z_0-9]*)\s*:\s*(?P<value>.*)$")
LINE_ID = re.compile(r"\s*<!--\s*#line:(?P<id>[\w-]+)\s*-->\s*$")
CONDITION = r"(?:\[if\s+(?P<cond>[^\]]+?)\]\s*)?"
CHOICE = re.compile(r'^\*\s*' + CONDITION + r'"(?P<text>[^"]*)"\s*->\s*(?P<target>\w+)\s*$')
JUMP = re.compile(r"^" + CONDITION + r"<<jump:\s*(?P<target>\w+)\s*>>\s*$")
SET = re.compile(r"^\[set:\s*(?P<var>\w+)\s*=\s*(?P<expr>[^\]]+?)\s*\]\s*$")
DIALOGUE = re.compile(r"^(?P<speaker>\w[\w ]*?):\s+(?P<text>.+)$")


def _metadata(body):
    """`category: shop, color: blue` -> dict. Anything else (e.g. REVIEW notes) -> None."""
    pairs = [META_PAIR.match(part) for part in body.split(",")]
    if not all(pairs):
        return None
    return {m["k"]: m["v"] for m in pairs}


def parse_markdown_to_ast(markdown_source):
    nodes, diagnostics = [], []
    current = None

    # Match browser textarea newlines; splitlines() also splits Unicode separators.
    lines = markdown_source.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue

        if m := HEADER.match(line):
            if current is not None:
                current["source_end_line"] = lineno - 1
            current = {"id": m["id"], "metadata": {}, "sequence": [], "choices": [],
                       "source_line": lineno, "source_end_line": lineno}
            nodes.append(current)
            continue

        if current is None:
            diagnostics.append({"severity": "error", "line": lineno,
                                "message": "Content before the first '# Node_' header."})
            continue

        if m := FIELD.match(line):
            current["metadata"][m["key"]] = m["value"]
            continue

        if m := COMMENT_ONLY.match(line):
            meta = _metadata(m["body"])
            if meta is not None:
                current["metadata"].update(meta)
            continue  # other comments (REVIEW notes) are not narrative content

        line_id = None
        if m := LINE_ID.search(line):
            line_id = m["id"]
            line = line[: m.start()].rstrip()

        if m := CHOICE.match(line):
            current["choices"].append({"text": m["text"], "target": m["target"],
                                       "condition": m["cond"], "line_id": line_id,
                                       "source_line": lineno})
        elif m := JUMP.match(line):
            current["sequence"].append({"type": "jump", "target": m["target"],
                                        "condition": m["cond"], "source_line": lineno})
        elif m := SET.match(line):
            current["sequence"].append({"type": "mutation", "op": "set", "var": m["var"],
                                        "expr": m["expr"], "source_line": lineno})
        elif m := DIALOGUE.match(line):
            current["sequence"].append({"type": "dialogue", "speaker": m["speaker"],
                                        "text": m["text"], "line_id": line_id,
                                        "source_line": lineno})
        else:
            diagnostics.append({"severity": "error", "line": lineno, "node_id": current["id"],
                                "message": f"Unrecognized line: {raw.strip()!r}"})

    if current is not None:
        current["source_end_line"] = len(lines)
    if not nodes:
        diagnostics.append({"severity": "error", "line": 1,
                            "message": "Add at least one '# Node_ID' header."})
    return {"nodes": nodes, "diagnostics": diagnostics,
            "snapshot_id": hashlib.sha256(markdown_source.encode("utf-8")).hexdigest()}
