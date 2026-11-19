import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.conf import settings
from .models import Draft
from .assets import frontend_assets


VALID = '# A\nNarrator: Hello.\n* "Go" -> B\n# B\nNarrator: Goodbye.'

class EditorTests(TestCase):
    @override_settings(CSRF_COOKIE_NAME="custom_demo_csrf")
    def test_editor_uses_configured_csrf_cookie_without_project_login_url(self):
        response = self.client.get(reverse("editor:index"))
        self.assertContains(response, 'data-csrf-cookie="custom_demo_csrf"')
        self.assertNotContains(response, 'data-login-url=')

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        
        response = self.client.get(reverse("editor:index"))
        self.assertEqual(response.status_code, 200)
        # Retrieve the CSRF token for authenticated requests.
        self.token = self.client.cookies[settings.CSRF_COOKIE_NAME].value

    def post_sync(self, source):
        return self.client.post(reverse("editor:sync"), {"markdown_source": source},
            content_type="application/json", HTTP_X_CSRFTOKEN=self.token)

    def save_draft(self, source, revision=0):
        return self.client.put(reverse("editor:save"),
            {"markdown_source": source, "revision": revision}, content_type="application/json",
            HTTP_X_CSRFTOKEN=self.token)

    def test_django_template_and_built_assets(self):
        response = self.client.get(reverse("editor:index"))
        self.assertTemplateUsed(response, "editor/index.html")
        self.assertContains(response, 'id="markdown-source"')
        assets = frontend_assets()
        if assets:
            self.assertContains(response, f'src="{assets["script"]}"')
        else:
            self.assertContains(response, "Frontend assets are missing")
        self.assertNotContains(response, "localhost:5173")
        self.assertContains(response, 'data-sync-url="/sync"')
        self.assertContains(response, 'data-save-url="/save"')

    def test_demo_keeps_save_draft_without_project_navigation(self):
        response = self.client.get(reverse("editor:index"))
        self.assertContains(response, ">Save draft</button>")
        self.assertContains(response, "<h1>Dialogue editor</h1>")
        self.assertNotContains(response, 'id="back-to-projects"')
        self.assertNotContains(response, 'id="leave-dialog"')
        self.assertNotContains(response, 'id="logout-form"')

    def test_missing_manifest_or_script_shows_build_hint(self):
        with TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(json.dumps({"src/main.tsx": {"file": "assets/missing.js"}}))
            for files in ([None], [str(manifest), None]):
                with self.subTest(files=files), patch("editor.assets.finders.find", side_effect=files):
                    response = self.client.get(reverse("editor:index"))
                self.assertContains(response, "Frontend assets are missing")
                self.assertNotContains(response, 'type="module"')

    def test_sync_returns_valid_graph_without_saving(self):
        original = Draft.objects.get().markdown_source
        result = self.post_sync(VALID)
        self.assertEqual(result.status_code, 200)
        graph = result.json()["graph"]
        self.assertEqual([node["id"] for node in graph["nodes"]], ["A", "B"])
        self.assertEqual(graph["edges"][0]["target"], "B")
        self.assertEqual(Draft.objects.get().markdown_source, original)

    def test_all_invalid_inputs_return_diagnostics_without_graph(self):
        for source in ["", "# A\n???", "# A\n# A", '# A\n* "Go" -> Missing']:
            with self.subTest(source=source):
                response = self.post_sync(source)
                self.assertEqual(response.status_code, 422)
                self.assertNotIn("graph", response.json())
                self.assertNotIn("nodes", response.json())
                self.assertTrue(response.json()["diagnostics"])

    def test_invalid_draft_saves_exactly_and_reloads(self):
        source = '# A\r\nTHIS IS NOT VALID\n'
        self.assertEqual(self.save_draft(source).status_code, 200)
        self.assertEqual(Draft.objects.get().markdown_source, source)
        self.assertEqual(self.client.get("/").context["markdown_source"], source)
        self.assertEqual(self.post_sync(source).status_code, 422)

    def test_empty_draft_is_saved(self):
        self.assertEqual(self.save_draft("").status_code, 200)
        self.assertEqual(Draft.objects.get().markdown_source, "")

    def test_two_tabs_cannot_overwrite_newer_save(self):
        self.assertEqual(self.save_draft("first").json()["revision"], 1)
        self.assertEqual(self.save_draft("stale", 0).status_code, 409)
        self.assertEqual(Draft.objects.get().markdown_source, "first")
        self.assertEqual(self.save_draft("second", 1).status_code, 200)

    def test_drafts_are_isolated_by_session(self):
        self.save_draft("private draft")
        other = Client()
        response = other.get("/")
        self.assertNotEqual(response.context["markdown_source"], "private draft")
        self.assertEqual(Draft.objects.count(), 2)

    def test_csrf_required_on_sync_and_save(self):
        for url, method in [("/sync", self.client.post), ("/save", self.client.put)]:
            response = method(url, {"markdown_source": VALID, "revision": 0}, content_type="application/json")
            self.assertEqual(response.status_code, 403)
            self.assertFalse(response.json()["ok"])

    def test_payload_shape_and_malformed_json(self):
        for body in ["{", "[]", "null", '{"markdown_source": 123}']:
            response = self.client.post("/sync", body, content_type="application/json", HTTP_X_CSRFTOKEN=self.token)
            self.assertEqual(response.status_code, 400)

    def test_content_type_and_size_limits(self):
        response = self.client.post("/sync", VALID, content_type="text/plain", HTTP_X_CSRFTOKEN=self.token)
        self.assertEqual(response.status_code, 415)
        self.assertEqual(self.post_sync("x" * 200_001).status_code, 413)

    def test_unpaired_surrogates_are_reported_instead_of_crashing(self):
        self.assertEqual(self.post_sync("# A\nNarrator: \ud800").status_code, 400)

    def test_wrong_methods(self):
        self.assertEqual(self.client.get("/sync").status_code, 405)
        self.assertEqual(self.client.get("/save").status_code, 405)

    def test_textarea_cannot_be_closed_by_saved_markdown(self):
        source = '</textarea><script>window.injected=true</script>'
        self.save_draft(source)
        response = self.client.get("/")
        self.assertNotContains(response, source)
        self.assertContains(response, "&lt;/textarea&gt;&lt;script&gt;")
