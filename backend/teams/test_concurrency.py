"""Two members changing one team at the same moment, on real PostgreSQL.

SQLite cannot hold row locks between connections, so these tests skip there.
Run them with config.settings_postgres_test; its docstring has the command.
"""

import threading
import time
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase

from . import services
from .models import Team, TeamMembership

ROUNDS = 5
# Holds each change inside its transaction long enough for the other to start.
PAUSE_SECONDS = 0.3


def run_together(*calls):
    """Start the calls at the same moment, each on its own connection. Returns results or errors."""
    barrier = threading.Barrier(len(calls))
    results = [None] * len(calls)

    def run(index, call):
        try:
            barrier.wait()
            results[index] = call()
        except Exception as error:  # noqa: BLE001 - the test inspects it
            results[index] = error
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(i, call)) for i, call in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return results


@skipUnless(connection.vendor == "postgresql", "Needs PostgreSQL row locks.")
class LastMemberConcurrencyTests(TransactionTestCase):
    def setUp(self):
        User = get_user_model()
        self.ada = User.objects.create_user(email="ada@example.com", display_name="Ada")
        self.ben = User.objects.create_user(email="ben@example.com", display_name="Ben")
        original = services._ensure_not_last

        def slow_check(team):
            original(team)
            time.sleep(PAUSE_SECONDS)

        patcher = patch.object(services, "_ensure_not_last", slow_check)
        patcher.start()
        self.addCleanup(patcher.stop)

    def new_team(self):
        team = Team.objects.create(name="Pair")
        TeamMembership.objects.create(team=team, user=self.ada)
        TeamMembership.objects.create(team=team, user=self.ben)
        return team

    def assert_one_left(self, team, results, allowed_errors):
        successes = [r for r in results if not isinstance(r, Exception)]
        errors = [r for r in results if isinstance(r, Exception)]
        self.assertEqual(len(successes), 1, results)
        self.assertEqual(len(errors), 1, results)
        self.assertIsInstance(errors[0], allowed_errors)
        self.assertEqual(TeamMembership.objects.filter(team=team).count(), 1)

    def test_two_members_leaving_together_keep_one(self):
        for _ in range(ROUNDS):
            team = self.new_team()
            results = run_together(
                lambda: services.leave_team(self.ada, team.pk),
                lambda: services.leave_team(self.ben, team.pk),
            )
            self.assert_one_left(team, results, services.LastMember)

    def test_two_members_removing_each_other_keep_one(self):
        for _ in range(ROUNDS):
            team = self.new_team()
            results = run_together(
                lambda: services.remove_member(self.ada, team.pk, self.ben.pk),
                lambda: services.remove_member(self.ben, team.pk, self.ada.pk),
            )
            self.assert_one_left(team, results, services.NotAMember)

    def test_leave_and_remove_together_keep_one(self):
        for _ in range(ROUNDS):
            team = self.new_team()
            results = run_together(
                lambda: services.leave_team(self.ada, team.pk),
                lambda: services.remove_member(self.ben, team.pk, self.ada.pk),
            )
            self.assertEqual(TeamMembership.objects.filter(team=team).count(), 1, results)
            self.assertEqual(
                list(TeamMembership.objects.filter(team=team).values_list("user", flat=True)),
                [self.ben.pk],
            )

    def test_without_the_team_lock_both_could_leave(self):
        """Control: the same race with the lock removed empties the team."""
        team = self.new_team()
        with patch.object(Team.objects, "select_for_update", Team.objects.all):
            results = run_together(
                lambda: services.leave_team(self.ada, team.pk),
                lambda: services.leave_team(self.ben, team.pk),
            )
        self.assertFalse(any(isinstance(r, Exception) for r in results), results)
        self.assertEqual(TeamMembership.objects.filter(team=team).count(), 0)
