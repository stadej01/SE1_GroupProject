import unittest
import django
from types import SimpleNamespace

django.setup()

from projects.views import export_response


class US34ExportBlocking(unittest.TestCase):

    def test_invalid_variable_blocks_download(self):
        md = """<!-- start: Node_A -->
[var: global integer coins = ten]
# Node_A
Narrator: Hello!
"""
        project = SimpleNamespace(name="Test Dialogue")

        response = export_response(project, md)

        self.assertEqual(response.status_code, 422)
        self.assertNotIn("Content-Disposition", response)

        self.assertTrue(
            any(
                "coins" in error["message"]
                for error in response.data["diagnostics"]
            )
        )
    def test_invalid_choice_effect_blocks_download(self):
        md = """<!-- start: Node_A -->
[var: global boolean has_key = false]
# Node_A
* "Use key" -> Node_B
[effect: has_key -= 5]
# Node_B
Narrator: Goodbye!
"""
        project = SimpleNamespace(name="Test Dialogue")

        response = export_response(project, md)

        self.assertEqual(response.status_code, 422)
        self.assertNotIn("Content-Disposition", response)

        self.assertTrue(
            any(
                "has_key" in error["message"]
                and "Use key" in error["message"]
                for error in response.data["diagnostics"]
            )
        )