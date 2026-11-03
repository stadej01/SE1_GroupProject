import json
import unittest
from pathlib import Path

from dialogue_graph import GraphValidationError, build_graph, parse_markdown_to_ast

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def graph_for(md):
    return build_graph(parse_markdown_to_ast(md))


class MerchantFixture(unittest.TestCase):
    def setUp(self):
        self.graph = graph_for((FIXTURES / "merchant.md").read_text(encoding="utf-8"))
        self.edges = {edge["id"]: edge for edge in self.graph["edges"]}

    def test_parses_cleanly(self):
        self.assertEqual(self.graph["diagnostics"], [])

    def test_greeting_has_jump_and_choice_edges(self):  # US-29 AC1 input
        out = [edge for edge in self.graph["edges"] if edge["source"] == "Node_Merchant_Greeting"]
        self.assertEqual([edge["kind"] for edge in out], ["jump"] + ["choice"] * 4)

    def test_jump_keeps_condition_and_target(self):
        jump = self.edges["Node_Merchant_Greeting:jump:0"]
        self.assertEqual(jump["target"], "Node_Merchant_Annoyed")
        self.assertEqual(jump["condition"], "talk_count > 5")

    def test_choice_keeps_text_condition_and_target(self):
        choice = self.edges["Node_Merchant_Greeting:choice:0"]
        self.assertEqual(choice["label"], "I'll buy the enchanted dagger (50 Gold).")
        self.assertEqual(choice["condition"], "gold >= 50")
        self.assertEqual(choice["target"], "Node_Buy_Dagger")

    def test_unconditional_choice_has_no_condition(self):
        self.assertIsNone(self.edges["Node_Merchant_Greeting:choice:3"]["condition"])

    def test_metadata_read_and_review_comment_ignored(self):
        greeting = self.graph["nodes"][0]
        self.assertEqual((greeting["category"], greeting["color"]), ("shop", "blue"))
        self.assertTrue(greeting["preview"].startswith("Merchant: Ah, welcome back"))

    def test_loops_are_preserved_as_edges(self):  # US-29 AC2 input
        self.assertEqual(self.edges["Node_Hand_In_Quest:jump:0"]["target"], "Node_Merchant_Greeting")
        self.assertEqual(self.edges["Node_Browse_Shop:choice:1"]["target"], "Node_Browse_Shop")

    def test_jump_at_end_of_node_is_marked(self):
        self.assertTrue(self.edges["Node_Merchant_Annoyed:jump:0"]["ends_node"])
        self.assertTrue(self.edges["Node_Hand_In_Quest:jump:0"]["ends_node"])

    def test_mid_dialogue_jump_is_not_marked(self):
        self.assertFalse(self.edges["Node_Merchant_Greeting:jump:0"]["ends_node"])

    def test_choices_never_marked(self):
        self.assertFalse(any(edge["ends_node"] for edge in self.graph["edges"] if edge["kind"] == "choice"))

    def test_matches_checked_in_contract(self):
        """Compare existing JSON contract fields while allowing newer node metadata."""
        expected = json.loads((FIXTURES / "merchant.graph.json").read_text(encoding="utf-8"))
        self.assertEqual(len(self.graph["nodes"]), len(expected["nodes"]))
        for key, value in expected.items():
            if key != "nodes":
                self.assertEqual(self.graph[key], value)
        for actual_node, expected_node in zip(self.graph["nodes"], expected["nodes"]):
            for key, value in expected_node.items():
                self.assertEqual(actual_node[key], value)


class EdgeCases(unittest.TestCase):
    def test_missing_target_blocks_graph(self):
        with self.assertRaises(GraphValidationError) as caught:
            graph_for('# A\n* "Go" -> Nowhere\n')
        self.assertIn("does not exist", caught.exception.diagnostics[0]["message"])

    def test_unconditional_jump(self):
        g = graph_for("# A\n<<jump: B>>\n# B\n")
        self.assertEqual((g["edges"][0]["kind"], g["edges"][0]["condition"]), ("jump", None))

    def test_unknown_line_reports_line_number(self):
        with self.assertRaises(GraphValidationError) as caught:
            graph_for("# A\n??? what\n")
        self.assertEqual(caught.exception.diagnostics[0]["line"], 2)

    def test_duplicate_ids_reported(self):
        with self.assertRaises(GraphValidationError) as caught:
            graph_for("# A\n# A\n")
        self.assertIn("Duplicate", caught.exception.diagnostics[0]["message"])

    def test_empty_script_and_blank_choices_block_graph(self):
        for source in ["", " \n\n", '# A\n* " " -> A\n']:
            with self.subTest(source=source), self.assertRaises(GraphValidationError):
                graph_for(source)

    def test_source_spans_cover_exact_sections(self):
        source = "# A\r\nNarrator: Hello.\r\n\r\n# B\r\nNarrator: Goodbye."
        nodes = graph_for(source)["nodes"]
        self.assertEqual([(n["source_line"], n["source_end_line"]) for n in nodes], [(1, 3), (4, 5)])

    def test_text_only_edit_changes_snapshot_but_not_edge_ids(self):
        source = '# A\nNarrator: Hello.\n* "Go" -> A'
        before, after = graph_for(source), graph_for(source.replace("Hello.", "Goodbye."))
        self.assertNotEqual(before["snapshot_id"], after["snapshot_id"])
        self.assertEqual(before["edges"], after["edges"])
        self.assertEqual(graph_for(source)["snapshot_id"], before["snapshot_id"])

    def test_sequence_order_and_expressions_are_preserved_without_execution(self):
        ast = parse_markdown_to_ast('# A\nNarrator: Hello\n[set: coins = coins - 5]\n[if coins > 0] <<jump: A>>\nNarrator: Goodbye')
        items = ast["nodes"][0]["sequence"]
        self.assertEqual([item["type"] for item in items], ["dialogue", "mutation", "jump", "dialogue"])
        self.assertEqual(items[1]["expr"], "coins - 5")
        self.assertEqual(items[2]["condition"], "coins > 0")


if __name__ == "__main__":
    unittest.main()
