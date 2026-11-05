"""Clear the application data listed in a reviewed manifest. Run only by hand."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from projects.reset import Repository, ResetError, check_target, reset

from ._reset_target import add_target_arguments, outside_repository, write_private_json


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        add_target_arguments(parser)
        parser.add_argument("--manifest", required=True, help="From reset_inventory")
        parser.add_argument("--result", required=True, help="Result to write, as JSON")
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Without this flag, nothing is changed.",
        )

    def handle(self, *args, **options):
        result_path = outside_repository(options["result"])
        manifest = json.loads(Path(options["manifest"]).read_text())
        try:
            check_target(
                options["database_host"],
                options["database_name"],
                options["repository"],
                options["branch"],
            )
            if not options["execute"]:
                self.stdout.write(
                    "Would delete "
                    f"{len(manifest['files_to_delete'])} files and clear "
                    f"{', '.join(manifest['tables_to_clear'])}. Add --execute to do it."
                )
                return
            result = reset(Repository(), manifest)
        except ResetError as error:
            raise CommandError(str(error)) from error

        write_private_json(result_path, result)
        self.stdout.write(self.style.SUCCESS("Reset finished."))
        self.stdout.write(f"Reset commit: {result['reset_commit']}")
        self.stdout.write(f"Files deleted: {len(result['deleted_files'])}")
        for table in manifest["tables_to_clear"]:
            self.stdout.write(f"  {table}: {result['tables'][table]}")
        self.stdout.write(f"Result: {result_path}")
