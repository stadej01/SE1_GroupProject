import uuid
from unittest import mock

from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase
from django.urls import reverse
from rest_framework import status

from teams.models import Team, TeamMembership

from .admin import CommentInline
from .models import Comment, Project
from .reset import BUSINESS_TABLES
from .storage import ContentStoreError, InMemoryContentStore
from .tests import ProjectAPITestCase

MARKDOWN = (
    "<!-- start: Node_1 -->\n"
    "# Node_1\n"
    "Merchant: Hello! <!-- #line:dlg_001 -->\n"
    '* "Goodbye." -> Node_2 <!-- #line:chc_001 -->\n'
    "\n"
    "# Node_2\n"
    "Merchant: Bye.\n"
)
SECRET = "SECRET-REVIEW-NOTE"


class CommentModelTests(TestCase):
    def test_comments_belong_to_a_project_and_go_with_it(self):
        user = get_user_model().objects.create_user(
            email="reviewer@example.com", display_name="Reviewer"
        )
        project = Project.objects.create(team=Team.objects.create(name="T"), name="P")
        comment = Comment.objects.create(
            project=project, node_id="Node_1", author=user, body="Check the tone."
        )

        self.assertIsInstance(comment.pk, uuid.UUID)
        self.assertIsNone(comment.edited_at)
        self.assertEqual(list(project.comments.all()), [comment])
        project.delete()
        self.assertFalse(Comment.objects.exists())

    def test_reset_clears_comments_before_their_project(self):
        tables = list(BUSINESS_TABLES)
        self.assertLess(tables.index("projects_comment"), tables.index("projects_project"))
        self.assertLess(tables.index("projects_comment"), tables.index("accounts_user"))


class CommentAdminTests(TestCase):
    def test_admin_lists_comments_but_cannot_add_one_without_an_author(self):
        request = RequestFactory().get("/admin/")
        request.user = get_user_model().objects.create_superuser(
            email="admin@example.com", display_name="Admin", password="admin-river-947"
        )
        inline = CommentInline(Project, admin.site)

        self.assertFalse(inline.has_add_permission(request))
        self.assertTrue(inline.has_view_permission(request))


class CommentAPITestCase(ProjectAPITestCase):
    def setUp(self):
        super().setUp()
        self.teammate = get_user_model().objects.create_user(
            email="writer@example.com", display_name="Writer"
        )
        TeamMembership.objects.create(team=self.team, user=self.teammate)
        self.project_id = self.create_project()
        response = self.save_project(self.project_id, MARKDOWN)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def comments_url(self, project_id=None):
        return reverse("project-comments", args=[project_id or self.project_id])

    def comment_url(self, comment_id, project_id=None):
        return reverse(
            "project-comment-detail", args=[project_id or self.project_id, comment_id]
        )

    def add_comment(self, node_id="Node_1", body="Check the tone."):
        return self.client.post(
            self.comments_url(), {"node_id": node_id, "body": body}, format="json"
        )

    def created_comment(self, **kwargs):
        response = self.add_comment(**kwargs)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return response.json()

    def project_state(self):
        project = Project.objects.get(pk=self.project_id)
        markdown = self.open_project(self.project_id).json()["markdown_source"]
        return project.revision, project.head_commit_sha, markdown


class AddCommentTests(CommentAPITestCase):
    """team members comment on a node and see each other's comments."""

    def test_member_adds_a_comment_to_a_saved_node(self):
        response = self.add_comment()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.json()
        self.assertEqual(body["node_id"], "Node_1")
        self.assertEqual(body["project_id"], self.project_id)
        self.assertEqual(body["author_id"], self.member.pk)
        self.assertEqual(body["author_name"], "Designer")
        self.assertEqual(body["body"], "Check the tone.")
        self.assertIsNone(body["edited_at"])
        self.assertTrue(body["created_at"])

    def test_teammate_sees_the_comment_when_opening_the_project(self):
        comment = self.created_comment()

        self.client.force_authenticate(self.teammate)
        response = self.open_project(self.project_id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["comments"], [comment])

    def test_list_returns_every_comment_in_created_order(self):
        first = self.created_comment(body="First")
        self.client.force_authenticate(self.teammate)
        second = self.created_comment(node_id="Node_2", body="Second")

        response = self.client.get(self.comments_url())

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["comments"], [first, second])

    def test_outsider_cannot_list_or_add_comments(self):
        self.created_comment()
        self.client.force_authenticate(self.outsider)

        self.assertEqual(
            self.client.get(self.comments_url()).status_code, status.HTTP_403_FORBIDDEN
        )
        self.assertEqual(self.add_comment().status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Comment.objects.count(), 1)

    def test_unauthenticated_request_returns_401(self):
        self.client.force_authenticate(None)

        self.assertEqual(self.add_comment().status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(
            self.client.get(self.comments_url()).status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_node_missing_from_the_saved_markdown_returns_404(self):
        response = self.add_comment(node_id="Node_Unsaved")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            response.json()["detail"], "Save the project before commenting on this node."
        )
        self.assertFalse(Comment.objects.exists())

    def test_unknown_project_returns_404(self):
        response = self.client.post(
            self.comments_url(uuid.uuid4()),
            {"node_id": "Node_1", "body": "Hi"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_blank_or_missing_body_returns_400(self):
        for body in ("", "   ", None):
            with self.subTest(body=body):
                data = {"node_id": "Node_1"} if body is None else {"node_id": "Node_1", "body": body}
                response = self.client.post(self.comments_url(), data, format="json")
                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Comment.objects.exists())

    def test_overlong_body_returns_400(self):
        response = self.add_comment(body="x" * 5001)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_storage_outage_returns_503(self):
        with (
            mock.patch.object(
                InMemoryContentStore, "read", side_effect=ContentStoreError("down")
            ),
            self.assertLogs("projects.views", "WARNING") as logs,
        ):
            response = self.add_comment()

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("Could not read Markdown to comment on project", logs.output[0])
        self.assertFalse(Comment.objects.exists())

    def test_adding_a_comment_leaves_the_project_unchanged(self):
        before = self.project_state()
        with mock.patch.object(InMemoryContentStore, "write") as write:
            self.created_comment()

        write.assert_not_called()
        self.assertEqual(self.project_state(), before)


class ChangeCommentTests(CommentAPITestCase):
    """only the author can edit or delete"""

    def setUp(self):
        super().setUp()
        self.comment = self.created_comment()
        self.url = self.comment_url(self.comment["comment_id"])

    def test_author_edits_the_comment(self):
        response = self.client.put(self.url, {"body": "Tone is fine now."}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(body["body"], "Tone is fine now.")
        self.assertIsNotNone(body["edited_at"])
        self.assertEqual(body["created_at"], self.comment["created_at"])
        self.assertEqual(body["author_id"], self.member.pk)
        self.assertEqual(Comment.objects.get().body, "Tone is fine now.")

    def test_author_deletes_the_comment(self):
        response = self.client.delete(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.json()["message"],
            f"Comment {self.comment['comment_id']} successfully deleted.",
        )
        self.assertFalse(Comment.objects.exists())

    def test_another_member_cannot_edit_or_delete(self):
        self.client.force_authenticate(self.teammate)

        edit = self.client.put(self.url, {"body": "Hijacked"}, format="json")
        delete = self.client.delete(self.url)

        self.assertEqual(edit.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(delete.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Comment.objects.get().body, "Check the tone.")

    def test_outsider_cannot_edit_or_delete(self):
        self.client.force_authenticate(self.outsider)

        self.assertEqual(
            self.client.put(self.url, {"body": "x"}, format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(self.client.delete(self.url).status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Comment.objects.exists())

    def test_unauthenticated_request_returns_401(self):
        self.client.force_authenticate(None)

        self.assertEqual(
            self.client.put(self.url, {"body": "x"}, format="json").status_code,
            status.HTTP_401_UNAUTHORIZED,
        )
        self.assertEqual(
            self.client.delete(self.url).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_comment_from_another_project_returns_404(self):
        other_project = self.create_project()
        url = self.comment_url(self.comment["comment_id"], project_id=other_project)

        self.assertEqual(
            self.client.put(url, {"body": "x"}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Comment.objects.exists())

    def test_unknown_comment_returns_404(self):
        url = self.comment_url(uuid.uuid4())

        self.assertEqual(self.client.delete(url).status_code, status.HTTP_404_NOT_FOUND)

    def test_blank_edit_returns_400(self):
        response = self.client.put(self.url, {"body": "  "}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        comment = Comment.objects.get()
        self.assertEqual(comment.body, "Check the tone.")
        self.assertIsNone(comment.edited_at)

    def test_edit_and_delete_never_change_the_dialogue(self):
        before = self.project_state()
        with mock.patch.object(InMemoryContentStore, "write") as write:
            self.client.put(self.url, {"body": "Edited"}, format="json")
            self.client.force_authenticate(self.teammate)
            self.client.put(self.url, {"body": "Refused"}, format="json")
            self.client.delete(self.url)
            self.client.force_authenticate(self.member)
            self.client.put(self.url, {"body": ""}, format="json")
            self.client.delete(self.url)

        write.assert_not_called()
        self.assertEqual(self.project_state(), before)


class CommentExportTests(CommentAPITestCase):
    """comments never reach the exported JSON."""

    def node(self, export, node_id):
        return next(node for node in export["nodes"] if node["id"] == node_id)

    def test_saved_export_leaves_out_comments(self):
        before = self.export_project(self.project_id).json()
        self.created_comment(body=SECRET)

        response = self.export_project(self.project_id)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(SECRET, response.content.decode())
        self.assertNotIn("comments", response.content.decode())
        after = response.json()
        for key in ("sequence", "choices"):
            self.assertEqual(self.node(after, "Node_1")[key], self.node(before, "Node_1")[key])

    def test_unsaved_export_leaves_out_comments(self):
        before = self.export_unsaved(self.project_id, MARKDOWN).json()
        self.created_comment(body=SECRET)

        response = self.export_unsaved(self.project_id, MARKDOWN)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(SECRET, response.content.decode())
        self.assertEqual(response.json()["nodes"], before["nodes"])
