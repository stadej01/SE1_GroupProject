import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from dialogue_graph import (
    SCHEMA_VERSION,
    GraphValidationError,
    compile_to_json,
    error_log,
    parse_markdown_to_ast,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def compile_markdown(md):
    return compile_to_json(parse_markdown_to_ast(md))


def compile_errors(md):
    ast = parse_markdown_to_ast(md)
    try:
        compile_to_json(ast)
    except GraphValidationError as failure:
        return ast, failure.diagnostics
    raise AssertionError("Expected compilation to fail.")


class MerchantExport(unittest.TestCase):
    """US-25 AC1: a valid script compiles to JSON that keeps its narrative data."""

    def setUp(self):
        markdown = (FIXTURES / "merchant.md").read_text(encoding="utf-8")
        self.export, self.warnings = compile_markdown(markdown)
        self.nodes = {node["id"]: node for node in self.export["nodes"]}

    def test_has_schema_version_snapshot_and_start(self):
        self.assertEqual(self.export["schema_version"], SCHEMA_VERSION)
        self.assertEqual(len(self.export["snapshot_id"]), 64)
        self.assertEqual(self.export["start_nodes"], ["Node_Merchant_Greeting"])
        self.assertEqual(self.warnings, [])

    def test_keeps_every_unique_node_id_in_written_order(self):
        self.assertEqual(
            [node["id"] for node in self.export["nodes"]],
            [
                "Node_Merchant_Greeting",
                "Node_Merchant_Annoyed",
                "Node_Buy_Dagger",
                "Node_Hand_In_Quest",
                "Node_Browse_Shop",
                "Node_Exit",
            ],
        )

    def test_keeps_dialogue_blocks_with_speaker_and_line_id(self):
        dialogue = [
            item for item in self.nodes["Node_Merchant_Greeting"]["sequence"]
            if item["type"] == "dialogue"
        ]
        self.assertEqual(
            dialogue[0],
            {
                "type": "dialogue",
                "speaker": "Merchant",
                "text": "Ah, welcome back, traveler!",
                "line_id": "dlg_mrc_001",
            },
        )
        self.assertEqual(len(dialogue), 3)

    def test_keeps_dialogue_jumps_and_mutations_interleaved(self):
        kinds = [item["type"] for item in self.nodes["Node_Merchant_Greeting"]["sequence"]]
        self.assertEqual(
            kinds, ["dialogue", "mutation", "mutation", "dialogue", "jump", "dialogue"]
        )

    def test_keeps_jump_destination_and_condition(self):
        jump = self.nodes["Node_Merchant_Greeting"]["sequence"][4]
        self.assertEqual(
            jump,
            {"type": "jump", "target": "Node_Merchant_Annoyed", "condition": "talk_count > 5"},
        )

    def test_keeps_choices_with_text_condition_and_destination(self):
        choices = self.nodes["Node_Merchant_Greeting"]["choices"]
        self.assertEqual(len(choices), 4)
        self.assertEqual(
            choices[0],
            {
                "text": "I'll buy the enchanted dagger (50 Gold).",
                "target": "Node_Buy_Dagger",
                "condition": "gold >= 50",
                "line_id": "chc_mrc_001",
            },
        )
        self.assertIsNone(choices[2]["condition"])

    def test_every_destination_is_an_exported_node(self):
        for node in self.export["nodes"]:
            jumps = [item for item in node["sequence"] if item["type"] == "jump"]
            for item in [*jumps, *node["choices"]]:
                self.assertIn(item["target"], self.nodes)

    def test_leaves_out_editor_only_data(self):
        text = json.dumps(self.export)
        self.assertNotIn("source_line", text)
        self.assertNotIn("REVIEW", text)
        self.assertNotIn("diagnostics", self.export)

    def test_export_is_plain_json(self):
        self.assertEqual(json.loads(json.dumps(self.export)), self.export)


class ExportWarnings(unittest.TestCase):
    def test_missing_start_node_is_a_warning_not_a_failure(self):
        export, warnings = compile_markdown("# Node_A\nNarrator: Hello.\n")

        self.assertEqual([node["id"] for node in export["nodes"]], ["Node_A"])
        self.assertEqual([item["severity"] for item in warnings], ["warning"])


class BrokenScriptExport(unittest.TestCase):
    """US-25 AC2: a broken script does not compile and reports why."""

    def test_unrecognized_syntax_fails_with_its_line_and_node(self):
        _, diagnostics = compile_errors(
            "<!-- start: Node_A -->\n# Node_A\nNarrator: Hello.\n* \"Unclosed -> Node_A\n"
        )

        error = next(item for item in diagnostics if item["severity"] == "error")
        self.assertEqual(error["line"], 4)
        self.assertEqual(error["node_id"], "Node_A")
        self.assertIn("Unrecognized line", error["message"])

    def test_content_before_the_first_header_fails(self):
        _, diagnostics = compile_errors("Narrator: Too early.\n# Node_A\nNarrator: Hi.\n")

        self.assertEqual(diagnostics[0]["line"], 1)

    def test_empty_script_fails(self):
        _, diagnostics = compile_errors("")

        self.assertIn("header", diagnostics[0]["message"])

    def test_missing_destination_fails(self):
        _, diagnostics = compile_errors(
            "<!-- start: Node_A -->\n# Node_A\nNarrator: Hi.\n<<jump: Node_Missing>>\n"
        )

        self.assertTrue(any("Node_Missing" in item["message"] for item in diagnostics))

    def test_error_log_has_message_time_stamp_and_source(self):
        ast, diagnostics = compile_errors("# Node_A\nthis is not dialogue\n")
        when = datetime(2026, 11, 10, 21, 30, tzinfo=timezone.utc)

        log = error_log(diagnostics, ast["snapshot_id"], detected_at=when)

        self.assertFalse(log["ok"])
        self.assertEqual(log["detected_at"], "2026-11-10T21:30:00Z")
        self.assertEqual(log["snapshot_id"], ast["snapshot_id"])
        entry = log["diagnostics"][0]
        self.assertEqual(entry["severity"], "error")
        self.assertIn("Unrecognized line", entry["message"])
        self.assertEqual(entry["detected_at"], "2026-11-10T21:30:00Z")
        self.assertEqual((entry["line"], entry["node_id"]), (2, "Node_A"))
        self.assertEqual(entry["snapshot_id"], ast["snapshot_id"])

    def test_error_log_without_a_line_still_lists_the_message(self):
        log = error_log([{"severity": "error", "message": "Broken."}], "abc")

        self.assertEqual(log["diagnostics"][0]["line"], None)
        self.assertTrue(log["detected_at"].endswith("Z"))


if __name__ == "__main__":
    unittest.main()
