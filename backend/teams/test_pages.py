from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from accounts.tokens import create_token
from projects.models import Project

from . import services
from .models import Team, TeamMembership

PASSWORD = "team-river-window-947"


def make_user(email, name):
    return get_user_model().objects.create_user(email=email, display_name=name, password=PASSWORD)


class TeamPageTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ada = make_user("ada@example.com", "Ada")
        cls.ben = make_user("ben@example.com", "Ben")
        cls.cy = make_user("cy@example.com", "Cy")
        cls.team = Team.objects.create(name="Writers")
        TeamMembership.objects.create(team=cls.team, user=cls.ada)
        TeamMembership.objects.create(team=cls.team, user=cls.ben)
        cls.project = Project.objects.create(team=cls.team, name="Shared story")

    def sign_in(self, user, client=None):
        client = client or self.client
        client.cookies[settings.JWT_COOKIE_NAME] = create_token(user)
        return client

    def members(self, team=None):
        return set((team or self.team).memberships.values_list("user__email", flat=True))

    def url(self, name, *args):
        return reverse(f"teams:{name}", args=args)


class CreateTeamTests(TeamPageTestCase):
    def test_creates_team_with_creator_as_only_member_and_shows_it_on_home(self):
        self.sign_in(self.cy)
        response = self.client.post(self.url("create"), {"team-name": "  Night shift  "})
        team = Team.objects.get(name="Night shift")
        self.assertRedirects(response, f"/#team-{team.pk}", fetch_redirect_response=False)
        self.assertEqual(self.members(team), {"cy@example.com"})
        home = self.client.get("/")
        self.assertContains(home, "Created Night shift.")
        self.assertContains(home, f'<h2 id="team-{team.pk}-name">Night shift</h2>', html=False)
        self.assertContains(home, "1 member")

    def test_blank_name_shows_error_and_creates_nothing(self):
        self.sign_in(self.cy)
        counts = (Team.objects.count(), TeamMembership.objects.count())
        for name in ("", "   "):
            with self.subTest(name=repr(name)):
                response = self.client.post(self.url("create"), {"team-name": name})
                self.assertContains(response, "Enter a team name.", status_code=400)
                self.assertEqual(counts, (Team.objects.count(), TeamMembership.objects.count()))

    def test_too_long_name_is_rejected(self):
        self.sign_in(self.cy)
        response = self.client.post(self.url("create"), {"team-name": "x" * 201})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Team.objects.filter(name="x" * 201).exists())

    def test_team_and_membership_are_created_together(self):
        failure = RuntimeError("membership write failed")
        with patch.object(TeamMembership.objects, "create", side_effect=failure), \
                self.assertRaises(RuntimeError):
            services.create_team(self.cy, "Half made")
        self.assertFalse(Team.objects.filter(name="Half made").exists())

    def test_requires_sign_in_and_post(self):
        response = self.client.post(self.url("create"), {"team-name": "Anonymous"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Team.objects.filter(name="Anonymous").exists())
        self.sign_in(self.cy)
        self.assertEqual(self.client.get(self.url("create")).status_code, 405)


class TeamPageViewTests(TeamPageTestCase):
    def test_member_sees_name_members_emails_and_own_account(self):
        self.sign_in(self.ada)
        response = self.client.get(self.url("detail", self.team.pk))
        self.assertContains(response, '<h1 class="page-title">Team members</h1>')
        self.assertContains(response, 'aria-current="page">Writers</span>')
        for text in ("Ada", "ada@example.com", "Ben", "ben@example.com", "Members (2)"):
            self.assertContains(response, text)
        self.assertContains(response, '<span class="member-name">Ada<span class="you">You</span></span>', html=False)
        self.assertNotContains(response, '<span class="member-name">Ben<span class="you">')
        self.assertContains(response, f'action="{self.url("leave", self.team.pk)}"')
        self.assertContains(response, f'action="{self.url("remove-member", self.team.pk, self.ben.pk)}"')
        self.assertNotContains(response, f'action="{self.url("remove-member", self.team.pk, self.ada.pk)}"')
        self.assertContains(response, 'href="/#team-%d"' % self.team.pk)

    def test_suggestions_only_include_active_colleagues_outside_this_team(self):
        self.sign_in(self.ada)
        outsider = make_user("outside@example.com", "Other")
        inactive = make_user("inactive@example.com", "Inactive")
        inactive.is_active = False
        inactive.save(update_fields=["is_active"])
        for name in ("First", "Second"):
            shared = Team.objects.create(name=name)
            for user in (self.ada, self.ben, self.cy, inactive):
                TeamMembership.objects.create(team=shared, user=user)
        another = Team.objects.create(name="Elsewhere")
        TeamMembership.objects.create(team=another, user=outsider)
        response = self.client.get(self.url("detail", self.team.pk))
        self.assertEqual(list(response.context["suggestions"]), [self.cy])
        self.assertNotContains(response, outsider.email)
        self.assertNotContains(response, inactive.email)

    def test_confirmation_names_the_person_team_and_projects(self):
        self.sign_in(self.ada)
        response = self.client.get(self.url("detail", self.team.pk))
        self.assertContains(response, 'data-confirm-title="Remove Ben?"')
        self.assertContains(response, 'data-confirm-body="ben@example.com will lose access to Writers and its 1 project.')
        self.assertContains(response, 'data-confirm-title="Leave Writers?"')

    def test_only_member_sees_disabled_leave_with_reason(self):
        solo = Team.objects.create(name="Solo")
        TeamMembership.objects.create(team=solo, user=self.cy)
        self.sign_in(self.cy)
        response = self.client.get(self.url("detail", solo.pk))
        self.assertRegex(response.content.decode(), r'<button class="danger" type="submit" disabled aria-describedby="last-member-note">Leave team</button>')
        self.assertContains(response, "A team needs at least one member.")

    def test_names_are_escaped(self):
        self.team.name = '<script>alert("x")</script>'
        self.team.save()
        self.sign_in(self.ada)
        response = self.client.get(self.url("detail", self.team.pk))
        self.assertNotContains(response, '<script>alert("x")</script>')
        self.assertContains(response, "&lt;script&gt;")

    def test_signed_out_visitor_goes_to_login(self):
        url = self.url("detail", self.team.pk)
        self.assertRedirects(self.client.get(url), f"/accounts/login/?next={url}", fetch_redirect_response=False)

    def test_unknown_team_is_404(self):
        self.sign_in(self.ada)
        self.assertEqual(self.client.get(self.url("detail", 999999)).status_code, 404)


class AddMemberTests(TeamPageTestCase):
    def test_member_adds_registered_user_who_then_sees_team_and_projects(self):
        self.sign_in(self.ben)
        response = self.client.post(self.url("add-member", self.team.pk), {"email": "  CY@Example.com "})
        self.assertRedirects(response, self.url("detail", self.team.pk), fetch_redirect_response=False)
        self.assertEqual(self.members(), {"ada@example.com", "ben@example.com", "cy@example.com"})
        self.assertContains(self.client.get(response.url), "Added Cy.")
        cy = self.sign_in(self.cy, Client())
        home = cy.get("/")
        self.assertContains(home, "Writers")
        self.assertContains(home, "Shared story")
        self.assertEqual(cy.get(reverse("project-detail", args=[self.project.pk])).status_code, 200)

    def test_unregistered_email_shows_error_and_adds_nobody(self):
        self.sign_in(self.ada)
        response = self.client.post(self.url("add-member", self.team.pk), {"email": "nobody@example.com"})
        self.assertContains(response, "No account uses this email.", status_code=400)
        self.assertEqual(self.members(), {"ada@example.com", "ben@example.com"})

    def test_existing_member_shows_error_and_keeps_one_membership(self):
        self.sign_in(self.ada)
        response = self.client.post(self.url("add-member", self.team.pk), {"email": "BEN@example.com"})
        self.assertContains(response, "Ben is already a member of this team.", status_code=400)
        self.assertEqual(self.team.memberships.filter(user=self.ben).count(), 1)

    def test_invalid_or_blank_email_is_rejected(self):
        self.sign_in(self.ada)
        for email in ("", "not-an-email"):
            with self.subTest(email=email):
                response = self.client.post(self.url("add-member", self.team.pk), {"email": email})
                self.assertEqual(response.status_code, 400)
        self.assertEqual(self.members(), {"ada@example.com", "ben@example.com"})

    def test_inactive_account_counts_as_unregistered(self):
        self.cy.is_active = False
        self.cy.save()
        self.sign_in(self.ada)
        response = self.client.post(self.url("add-member", self.team.pk), {"email": "cy@example.com"})
        self.assertContains(response, "No account uses this email.", status_code=400)


class RemoveAndLeaveTests(TeamPageTestCase):
    def test_any_member_removes_another_who_loses_access(self):
        self.sign_in(self.ben)
        response = self.client.post(self.url("remove-member", self.team.pk, self.ada.pk))
        self.assertRedirects(response, self.url("detail", self.team.pk))
        self.assertEqual(self.members(), {"ben@example.com"})
        ada = self.sign_in(self.ada, Client(enforce_csrf_checks=False))
        self.assertNotContains(ada.get("/"), "Writers")
        self.assertEqual(ada.get(self.url("detail", self.team.pk)).status_code, 403)
        self.assertEqual(ada.get(reverse("pages:project", args=[self.project.pk])).status_code, 403)
        self.assertEqual(ada.get(reverse("project-detail", args=[self.project.pk])).status_code, 403)
        save = ada.put(reverse("project-save", args=[self.project.pk]), {
            "markdown_source": "# A\nNarrator: hi.", "layout_data": {"nodes": []}, "base_revision": 1,
        }, content_type="application/json")
        self.assertEqual(save.status_code, 403)
        self.project.refresh_from_db()
        self.assertEqual(self.project.revision, 1)

    def test_member_leaves_and_returns_home_without_the_team(self):
        self.sign_in(self.ada)
        response = self.client.post(self.url("leave", self.team.pk))
        self.assertRedirects(response, reverse("pages:home"), fetch_redirect_response=False)
        home = self.client.get("/")
        self.assertContains(home, "You left Writers.")
        self.assertNotContains(home, "Shared story")
        self.assertEqual(self.members(), {"ben@example.com"})

    def test_removing_yourself_through_remove_is_leaving(self):
        self.sign_in(self.ada)
        response = self.client.post(self.url("remove-member", self.team.pk, self.ada.pk))
        self.assertRedirects(response, reverse("pages:home"), fetch_redirect_response=False)
        self.assertEqual(self.members(), {"ben@example.com"})

    def test_last_member_cannot_leave_or_be_removed(self):
        TeamMembership.objects.filter(user=self.ben).delete()
        self.sign_in(self.ada)
        for url in (self.url("leave", self.team.pk), self.url("remove-member", self.team.pk, self.ada.pk)):
            with self.subTest(url=url):
                response = self.client.post(url)
                self.assertContains(response, "You are the only member, so you cannot leave this team.", status_code=409)
                self.assertEqual(self.members(), {"ada@example.com"})

    def test_removing_someone_already_gone_reports_it(self):
        self.sign_in(self.ada)
        response = self.client.post(self.url("remove-member", self.team.pk, self.cy.pk))
        self.assertContains(response, "That person is no longer a member of this team.", status_code=409)
        self.assertEqual(self.members(), {"ada@example.com", "ben@example.com"})

    def test_after_mutual_removal_one_member_remains(self):
        services.remove_member(self.ada, self.team.pk, self.ben.pk)
        with self.assertRaises(services.NotAMember):
            services.remove_member(self.ben, self.team.pk, self.ada.pk)
        self.assertEqual(self.members(), {"ada@example.com"})

    def test_removals_require_post(self):
        self.sign_in(self.ada)
        for url in (self.url("leave", self.team.pk), self.url("remove-member", self.team.pk, self.ben.pk),
                    self.url("add-member", self.team.pk)):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.members(), {"ada@example.com", "ben@example.com"})


class NonMemberTests(TeamPageTestCase):
    def test_nonmember_gets_403_on_page_and_every_change(self):
        self.sign_in(self.cy)
        before = self.members()
        page = self.client.get(self.url("detail", self.team.pk))
        self.assertContains(page, "You are not a member of this team.", status_code=403)
        self.assertNotContains(page, "ada@example.com", status_code=403)
        self.assertNotContains(page, "Writers", status_code=403)
        requests = [
            (self.url("add-member", self.team.pk), {"email": "cy@example.com"}),
            (self.url("add-member", self.team.pk), {"email": "nobody@example.com"}),
            (self.url("remove-member", self.team.pk, self.ada.pk), {}),
            (self.url("leave", self.team.pk), {}),
        ]
        for url, data in requests:
            with self.subTest(url=url, data=data):
                response = self.client.post(url, data)
                self.assertEqual(response.status_code, 403)
                self.assertNotContains(response, "ada@example.com", status_code=403)
        self.assertEqual(self.members(), before)

    def test_changes_without_csrf_token_are_refused(self):
        client = self.sign_in(self.ada, Client(enforce_csrf_checks=True))
        response = client.post(self.url("remove-member", self.team.pk, self.ben.pk))
        self.assertEqual(response.status_code, 403)
        response = client.post(self.url("create"), {"team-name": "Forged"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.members(), {"ada@example.com", "ben@example.com"})
        self.assertFalse(Team.objects.filter(name="Forged").exists())
