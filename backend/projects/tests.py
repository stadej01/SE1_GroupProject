import base64
import io
import json
from unittest import mock
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlsplit

import psycopg
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import DatabaseError, OperationalError
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from teams.models import Team, TeamMembership

from .checks import SECRET_KEY_PLACEHOLDER, required_configuration
from .models import NodePosition, Project
from .services import commit_author, commit_message, save_project
from .storage import (
    ContentStoreError,
    GitHubContentStore,
    InMemoryContentStore,
    get_content_store,
)
from .views import get_member_project

# Create your tests here.

SINGLE_LINE_COMMIT = r'^docs\(dialogue\): (create|update) "[^\r\n]*" r\d+ by [^\r\n]+$'


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

    def test_author_is_sent_and_the_committer_stays_the_token_account(self):
        author = {"name": "Leyan", "email": "user-7@dialogue.invalid"}

        self.store.write(self.PATH, "# Node_1\n", "Save", author=author)

        [put] = self.github.puts()
        self.assertEqual(put["author"], author)
        self.assertNotIn("committer", put)

    def test_empty_content_is_a_commit_and_reads_back_empty(self):
        self.store.write(self.PATH, "# Node_1\n", "Save 1")

        cleared = self.store.write(self.PATH, "", "Save 2")

        self.assertEqual(self.github.puts()[1]["content"], "")
        self.assertEqual(self.store.read(self.PATH, cleared), "")

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


class FakeCursor:
    """Records SQL and can fail the advisory lock the way PostgreSQL does."""

    def __init__(self, lock_error=None):
        self.statements = []
        self.lock_error = lock_error

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def execute(self, sql, params=None):
        self.statements.append((sql, params))
        if self.lock_error and "pg_advisory_xact_lock" in sql:
            raise self.lock_error


class FakePostgres:
    vendor = "postgresql"

    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor


def lock_timeout_error():
    error = OperationalError("canceling statement due to lock timeout")
    error.__cause__ = psycopg.errors.LockNotAvailable()
    return error


class WriteLockTests(SimpleTestCase):
    def setUp(self):
        self.github = FakeGitHub()
        patcher = mock.patch("projects.storage.urlopen", side_effect=self.github)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.store = GitHubContentStore("Team6/Dialogue", "test-token", "main")

    def test_key_is_stable_and_depends_only_on_repository_and_branch(self):
        same = GitHubContentStore("team6/dialogue", "another-token", "main")

        # A fixed value: every process must compute the same key, across restarts.
        self.assertEqual(self.store.write_lock_key(), -4462256706123772531)
        self.assertEqual(same.write_lock_key(), self.store.write_lock_key())
        for other in (
            GitHubContentStore("team6/dialogue", "test-token", "drafts"),
            GitHubContentStore("team6/other", "test-token", "main"),
        ):
            self.assertNotEqual(other.write_lock_key(), self.store.write_lock_key())

    def test_write_takes_the_lock_before_touching_github(self):
        cursor = FakeCursor()

        def check_lock_was_taken(request, timeout):
            self.assertTrue(
                any("pg_advisory_xact_lock" in sql for sql, _ in cursor.statements)
            )
            return self.github(request, timeout)

        with (
            mock.patch("projects.storage.connection", FakePostgres(cursor)),
            mock.patch("projects.storage.urlopen", side_effect=check_lock_was_taken),
        ):
            self.store.write("projects/x.md", "# Node_1\n", "Save")

        self.assertEqual(
            cursor.statements[1],
            ("SELECT pg_advisory_xact_lock(%s)", [self.store.write_lock_key()]),
        )
        self.assertIn("lock_timeout", cursor.statements[0][0])
        self.assertEqual(cursor.statements[2][0], "SET LOCAL lock_timeout TO DEFAULT")

    def test_lock_timeout_is_a_store_error_and_nothing_is_written(self):
        cursor = FakeCursor(lock_error=lock_timeout_error())

        with (
            mock.patch("projects.storage.connection", FakePostgres(cursor)),
            self.assertRaisesMessage(ContentStoreError, "Timed out"),
        ):
            self.store.write("projects/x.md", "# Node_1\n", "Save")

        self.assertEqual(self.github.requests, [])

    def test_other_database_errors_are_not_reported_as_store_errors(self):
        cursor = FakeCursor(lock_error=OperationalError("server closed the connection"))

        with (
            mock.patch("projects.storage.connection", FakePostgres(cursor)),
            self.assertRaises(OperationalError),
        ):
            self.store.write("projects/x.md", "# Node_1\n", "Save")

    def test_other_databases_never_call_the_postgres_lock(self):
        with mock.patch("projects.storage.connection") as connection:
            connection.vendor = "sqlite"
            self.store.write("projects/x.md", "# Node_1\n", "Save")

        connection.cursor.assert_not_called()


class ContentStoreSettingsTests(SimpleTestCase):
    def test_full_app_store_is_github_even_without_a_repository(self):
        with self.settings(
            CONTENT_STORE="github",
            GITHUB_REPOSITORY="team6/dialogue-content",
            GITHUB_TOKEN="test-token",
            GITHUB_BRANCH="drafts",
        ):
            store = get_content_store()
        self.assertIsInstance(store, GitHubContentStore)
        self.assertEqual(store.repository, "team6/dialogue-content")
        self.assertEqual(store.branch, "drafts")

        with self.settings(CONTENT_STORE="github", GITHUB_REPOSITORY=""):
            self.assertIsInstance(get_content_store(), GitHubContentStore)

    def test_only_test_settings_choose_memory(self):
        with self.settings(CONTENT_STORE="memory"):
            self.assertIsInstance(get_content_store(), InMemoryContentStore)


class RequiredConfigurationTests(SimpleTestCase):
    COMPLETE = {
        "CONTENT_STORE": "github",
        "SECRET_KEY": "a-real-secret-value",
        "GITHUB_REPOSITORY": "team6/dialogue-content",
        "GITHUB_TOKEN": "a-real-token-value",
        "GITHUB_BRANCH": "main",
    }

    def problems(self, engine="django.db.backends.postgresql", **overrides):
        with (
            self.settings(**{**self.COMPLETE, **overrides}),
            mock.patch.dict(settings.DATABASES["default"], ENGINE=engine),
        ):
            return required_configuration(None)

    def test_complete_configuration_passes(self):
        self.assertEqual(self.problems(), [])

    def test_memory_storage_needs_no_repository(self):
        self.assertEqual(
            self.problems(CONTENT_STORE="memory", GITHUB_REPOSITORY="", GITHUB_TOKEN=""),
            [],
        )

    def test_each_missing_value_is_named_and_points_to_the_readme(self):
        cases = {
            "DJANGO_SECRET_KEY": {"SECRET_KEY": ""},
            "DATABASE_URL": {"engine": "django.db.backends.dummy"},
            "GITHUB_REPOSITORY": {"GITHUB_REPOSITORY": ""},
            "GITHUB_TOKEN": {"GITHUB_TOKEN": ""},
            "GITHUB_BRANCH": {"GITHUB_BRANCH": ""},
        }
        for name, overrides in cases.items():
            with self.subTest(name=name):
                [problem] = self.problems(**overrides)
                self.assertIn(name, problem.msg)
                self.assertIn("README.md", problem.hint)

    def test_all_problems_are_reported_together(self):
        problems = self.problems(GITHUB_REPOSITORY="", GITHUB_TOKEN="", SECRET_KEY="")

        self.assertEqual(len(problems), 3)

    def test_template_placeholder_is_rejected(self):
        [problem] = self.problems(SECRET_KEY=SECRET_KEY_PLACEHOLDER)

        self.assertIn("DJANGO_SECRET_KEY", problem.msg)

    def test_repository_must_be_owner_slash_name(self):
        [problem] = self.problems(GITHUB_REPOSITORY="not-a-repository")

        self.assertIn("owner/name", problem.msg)

    def test_problems_never_contain_configured_values(self):
        problems = self.problems(GITHUB_REPOSITORY="", SECRET_KEY=SECRET_KEY_PLACEHOLDER)

        text = " ".join(f"{problem.msg} {problem.hint}" for problem in problems)
        self.assertNotIn(self.COMPLETE["GITHUB_TOKEN"], text)
        self.assertNotIn(SECRET_KEY_PLACEHOLDER, text)


class CommitTextTests(SimpleTestCase):
    def project(self, name="Act 1 Dialogue", revision=1, head_commit_sha=""):
        return Project(name=name, revision=revision, head_commit_sha=head_commit_sha)

    def user(self, display_name="Leyan", pk=7):
        return get_user_model()(pk=pk, display_name=display_name)

    def test_first_body_is_a_create_with_the_next_revision(self):
        self.assertEqual(
            commit_message(self.project(), self.user()),
            'docs(dialogue): create "Act 1 Dialogue" r2 by Leyan',
        )

    def test_later_body_is_an_update(self):
        project = self.project(revision=6, head_commit_sha="a" * 40)

        self.assertEqual(
            commit_message(project, self.user("Xiaoming")),
            'docs(dialogue): update "Act 1 Dialogue" r7 by Xiaoming',
        )

    def test_line_breaks_controls_and_quotes_stay_on_one_valid_line(self):
        project = self.project(name='Act "1"\nsecond\tline end\\')

        message = commit_message(project, self.user("Lin\r\nYe\x07an"))

        self.assertEqual(
            message,
            r'docs(dialogue): create "Act \"1\" second line end\\" r2 by Lin Ye an',
        )
        self.assertRegex(message, SINGLE_LINE_COMMIT)

    def test_a_name_git_would_empty_falls_back_to_the_user_id(self):
        for name in ("", "  \n", "...", "<>"):
            with self.subTest(name=name):
                user = self.user(name)
                self.assertTrue(commit_message(self.project(), user).endswith(" by user-7"))
                self.assertEqual(commit_author(user)["name"], "user-7")

    def test_author_uses_a_fixed_address_and_not_the_login_email(self):
        user = self.user()
        user.email = "real.person@example.com"

        self.assertEqual(
            commit_author(user), {"name": "Leyan", "email": "user-7@dialogue.invalid"}
        )


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
        self.assertEqual(
            project.github_path, f"teams/{self.team.pk}/projects/{project.pk}.md"
        )
        self.assertEqual(project.head_commit_sha, "")

    def test_same_name_gets_its_own_file_in_each_team(self):
        other_team = Team.objects.create(name="Team 7")
        TeamMembership.objects.create(team=other_team, user=self.member)
        first = Project.objects.get(pk=self.create_project())
        second = Project.objects.get(pk=self.create_project())
        elsewhere = Project.objects.create(team=other_team, name=first.name)

        self.assertEqual(
            len({first.github_path, second.github_path, elsewhere.github_path}), 3
        )
        self.assertEqual(
            elsewhere.github_path, f"teams/{other_team.pk}/projects/{elsewhere.pk}.md"
        )

    def test_client_cannot_choose_the_path(self):
        response = self.client.post(
            reverse("project-create"),
            {"name": "Act 1", "team_id": self.team.pk, "github_path": "../evil.md"},
            format="json",
        )

        project = Project.objects.get(pk=response.json()["project_id"])
        self.assertEqual(
            project.github_path, f"teams/{self.team.pk}/projects/{project.pk}.md"
        )

    def test_renaming_the_project_or_team_keeps_the_path(self):
        project = Project.objects.get(pk=self.create_project())
        path = project.github_path

        project.name = "Renamed"
        project.save()
        self.team.name = "Renamed team"
        self.team.save()

        self.assertEqual(Project.objects.get(pk=project.pk).github_path, path)

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

    def test_unauthenticated_request_returns_401(self):
        project_id = self.create_project()
        self.client.force_authenticate(user=None)

        response = self.save_project(project_id, self.MARKDOWN, self.NODES)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        project = Project.objects.get(pk=project_id)
        self.assertEqual(project.revision, 1)
        self.assertEqual(project.head_commit_sha, "")
        self.assertFalse(project.positions.exists())

    def test_unknown_project_returns_404(self):
        response = self.save_project(
            "00000000-0000-0000-0000-000000000000", self.MARKDOWN, self.NODES
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertFalse(Project.objects.exists())

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
                    self.assertLogs("projects.views", "WARNING"),
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
            (f"teams/{self.team.pk}/projects/{project_id}.md", self.MARKDOWN.encode()),
        )
        [put] = self.github.puts()
        self.assertEqual(
            put["message"], 'docs(dialogue): create "Act 1 Dialogue" r2 by Designer'
        )
        self.assertEqual(
            put["author"],
            {"name": "Designer", "email": f"user-{self.member.pk}@dialogue.invalid"},
        )
        self.assertNotIn("designer@example.com", self.github.requests[-1].data.decode())
        reopened = self.open_project(project_id).json()
        self.assertEqual(reopened["markdown_source"], self.MARKDOWN)
        self.assertEqual(reopened["layout_data"], {"nodes": self.NODES})

    def test_a_project_with_the_old_path_keeps_it_and_stays_readable(self):
        project = Project.objects.create(
            team=self.team, name="Sprint 3 project", github_path="projects/legacy.md"
        )
        sha = self.store.write(project.github_path, self.MARKDOWN, "Save old")
        project.head_commit_sha = sha
        project.save()

        reopened = self.open_project(project.pk).json()
        self.assertEqual(reopened["markdown_source"], self.MARKDOWN)

        response = self.save_project(project.pk, "# Node_1\nChanged.\n")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        project.refresh_from_db()
        self.assertEqual(project.github_path, "projects/legacy.md")
        self.assertEqual(
            self.github.commits[project.head_commit_sha][0], "projects/legacy.md"
        )
        self.assertEqual(self.store.read("projects/legacy.md", sha), self.MARKDOWN)

    def test_two_accounts_are_recorded_as_separate_authors(self):
        second = get_user_model().objects.create_user(
            email="writer@example.com", display_name="Writer"
        )
        TeamMembership.objects.create(team=self.team, user=second)
        project_id = self.create_project()
        self.save_project(project_id, self.MARKDOWN, self.NODES)

        self.client.force_authenticate(second)
        self.save_project(project_id, "# Node_1\nChanged.\n", base_revision=2)

        first_put, second_put = self.github.puts()
        self.assertEqual(
            first_put["author"],
            {"name": "Designer", "email": f"user-{self.member.pk}@dialogue.invalid"},
        )
        self.assertEqual(
            second_put["author"],
            {"name": "Writer", "email": f"user-{second.pk}@dialogue.invalid"},
        )
        self.assertEqual(
            second_put["message"], 'docs(dialogue): update "Act 1 Dialogue" r3 by Writer'
        )
        self.assertNotIn("committer", second_put)

    def test_empty_project_save_makes_no_commit(self):
        project_id = self.create_project()

        response = self.save_project(project_id, "", self.NODES)

        self.assertEqual(response.json()["revision"], 2)
        self.assertEqual(self.github.puts(), [])
        project = Project.objects.get(pk=project_id)
        self.assertEqual(project.head_commit_sha, "")
        self.assertEqual(project.positions.count(), 1)

    def test_unchanged_save_makes_no_commit_and_advances_the_revision(self):
        project_id = self.create_project()
        self.save_project(project_id, self.MARKDOWN, self.NODES)

        response = self.save_project(project_id, self.MARKDOWN, self.NODES, base_revision=2)

        self.assertEqual(response.json()["revision"], 3)
        self.assertEqual(len(self.github.puts()), 1)

    def test_clearing_saved_text_commits_an_empty_file(self):
        project_id = self.create_project()
        self.save_project(project_id, self.MARKDOWN, self.NODES)
        first_sha = Project.objects.get(pk=project_id).head_commit_sha

        response = self.save_project(project_id, "", self.NODES, base_revision=2)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        [_, put] = self.github.puts()
        self.assertEqual(put["content"], "")
        self.assertEqual(
            put["message"], 'docs(dialogue): update "Act 1 Dialogue" r3 by Designer'
        )
        project = Project.objects.get(pk=project_id)
        self.assertNotEqual(project.head_commit_sha, first_sha)
        self.assertEqual(self.open_project(project_id).json()["markdown_source"], "")

    def test_stale_save_never_reaches_github(self):
        project_id = self.create_project()
        self.save_project(project_id, self.MARKDOWN, self.NODES)
        requests_before = len(self.github.requests)

        response = self.save_project(project_id, "# Node_1\nStale.\n", base_revision=1)

        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(len(self.github.requests), requests_before)
        self.assertEqual(
            self.open_project(project_id).json()["markdown_source"], self.MARKDOWN
        )

    def test_invalid_layout_never_reaches_github(self):
        project_id = self.create_project()

        response = self.save_project(
            project_id, self.MARKDOWN, [{"id": "Node_1", "position": {"x": "left", "y": 0}}]
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.github.requests, [])

    def test_waiting_too_long_for_the_branch_keeps_the_saved_version(self):
        project_id = self.create_project()
        self.save_project(project_id, self.MARKDOWN, self.NODES)
        saved = Project.objects.get(pk=project_id)
        cursor = FakeCursor(lock_error=lock_timeout_error())

        with (
            mock.patch("projects.storage.connection", FakePostgres(cursor)),
            self.assertLogs("projects.views", "WARNING"),
        ):
            response = self.save_project(project_id, "# Node_1\nChanged.\n", base_revision=2)

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(len(self.github.puts()), 1)
        project = Project.objects.get(pk=project_id)
        self.assertEqual(project.revision, saved.revision)
        self.assertEqual(project.head_commit_sha, saved.head_commit_sha)

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

    def assert_logged_with_the_cause(self, logs, action):
        [record] = logs.records
        self.assertIn(action, record.getMessage())
        self.assertIs(record.exc_info[0], ContentStoreError)
        self.assertIn("Network is unreachable", str(record.exc_info[1]))

    def test_github_outage_returns_503_and_changes_nothing(self):
        project_id = self.create_project()

        with self.github_outage(), self.assertLogs("projects.views", "WARNING") as logs:
            failed_save = self.save_project(project_id, self.MARKDOWN, self.NODES)

        self.assertEqual(failed_save.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assert_logged_with_the_cause(logs, f"save project {project_id}")
        project = Project.objects.get(pk=project_id)
        self.assertEqual(project.revision, 1)
        self.assertEqual(project.head_commit_sha, "")
        self.assertFalse(project.positions.exists())

        self.save_project(project_id, self.MARKDOWN, self.NODES)
        with self.github_outage(), self.assertLogs("projects.views", "WARNING") as logs:
            failed_open = self.open_project(project_id)

        self.assertEqual(failed_open.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assert_logged_with_the_cause(logs, f"open project {project_id}")
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
