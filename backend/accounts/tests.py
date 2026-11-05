from unittest.mock import patch

from django.test import TestCase, TransactionTestCase
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.urls import reverse

from teams.models import Team, TeamMembership

# Create your tests here.


class AccountPageTests(TestCase):
    PASSWORD = "river-window-sunset-947"

    def registration_data(self, **changes):
        return {
            "email": "Writer@Example.COM",
            "display_name": "Writer",
            "password1": self.PASSWORD,
            "password2": self.PASSWORD,
            **changes,
        }

    def create_user(self):
        return get_user_model().objects.create_user(
            email="writer@example.com", display_name="Writer", password=self.PASSWORD
        )

    def test_registration_normalizes_email_creates_workspace_and_logs_in(self):
        response = self.client.post(reverse("accounts:register"), self.registration_data())
        self.assertRedirects(response, "/")
        user = get_user_model().objects.get()
        self.assertEqual(user.email, "writer@example.com")
        self.assertTrue(user.check_password(self.PASSWORD))
        self.assertEqual(Team.objects.get().name, "Writer's team")
        self.assertEqual(TeamMembership.objects.get().user, user)
        self.assertEqual(str(user.pk), self.client.session["_auth_user_id"])

    def test_duplicate_email_is_rejected_without_new_workspace(self):
        self.create_user()
        response = self.client.post(reverse("accounts:register"), self.registration_data())
        self.assertFormError(response.context["form"], "email", "User with this Email already exists.")
        self.assertEqual(get_user_model().objects.count(), 1)
        self.assertFalse(Team.objects.exists())
        self.assertFalse(TeamMembership.objects.exists())

    def test_weak_password_is_rejected(self):
        response = self.client.post(reverse("accounts:register"), self.registration_data(
            password1="123", password2="123"
        ))
        self.assertTrue(response.context["form"].errors["password2"])
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(Team.objects.exists())

    def test_registration_rolls_back_user_and_team_if_membership_fails(self):
        with patch("accounts.views.TeamMembership.objects.create", side_effect=IntegrityError):
            with self.assertRaises(IntegrityError):
                self.client.post(reverse("accounts:register"), self.registration_data())
        self.assertFalse(get_user_model().objects.exists())
        self.assertFalse(Team.objects.exists())

    def test_login_returns_to_next(self):
        self.create_user()
        response = self.client.post(reverse("accounts:login"), {
            "username": "WRITER@example.COM", "password": self.PASSWORD,
            "next": "/?from=login",
        })
        self.assertRedirects(response, "/?from=login")

    def test_login_defaults_to_home_and_rejects_external_next(self):
        self.create_user()
        for next_url in ("", "https://outside.example/"):
            with self.subTest(next_url=next_url):
                self.client.logout()
                response = self.client.post(reverse("accounts:login"), {
                    "username": "writer@example.com", "password": self.PASSWORD,
                    "next": next_url,
                })
                self.assertRedirects(response, "/")

    def test_logged_in_login_page_goes_home_even_with_next(self):
        self.client.force_login(self.create_user())
        self.assertRedirects(self.client.get(reverse("accounts:login"), {"next": "/admin/"}), "/")

    def test_logout_requires_post_and_clears_session(self):
        self.client.force_login(self.create_user())
        for method in ("get", "head", "options", "put", "delete"):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)(reverse("accounts:logout")).status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.client.post(reverse("accounts:logout")), reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertRedirects(self.client.get("/"), "/accounts/login/?next=/")


class UserTests(TestCase):
    def test_create_user_and_authenticate_with_email(self):
        user = get_user_model().objects.create_user(
            email="designer@example.com",
            password="a-test-password-629",
            display_name="Designer",
        )

        self.assertTrue(user.check_password("a-test-password-629"))
        self.assertFalse(user.is_staff)
        self.assertEqual(
            authenticate(email=user.email, password="a-test-password-629"), user
        )
        self.assertIsNone(authenticate(email=user.email, password="incorrect"))

    def test_email_is_unique(self):
        get_user_model().objects.create_user(
            email="designer@example.com", display_name="First"
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            get_user_model().objects.create_user(
                email="designer@example.com", display_name="Second"
            )

    def test_email_capitalization_does_not_create_a_second_account(self):
        user = get_user_model().objects.create_user(
            email="Case@Example.com",
            password="a-test-password-629",
            display_name="First",
        )

        self.assertEqual(user.email, "case@example.com")
        self.assertEqual(
            authenticate(email="CASE@example.COM", password="a-test-password-629"), user
        )
        with self.assertRaises(IntegrityError), transaction.atomic():
            get_user_model().objects.create_user(
                email="case@example.com", display_name="Second"
            )

    def test_email_is_required(self):
        with self.assertRaisesMessage(ValueError, "An email address is required."):
            get_user_model().objects.create_user(email="", display_name="Designer")

    def test_display_name_is_required(self):
        for fields in ({}, {"display_name": ""}, {"display_name": "   "}):
            with self.subTest(fields=fields):
                with self.assertRaisesMessage(ValueError, "A display name is required."):
                    get_user_model().objects.create_user(
                        email="designer@example.com", **fields
                    )
        self.assertFalse(get_user_model().objects.exists())

    def test_create_superuser(self):
        user = get_user_model().objects.create_superuser(
            email="admin@example.com",
            password="an-admin-password-629",
            display_name="Administrator",
        )

        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("an-admin-password-629"))

    def test_admin_creates_and_reads_user(self):
        administrator = get_user_model().objects.create_superuser(
            email="admin@example.com",
            password="an-admin-password-629",
            display_name="Administrator",
        )
        self.client.force_login(administrator)
        add_url = reverse("admin:accounts_user_add")
        self.assertEqual(self.client.get(add_url).status_code, 200)

        response = self.client.post(
            add_url,
            {
                "email": "reviewer@example.com",
                "display_name": "Reviewer",
                "usable_password": "true",
                "password1": "a-reviewer-password-629",
                "password2": "a-reviewer-password-629",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)
        user = get_user_model().objects.get(email="reviewer@example.com")
        self.assertEqual(user.display_name, "Reviewer")
        self.assertTrue(user.check_password("a-reviewer-password-629"))
        detail = self.client.get(reverse("admin:accounts_user_change", args=[user.pk]))
        self.assertContains(detail, "reviewer@example.com")
        self.assertContains(detail, "Reviewer")


class LowercaseEmailsMigrationTests(TransactionTestCase):
    BEFORE = ("accounts", "0001_initial")
    AFTER = ("accounts", "0002_lowercase_existing_emails")
    PASSWORD = "a-test-password-629"

    def setUp(self):
        self.migrate_to(self.BEFORE)
        self.addCleanup(self.migrate_to, self.AFTER)

    def migrate_to(self, migration):
        MigrationExecutor(connection).migrate([migration])

    def add_old_account(self, email):
        """Store an account the way it was before this migration, without lowercasing."""
        state = MigrationExecutor(connection).loader.project_state([self.BEFORE])
        return state.apps.get_model("accounts", "User").objects.create(
            email=email, display_name="Designer", password=make_password(self.PASSWORD)
        )

    def stored_emails(self):
        return set(get_user_model().objects.values_list("email", flat=True))

    def test_account_with_capitals_can_log_in_after_migrating(self):
        account = self.add_old_account("Name@Example.COM")
        self.add_old_account("lower@example.com")

        self.migrate_to(self.AFTER)

        self.assertEqual(self.stored_emails(), {"name@example.com", "lower@example.com"})
        self.assertEqual(
            authenticate(email="Name@Example.COM", password=self.PASSWORD).pk, account.pk
        )

    def test_accounts_differing_only_by_capitalization_stop_the_migration(self):
        emails = {"Name@Example.com", "name@example.com", "Other@Example.com"}
        for email in emails:
            self.add_old_account(email)

        with self.assertRaisesMessage(ValueError, "Name@Example.com, name@example.com"):
            self.migrate_to(self.AFTER)

        self.assertEqual(self.stored_emails(), emails)
        self.assertNotIn(self.AFTER, MigrationRecorder(connection).applied_migrations())
        # Let the cleanup finish the migration.
        get_user_model().objects.filter(email="Name@Example.com").delete()

    def test_reversing_the_migration_changes_nothing(self):
        self.migrate_to(self.AFTER)
        get_user_model().objects.create_user(
            email="name@example.com", display_name="Designer"
        )

        self.migrate_to(self.BEFORE)

        self.assertEqual(self.stored_emails(), {"name@example.com"})
