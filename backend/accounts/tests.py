from django.test import TestCase, TransactionTestCase
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.hashers import make_password
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
from django.urls import reverse

# Create your tests here.


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
