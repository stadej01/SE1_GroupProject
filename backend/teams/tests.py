from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Team, TeamMembership


class TeamMembershipTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.member = User.objects.create_user(
            email="member@example.com", password="pw-test-12345", display_name="Member"
        )
        self.outsider = User.objects.create_user(
            email="outsider@example.com", password="pw-test-12345", display_name="Outsider"
        )
        self.team = Team.objects.create(name="Team X")
        TeamMembership.objects.create(team=self.team, user=self.member)

    def test_member_is_recognized(self):
        self.assertTrue(self.team.has_member(self.member))

    def test_non_member_is_rejected(self):
        self.assertFalse(self.team.has_member(self.outsider))

    def test_anonymous_user_is_not_a_member(self):
        self.assertFalse(self.team.has_member(AnonymousUser()))

    def test_duplicate_membership_is_rejected(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            TeamMembership.objects.create(team=self.team, user=self.member)