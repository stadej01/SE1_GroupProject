from unittest.mock import patch
from uuid import uuid4

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.tokens import create_token
from teams.models import Team, TeamMembership

from .models import NodePosition, Project


VALID = '# A\nNarrator: Hello.\n* "Go" -> B\n# B\nNarrator: Goodbye.'


class ProjectPageTests(TestCase):
    @override_settings(CSRF_COOKIE_NAME="custom_project_csrf")
    def test_project_has_configured_csrf_cookie_and_login_url(self):
        response = self.client.get(self.project_url())
        self.assertContains(response, 'data-csrf-cookie="custom_project_csrf"')
        self.assertContains(response, f'data-login-url="{reverse("accounts:login")}"')

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email="member@example.com", display_name="Member", password="member-river-window-947"
        )
        cls.team = Team.objects.create(name="Writing team")
        cls.other_team = Team.objects.create(name="Private other team")
        TeamMembership.objects.create(user=cls.user, team=cls.team)
        cls.project = Project.objects.create(team=cls.team, name="Our story")
        cls.other_project = Project.objects.create(team=cls.other_team, name="Secret project title")

    def setUp(self):
        self.client.cookies[settings.JWT_COOKIE_NAME] = create_token(self.user)

    def project_url(self, project=None):
        return reverse("pages:project", args=[(project or self.project).pk])

    def test_anonymous_home_and_project_redirect_and_login_returns_to_each(self):
        for url in ("/", self.project_url()):
            with self.subTest(url=url):
                self.client.cookies.pop(settings.JWT_COOKIE_NAME)
                response = self.client.get(url)
                self.assertRedirects(response, f"/accounts/login/?next={url}")
                self.assertEqual(self.client.get(response.url).context["next"], url)
                response = self.client.post(reverse("auth-login"), {
                    "email": self.user.email, "password": "member-river-window-947",
                }, content_type="application/json")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(self.client.get(url).status_code, 200)

    @override_settings(JWT_LIFETIME_SECONDS=-1)
    def test_expired_cookie_redirects_to_login(self):
        self.client.cookies[settings.JWT_COOKIE_NAME] = create_token(self.user)
        url = self.project_url()
        self.assertRedirects(self.client.get(url), f"/accounts/login/?next={url}")

    def test_home_lists_only_member_teams_and_their_projects(self):
        second_team = Team.objects.create(name="Second writing team")
        TeamMembership.objects.create(user=self.user, team=second_team)
        response = self.client.get("/")
        self.assertContains(response, self.team.name)
        self.assertContains(response, second_team.name)
        self.assertContains(response, self.project.name)
        self.assertNotContains(response, self.other_team.name)
        self.assertNotContains(response, self.other_project.name)
        self.assertEqual(list(response.context["form"].fields["team"].queryset), [self.team, second_team])

    def test_create_project_is_empty_and_writes_only_database(self):
        with patch("projects.storage.get_content_store") as store:
            response = self.client.post(reverse("pages:create"), {"name": "New story", "team": self.team.pk})
        project = Project.objects.get(name="New story")
        self.assertRedirects(response, self.project_url(project))
        self.assertEqual(project.revision, 1)
        self.assertEqual(project.head_commit_sha, "")
        self.assertEqual(project.github_path, f"teams/{self.team.pk}/projects/{project.pk}.md")
        self.assertFalse(NodePosition.objects.exists())
        store.assert_not_called()

    def test_create_rejects_another_team_without_writing_records(self):
        counts = (Project.objects.count(), Team.objects.count(), TeamMembership.objects.count())
        response = self.client.post(reverse("pages:create"), {"name": "Forbidden story", "team": self.other_team.pk})
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.context["form"].errors["team"])
        self.assertEqual(counts, (Project.objects.count(), Team.objects.count(), TeamMembership.objects.count()))
        self.assertFalse(NodePosition.objects.exists())

    def test_create_requires_post_and_nonblank_name(self):
        self.assertEqual(self.client.get(reverse("pages:create")).status_code, 405)
        response = self.client.post(reverse("pages:create"), {"name": "   ", "team": self.team.pk})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Project.objects.count(), 2)

    def test_account_without_team_sees_admin_help(self):
        TeamMembership.objects.filter(user=self.user).delete()
        response = self.client.get("/")
        self.assertContains(response, "Ask an administrator to add you to a team")
        self.assertContains(response, reverse("admin:index"))
        self.assertNotContains(response, "Create project")

    def test_project_editor_has_back_link_and_leave_dialog(self):
        response = self.client.get(self.project_url())
        self.assertRegex(response.content.decode(), rf'<a id="back-to-projects"[^>]*href="{reverse("pages:home")}"')
        self.assertContains(response, 'id="leave-dialog"')
        self.assertContains(response, "Save your changes before leaving?")
        self.assertContains(response, 'id="logout-form"')

    def test_nonmember_gets_403_without_project_name(self):
        response = self.client.get(self.project_url(self.other_project))
        self.assertContains(response, "Access denied", status_code=403)
        self.assertNotContains(response, self.other_project.name, status_code=403)
        self.assertNotContains(response, 'id="editor"', status_code=403)

    def test_unknown_project_is_404(self):
        self.assertEqual(self.client.get(reverse("pages:project", args=[uuid4()])).status_code, 404)

    def test_member_gets_empty_editor_without_reading_markdown(self):
        self.project.head_commit_sha = "a" * 40
        self.project.save()
        with patch("projects.storage.get_content_store") as store:
            response = self.client.get(self.project_url())
        self.assertTemplateUsed(response, "editor/index.html")
        self.assertContains(response, self.project.name)
        self.assertNotIn("markdown_source", response.context)
        self.assertRegex(response.content.decode(), r'<textarea[^>]*id="markdown-source"[^>]*></textarea>')
        self.assertNotContains(response, "Node_Merchant")
        self.assertContains(response, 'data-sync-url="/sync"')
        self.assertContains(response, f'data-open-url="/api/v1/projects/{self.project.pk}"')
        self.assertContains(response, f'data-save-url="/api/v1/projects/{self.project.pk}/save"')
        self.assertContains(response, 'data-revision="1"')
        self.assertNotContains(response, "draft")
        self.assertRegex(response.content.decode(), r'<textarea[^>]*id="markdown-source"[^>]*disabled')
        store.assert_not_called()


class SharedSyncTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.user = get_user_model().objects.create_user(email="writer@example.com", display_name="Writer")

    def sign_in(self):
        self.client.cookies[settings.JWT_COOKIE_NAME] = create_token(self.user)

    def test_anonymous_sync_is_json_401_even_without_csrf(self):
        response = self.client.post("/sync", {"markdown_source": VALID}, content_type="application/json")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json()["ok"])
        self.assertTrue(response.json()["diagnostics"])

    def test_admin_session_alone_cannot_sync(self):
        self.client.force_login(self.user)
        response = self.client.post("/sync", {"markdown_source": VALID}, content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_authenticated_sync_without_csrf_is_json_403(self):
        self.sign_in()
        response = self.client.post("/sync", {"markdown_source": VALID}, content_type="application/json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()["ok"])
        self.assertTrue(response.json()["diagnostics"])

    def test_authenticated_sync_with_csrf_returns_graph(self):
        self.sign_in()
        self.client.get("/")
        token = self.client.cookies[settings.CSRF_COOKIE_NAME].value
        response = self.client.post("/sync", {"markdown_source": VALID}, content_type="application/json", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])
        self.assertEqual([node["id"] for node in response.json()["graph"]["nodes"]], ["A", "B"])
        self.assertEqual(response.json()["graph"]["edges"][0]["target"], "B")

    def test_form_csrf_failure_keeps_django_html_response(self):
        response = self.client.post(reverse("accounts:register"), {"email": self.user.email})
        self.assertContains(response, "CSRF verification failed", status_code=403)
        self.assertTrue(response["Content-Type"].startswith("text/html"))

    def test_json_accept_header_gets_json_csrf_failure(self):
        response = self.client.post(reverse("accounts:register"), {}, HTTP_ACCEPT="application/json")
        self.assertEqual(response.status_code, 403)
        self.assertFalse(response.json()["ok"])
