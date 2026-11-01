"""python -m dialogue_graph path/to/file.md; invalid input produces no stdout."""
import argparse
import json
import sys
from pathlib import Path

from . import GraphValidationError, build_graph, parse_markdown_to_ast

def main():
    parser = argparse.ArgumentParser(description="Convert valid demo Markdown to graph JSON.")
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    try:
        graph = build_graph(parse_markdown_to_ast(args.source.read_text(encoding="utf-8")))
    except GraphValidationError as exc:
        print(json.dumps({"diagnostics": exc.diagnostics}, indent=2), file=sys.stderr)
        return 1
    except (OSError, UnicodeError) as exc:
        parser.exit(2, f"Cannot read Markdown: {exc}\n")
    print(json.dumps(graph, indent=2))
    return 0

if __name__ == "__main__":
    sys.exit(main())
