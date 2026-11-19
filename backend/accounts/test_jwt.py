import datetime

import jwt
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project
from teams.models import Team, TeamMembership

from .tokens import InvalidToken, create_token, user_from_token

OTHER_KEY = "some-other-signing-key-that-is-long-enough"


def make_user(email="designer@example.com", **fields):
    return get_user_model().objects.create_user(
        email=email, password="a-test-password-629", display_name="Designer", **fields
    )


def in_five_minutes():
    return datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=5)


class TokenTests(TestCase):
    def test_token_identifies_the_user_it_was_made_for(self):
        user = make_user()

        self.assertEqual(user_from_token(create_token(user)), user)

    @override_settings(JWT_LIFETIME_SECONDS=-1)
    def test_expired_token_is_rejected(self):
        token = create_token(make_user())

        with self.assertRaises(InvalidToken):
            user_from_token(token)

    def test_token_signed_with_another_key_is_rejected(self):
        user = make_user()
        forged = jwt.encode(
            {"sub": str(user.pk), "exp": in_five_minutes()}, OTHER_KEY, algorithm="HS256"
        )

        with self.assertRaises(InvalidToken):
            user_from_token(forged)

    def test_token_without_an_expiry_is_rejected(self):
        from django.conf import settings

        user = make_user()
        token = jwt.encode({"sub": str(user.pk)}, settings.SECRET_KEY, algorithm="HS256")

        with self.assertRaises(InvalidToken):
            user_from_token(token)

    def test_garbage_is_rejected(self):
        with self.assertRaises(InvalidToken):
            user_from_token("not-a-token")

    def test_token_of_an_inactive_user_is_rejected(self):
        user = make_user()
        token = create_token(user)
        user.is_active = False
        user.save()

        with self.assertRaises(InvalidToken):
            user_from_token(token)


class BearerAuthenticationTests(APITestCase):
    def setUp(self):
        self.member = make_user()
        self.outsider = make_user("outsider@example.com")
        self.team = Team.objects.create(name="Team 6")
        TeamMembership.objects.create(team=self.team, user=self.member)

    def post_project(self, authorization=None):
        headers = {"HTTP_AUTHORIZATION": authorization} if authorization else {}
        return self.client.post(
            reverse("project-create"),
            {"name": "Act 1", "team_id": self.team.pk},
            format="json",
            **headers,
        )

    def test_valid_token_signs_the_request_in(self):
        response = self.post_project(f"Bearer {create_token(self.member)}")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_request_without_a_token_gets_401_with_a_bearer_challenge(self):
        response = self.post_project()

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response["WWW-Authenticate"], "Bearer")
        self.assertFalse(Project.objects.exists())

    def test_invalid_token_gets_401_and_no_data(self):
        for header in ("Bearer not-a-token", "Bearer"):
            with self.subTest(header=header):
                response = self.post_project(header)

                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
                self.assertFalse(Project.objects.exists())

    @override_settings(JWT_LIFETIME_SECONDS=-1)
    def test_expired_token_gets_401(self):
        response = self.post_project(f"Bearer {create_token(self.member)}")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Project.objects.exists())

    def test_valid_token_of_a_non_member_gets_403(self):
        response = self.post_project(f"Bearer {create_token(self.outsider)}")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Project.objects.exists())

    def test_admin_session_login_still_works(self):
        self.client.force_login(self.member)

        response = self.post_project()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class TeamProjectRequestTests(APITestCase):
    def setUp(self):
        self.member = make_user()
        self.team = Team.objects.create(name="Team 6")
        TeamMembership.objects.create(team=self.team, user=self.member)
        self.project = Project.objects.create(team=self.team, name="Act 1")

    def open_project(self, authorization=None):
        headers = {"HTTP_AUTHORIZATION": authorization} if authorization else {}
        return self.client.get(
            reverse("project-detail", args=[self.project.pk]), **headers
        )

    def test_signed_out_or_invalid_token_gets_401_and_no_project_data(self):
        for header in (None, "Bearer not-a-token"):
            with self.subTest(header=header):
                response = self.open_project(header)

                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
                self.assertNotIn("markdown_source", response.json())

    @override_settings(JWT_LIFETIME_SECONDS=-1)
    def test_expired_token_gets_401_and_no_project_data(self):
        response = self.open_project(f"Bearer {create_token(self.member)}")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("markdown_source", response.json())