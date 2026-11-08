from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from projects.models import Project
from teams.models import Team, TeamMembership

from .tokens import user_from_token

PASSWORD = "a-test-password-629"


def make_user(email="designer@example.com", **fields):
    return get_user_model().objects.create_user(
        email=email, password=PASSWORD, display_name="Designer", **fields
    )


class LoginTests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.url = reverse("auth-login")

    def login(self, **body):
        return self.client.post(self.url, body, format="json")

    def test_valid_login_returns_a_token_and_the_user(self):
        response = self.login(email="designer@example.com", password=PASSWORD)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        body = response.json()
        self.assertEqual(user_from_token(body["token"]), self.user)
        self.assertEqual(
            body["user"],
            {"id": self.user.pk, "name": "Designer", "email": "designer@example.com"},
        )

    def test_email_capitalization_does_not_matter(self):
        response = self.login(email="DESIGNER@Example.com", password=PASSWORD)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_the_returned_token_signs_later_requests_in(self):
        team = Team.objects.create(name="Team 6")
        TeamMembership.objects.create(team=team, user=self.user)
        token = self.login(email="designer@example.com", password=PASSWORD).json()["token"]

        response = self.client.post(
            reverse("project-create"),
            {"name": "Act 1", "team_id": team.pk},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_wrong_password_or_unknown_email_gets_401_and_no_token(self):
        cases = {
            "wrong_password": {"email": "designer@example.com", "password": "nope"},
            "unknown_email": {"email": "nobody@example.com", "password": PASSWORD},
            "not_an_email": {"email": "not-an-email", "password": PASSWORD},
        }
        messages = set()
        for case, body in cases.items():
            with self.subTest(case=case):
                response = self.login(**body)

                self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
                self.assertNotIn("token", response.json())
                messages.add(response.json()["detail"])
        self.assertEqual(len(messages), 1)  # Does not reveal which accounts exist.

    def test_missing_or_blank_field_gets_400_naming_the_field(self):
        cases = [
            ({"password": PASSWORD}, ["email"]),
            ({"email": "designer@example.com"}, ["password"]),
            ({"email": "", "password": PASSWORD}, ["email"]),
            ({"email": "designer@example.com", "password": ""}, ["password"]),
            ({}, ["email", "password"]),
        ]
        for body, fields in cases:
            with self.subTest(body=body):
                response = self.login(**body)

                self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
                self.assertNotIn("token", response.json())
                for field in fields:
                    self.assertIn(field, response.json())

    def test_inactive_user_cannot_sign_in(self):
        self.user.is_active = False
        self.user.save()

        response = self.login(email="designer@example.com", password=PASSWORD)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("token", response.json())


class LoginDashboardTests(APITestCase):
    def test_login_lists_the_users_teams_and_projects(self):
        user = make_user()
        team_a = Team.objects.create(name="Team A")
        team_b = Team.objects.create(name="Team B")
        team_c = Team.objects.create(name="Team C")
        TeamMembership.objects.create(team=team_a, user=user)
        TeamMembership.objects.create(team=team_c, user=user)
        Project.objects.create(team=team_a, name="Beta")
        alpha = Project.objects.create(team=team_a, name="Alpha")
        Project.objects.create(team=team_b, name="Hidden")

        response = self.client.post(
            reverse("auth-login"),
            {"email": "designer@example.com", "password": PASSWORD},
            format="json",
        )

        teams = response.json()["teams"]
        self.assertEqual([team["name"] for team in teams], ["Team A", "Team C"])
        self.assertEqual(teams[0]["team_id"], team_a.pk)
        self.assertEqual([p["name"] for p in teams[0]["projects"]], ["Alpha", "Beta"])
        self.assertEqual(teams[0]["projects"][0]["project_id"], str(alpha.pk))
        self.assertEqual(teams[0]["projects"][0]["revision"], 1)
        self.assertEqual(teams[1]["projects"], [])

    def test_user_without_teams_gets_an_empty_dashboard(self):
        make_user()

        response = self.client.post(
            reverse("auth-login"),
            {"email": "designer@example.com", "password": PASSWORD},
            format="json",
        )

        self.assertEqual(response.json()["teams"], [])