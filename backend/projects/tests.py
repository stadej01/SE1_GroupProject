import base64
import io
import json
from unittest import mock
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlsplit

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from teams.models import Team, TeamMembership

from .models import NodePosition, Project
from .services import save_project
from .storage import (
    ContentStoreError,
    GitHubContentStore,
    InMemoryContentStore,
    get_content_store,
)
from .views import get_member_project

# Create your tests here.


class FakeGitHub:
    """Answers GitHub contents API requests for one branch, keeping every commit."""

    def __init__(self, branch="main"):
        self.branch = branch
        self.commits = {}
        self.branch_files = {}
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        url = urlsplit(request.full_url)
        path = unquote(url.path.partition("/contents/")[2])
        ref = parse_qs(url.query).get("ref", [None])[0]

        if request.get_method() == "PUT":
            body = json.loads(request.data)
            if body.get("sha") != self.branch_files.get(path):
                raise HTTPError(request.full_url, 409, "Conflict", None, None)
            commit_sha = f"{len(self.commits) + 1:040x}"
            self.commits[commit_sha] = (path, base64.b64decode(body["content"]))
            self.branch_files[path] = f"blob-{commit_sha}"
            return io.BytesIO(json.dumps({"commit": {"sha": commit_sha}}).encode())

        if ref == self.branch and path in self.branch_files:
            return io.BytesIO(json.dumps({"sha": self.branch_files[path]}).encode())
        stored = self.commits.get(ref)
        if stored is None or stored[0] != path:
            raise HTTPError(request.full_url, 404, "Not Found", None, None)
        return io.BytesIO(stored[1])

    def puts(self):
        return [json.loads(r.data) for r in self.requests if r.get_method() == "PUT"]


class GitHubContentStoreTests(SimpleTestCase):
    PATH = "projects/act-1.md"

    def setUp(self):
        self.github = FakeGitHub()
        patcher = mock.patch("projects.storage.urlopen", side_effect=self.github)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.store = GitHubContentStore("team6/dialogue-content", "test-token")

    def test_first_write_creates_the_file_and_returns_its_commit(self):
        sha = self.store.write(self.PATH, "# Node_1\nHello!\n", "Save Act 1")

        self.assertEqual(self.store.read(self.PATH, sha), "# Node_1\nHello!\n")
        put = next(r for r in self.github.requests if r.get_method() == "PUT")
        self.assertEqual(
            put.full_url,
            "https://api.github.com/repos/team6/dialogue-content/contents/"
            "projects/act-1.md",
        )
        self.assertEqual(put.get_header("Authorization"), "Bearer test-token")
        body = json.loads(put.data)
        self.assertEqual(body["message"], "Save Act 1")
        self.assertEqual(body["branch"], "main")
        self.assertNotIn("sha", body)

    def test_later_write_replaces_the_file_and_keeps_earlier_versions(self):
        first = self.store.write(self.PATH, "# Node_1\nFirst.\n", "Save 1")

        second = self.store.write(self.PATH, "# Node_1\nSecond.\n", "Save 2")

        self.assertEqual(self.github.puts()[1]["sha"], f"blob-{first}")
        self.assertEqual(self.store.read(self.PATH, first), "# Node_1\nFirst.\n")
        self.assertEqual(self.store.read(self.PATH, second), "# Node_1\nSecond.\n")

    def test_unknown_commit_raises_content_store_error(self):
        with self.assertRaises(ContentStoreError):
            self.store.read(self.PATH, "0" * 40)

    def test_github_failures_raise_content_store_error(self):
        url = "https://api.github.com/repos/team6/dialogue-content/contents/x.md"
        failures = {
            "unauthorized": HTTPError(url, 401, "Unauthorized", None, None),
            "conflict": HTTPError(url, 409, "Conflict", None, None),
            "unreachable": URLError("Name or service not known"),
            "timeout": TimeoutError("timed out"),
        }
        for case, failure in failures.items():
            with (
                self.subTest(case=case),
                mock.patch("projects.storage.urlopen", side_effect=failure),
            ):
                with self.assertRaises(ContentStoreError):
                    self.store.write(self.PATH, "# Node_1\n", "Save")
                with self.assertRaises(ContentStoreError):
                    self.store.read(self.PATH, "a" * 40)


class ContentStoreSettingsTests(SimpleTestCase):
    def test_repository_setting_chooses_the_store(self):
        with self.settings(
            GITHUB_REPOSITORY="team6/dialogue-content",
            GITHUB_TOKEN="test-token",
            GITHUB_BRANCH="drafts",
        ):
            store = get_content_store()

        self.assertIsInstance(store, GitHubContentStore)
        self.assertEqual(store.repository, "team6/dialogue-content")
        self.assertEqual(store.branch, "drafts")
        with self.settings(GITHUB_REPOSITORY=""):
            self.assertIsInstance(get_content_store(), InMemoryContentStore)


class ProjectAPITestCase(APITestCase):
    def setUp(self):
        self.store = InMemoryContentStore()
        patcher = mock.patch(
            "projects.views.get_content_store", return_value=self.store
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        users = get_user_model().objects
        self.member = users.create_user(
            email="designer@example.com", display_name="Designer"
        )
        self.outsider = users.create_user(
            email="outsider@example.com", display_name="Outsider"
        )
        self.team = Team.objects.create(name="Team 6")
        TeamMembership.objects.create(team=self.team, user=self.member)
        self.client.force_authenticate(self.member)

    def post_project(self, name="Act 1 Dialogue"):
        return self.client.post(
            reverse("project-create"),
            {"name": name, "team_id": self.team.pk},
            format="json",
        )

    def create_project(self):
        response = self.post_project()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.json()["project_id"]

    def open_project(self, project_id):
        return self.client.get(reverse("project-detail", args=[project_id]))

    def save_project(self, project_id, markdown, nodes=(), base_revision=1):
        return self.client.put(
            reverse("project-save", args=[project_id]),
            {
                "markdown_source": markdown,
                "layout_data": {"nodes": list(nodes)},
                "base_revision": base_revision,
            },
            format="json",
        )


class CreateProjectTests(ProjectAPITestCase):
    def test_member_creates_an_empty_project(self):
        response = self.post_project()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()
        self.assertEqual(body["name"], "Act 1 Dialogue")
        self.assertEqual(body["markdown_source"], "")
        self.assertEqual(body["revision"], 1)
        project = Project.objects.get(pk=body["project_id"])
        self.assertEqual(project.team, self.team)
        self.assertEqual(project.github_path, f"projects/{project.pk}.md")
        self.assertEqual(project.head_commit_sha, "")

    def test_unauthenticated_request_returns_401(self):
        self.client.force_authenticate(user=None)

        response = self.post_project()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Project.objects.exists())

    def test_non_member_returns_403(self):
        self.client.force_authenticate(self.outsider)

        response = self.post_project()

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Project.objects.exists())

    def test_blank_name_returns_422(self):
        response = self.post_project(name="   ")

        self.assertEqual(response.status_code, status.HTTP_422_UNPROCESSABLE_ENTITY)
        self.assertFalse(Project.objects.exists())


class OpenProjectTests(ProjectAPITestCase):
    def test_new_project_opens_as_an_empty_workspace(self):
        project_id = self.create_project()

        response = self.open_project(project_id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["team_id"], self.team.pk)
        self.assertEqual(body["markdown_source"], "")
        self.assertEqual(body["revision"], 1)
        self.assertEqual(body["layout_data"], {"nodes": []})

    def test_unknown_project_returns_404(self):
        response = self.open_project("00000000-0000-0000-0000-000000000000")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_non_member_cannot_open_the_project(self):
        project_id = self.create_project()
        self.client.force_authenticate(self.outsider)

        response = self.open_project(project_id)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn("markdown_source", response.json())

    def test_unauthenticated_request_returns_401(self):
        project_id = self.create_project()
        self.client.force_authenticate(user=None)

        response = self.open_project(project_id)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_open_keeps_its_snapshot_when_a_save_happens_during_content_read(self):
        project_id = self.create_project()
        original_markdown = "# Node_1\nOriginal.\n"
        original_nodes = [{"id": "Node_1", "position": {"x": 120, "y": 300}}]
        self.save_project(project_id, original_markdown, original_nodes)
        saved_project = Project.objects.get(pk=project_id)
        original_read = self.store.read

        def read_with_concurrent_save(path, sha):
            markdown = original_read(path, sha)
            with mock.patch.object(self.store, "read", side_effect=original_read):
                save_project(
                    saved_project,
                    self.member,
                    "# Node_1\nChanged.\n",
                    [{"id": "Node_1", "position": {"x": 900, "y": 800}}],
                    saved_project.revision,
                    self.store,
                )
            return markdown

        with mock.patch.object(self.store, "read", side_effect=read_with_concurrent_save):
            response = self.open_project(project_id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["revision"], 2)
        self.assertEqual(body["markdown_source"], original_markdown)
        self.assertEqual(body["layout_data"], {"nodes": original_nodes})
        self.assertEqual(Project.objects.get(pk=project_id).revision, 3)

    def test_open_refreshes_metadata_after_a_save_during_the_access_check(self):
        project_id = self.create_project()
        self.save_project(project_id, "# Node_1\nOriginal.\n")
        new_markdown = "# Node_1\nChanged.\n"
        new_nodes = [{"id": "Node_1", "position": {"x": 900, "y": 800}}]

        def check_access_then_save(request, project_id):
            project = get_member_project(request, project_id)
            save_project(
                project, self.member, new_markdown, new_nodes, project.revision,
                self.store,
            )
            return project

        with mock.patch(
            "projects.views.get_member_project", side_effect=check_access_then_save
        ):
            response = self.open_project(project_id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["revision"], 3)
        self.assertEqual(body["markdown_source"], new_markdown)
        self.assertEqual(body["layout_data"], {"nodes": new_nodes})


class SaveProjectTests(ProjectAPITestCase):
    MARKDOWN = "# Node_1\nHello!\n-> Choice 1 -> Node_2\n\n# Node_2\nBye.\n"
    NODES = [
        {"id": "Node_1", "position": {"x": 120, "y": 300}},
        {"id": "Node_2", "position": {"x": 420, "y": 300}},
    ]

    def test_saved_changes_are_restored_on_reopen(self):
        project_id = self.create_project()

        response = self.save_project(project_id, self.MARKDOWN, self.NODES)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["status"], "saved")
        self.assertEqual(body["revision"], 2)
        self.assertEqual(body["diagnostics"], [])
        reopened = self.open_project(project_id).json()
        self.assertEqual(reopened["markdown_source"], self.MARKDOWN)
        self.assertEqual(reopened["revision"], 2)
        self.assertEqual(reopened["layout_data"], {"nodes": self.NODES})

    def test_outdated_revision_returns_409_and_keeps_the_saved_state(self):
        project_id = self.create_project()
        self.save_project(project_id, self.MARKDOWN, self.NODES, base_revision=1)

        response = self.save_project(
            project_id, "# Node_1\nOverwritten.\n", base_revision=1
        )

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(response.json()["revision"], 2)
        reopened = self.open_project(project_id).json()
        self.assertEqual(reopened["markdown_source"], self.MARKDOWN)
        self.assertEqual(reopened["revision"], 2)

    def test_malformed_layout_returns_400_and_saves_nothing(self):
        cases = {
            "non_numeric_coordinate": [
                {"id": "Node_1", "position": {"x": "left", "y": 300}}
            ],
            "non_finite_coordinate": [
                {"id": "Node_1", "position": {"x": "inf", "y": 300}}
            ],
            "duplicate_node_ids": [self.NODES[0], self.NODES[0]],
        }

        for case, nodes in cases.items():
            with self.subTest(case=case):
                project_id = self.create_project()

                response = self.save_project(project_id, self.MARKDOWN, nodes)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                project = Project.objects.get(pk=project_id)
                self.assertEqual(project.revision, 1)
                self.assertEqual(project.head_commit_sha, "")
                self.assertFalse(project.positions.exists())

    def test_non_member_cannot_save(self):
        project_id = self.create_project()
        self.client.force_authenticate(self.outsider)

        response = self.save_project(project_id, self.MARKDOWN, self.NODES)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Project.objects.get(pk=project_id).revision, 1)

    def test_failed_markdown_read_aborts_save_without_writing(self):
        moved = [{"id": "Node_2", "position": {"x": 500, "y": 80}}]

        for markdown in (self.MARKDOWN, "# Node_1\nChanged.\n"):
            with self.subTest(markdown_changed=markdown != self.MARKDOWN):
                project_id = self.create_project()
                self.save_project(project_id, self.MARKDOWN, self.NODES)
                saved_project = Project.objects.get(pk=project_id)
                with (
                    mock.patch.object(
                        self.store, "read", side_effect=ContentStoreError("Read failed.")
                    ),
                    mock.patch.object(self.store, "write", wraps=self.store.write) as write,
                ):
                    response = self.save_project(
                        project_id, markdown, moved, base_revision=2
                    )

                self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
                write.assert_not_called()
                project = Project.objects.get(pk=project_id)
                self.assertEqual(project.head_commit_sha, saved_project.head_commit_sha)
                self.assertEqual(project.revision, saved_project.revision)
                self.assertEqual(project.updated_at, saved_project.updated_at)
                reopened = self.open_project(project_id).json()
                self.assertEqual(reopened["markdown_source"], self.MARKDOWN)
                self.assertEqual(reopened["layout_data"], {"nodes": self.NODES})


class GitHubSaveTests(ProjectAPITestCase):
    MARKDOWN = "# Node_1\nHello!\n"
    NODES = [{"id": "Node_1", "position": {"x": 120, "y": 300}}]

    def setUp(self):
        super().setUp()
        self.github = FakeGitHub()
        self.store = GitHubContentStore("team6/dialogue-content", "test-token")
        for patcher in (
            mock.patch("projects.storage.urlopen", side_effect=self.github),
            mock.patch("projects.views.get_content_store", return_value=self.store),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_save_commits_the_markdown_and_reopen_reads_that_commit(self):
        project_id = self.create_project()

        response = self.save_project(project_id, self.MARKDOWN, self.NODES)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        project = Project.objects.get(pk=project_id)
        self.assertEqual(
            self.github.commits[project.head_commit_sha],
            (f"projects/{project_id}.md", self.MARKDOWN.encode()),
        )
        [put] = self.github.puts()
        self.assertEqual(
            put["message"],
            f"Save Act 1 Dialogue ({project_id}) revision 2 by designer@example.com",
        )
        reopened = self.open_project(project_id).json()
        self.assertEqual(reopened["markdown_source"], self.MARKDOWN)
        self.assertEqual(reopened["layout_data"], {"nodes": self.NODES})

    def test_position_only_save_makes_no_commit(self):
        project_id = self.create_project()
        self.save_project(project_id, self.MARKDOWN, self.NODES)
        saved_sha = Project.objects.get(pk=project_id).head_commit_sha
        moved = [{"id": "Node_1", "position": {"x": 500, "y": 80}}]

        response = self.save_project(project_id, self.MARKDOWN, moved, base_revision=2)

        self.assertEqual(response.json()["revision"], 3)
        self.assertEqual(len(self.github.puts()), 1)
        project = Project.objects.get(pk=project_id)
        self.assertEqual(project.head_commit_sha, saved_sha)
        position = NodePosition.objects.get(project=project, node_id="Node_1")
        self.assertEqual((position.x, position.y), (500, 80))

    def github_outage(self):
        return mock.patch(
            "projects.storage.urlopen", side_effect=URLError("Network is unreachable")
        )

    def test_github_outage_returns_503_and_changes_nothing(self):
        project_id = self.create_project()

        with self.github_outage():
            failed_save = self.save_project(project_id, self.MARKDOWN, self.NODES)

        self.assertEqual(failed_save.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        project = Project.objects.get(pk=project_id)
        self.assertEqual(project.revision, 1)
        self.assertEqual(project.head_commit_sha, "")
        self.assertFalse(project.positions.exists())

        self.save_project(project_id, self.MARKDOWN, self.NODES)
        with self.github_outage():
            failed_open = self.open_project(project_id)

        self.assertEqual(failed_open.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        reopened = self.open_project(project_id).json()
        self.assertEqual(reopened["markdown_source"], self.MARKDOWN)
        self.assertEqual(reopened["revision"], 2)

    def test_database_failure_after_the_commit_keeps_the_previous_version(self):
        project_id = self.create_project()
        self.save_project(project_id, self.MARKDOWN, self.NODES)
        project = Project.objects.get(pk=project_id)

        with (
            mock.patch.object(Project, "save", side_effect=DatabaseError("Write failed.")),
            self.assertRaises(DatabaseError),
        ):
            save_project(
                project, self.member, "# Node_1\nChanged.\n", self.NODES, 2, self.store
            )

        self.assertEqual(len(self.github.commits), 2)
        reopened = self.open_project(project_id).json()
        self.assertEqual(reopened["markdown_source"], self.MARKDOWN)
        self.assertEqual(reopened["revision"], 2)
