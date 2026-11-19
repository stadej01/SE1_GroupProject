"""Put files back from a manifest with a new commit, for recovering from a failed reset.

Restore the database from the reset's backup with pg_restore as well, so that
the two sides match. Saved versions are read through the database's commit SHAs.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from projects.reset import Repository, ResetError, check_target, restore_files

from ._reset_target import add_target_arguments


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        add_target_arguments(parser)
        parser.add_argument("--manifest", required=True, help="From reset_inventory")

    def handle(self, *args, **options):
        manifest = json.loads(Path(options["manifest"]).read_text())
        try:
            check_target(
                options["database_host"],
                options["database_name"],
                options["repository"],
                options["branch"],
            )
            commit = restore_files(Repository(), manifest)
        except ResetError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(self.style.SUCCESS(f"Files restored in commit {commit}."))
