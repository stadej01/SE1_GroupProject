"""List exactly what a reset of the named target would clear. Changes nothing."""

import os
import subprocess

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from projects.reset import Repository, ResetError, build_inventory, check_target, file_sha256

from ._reset_target import add_target_arguments, outside_repository, write_private_json


def dump_database(path):
    """Back the database up with pg_dump, passing the password out of its arguments."""
    database = connection.settings_dict
    environment = {
        **os.environ,
        "PGHOST": database["HOST"],
        "PGPORT": str(database["PORT"] or 5432),
        "PGDATABASE": database["NAME"],
        "PGUSER": database["USER"],
        "PGPASSWORD": database["PASSWORD"] or "",
        "PGSSLMODE": database["OPTIONS"].get("sslmode", "prefer"),
    }
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    result = subprocess.run(
        ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", f"--file={path}"],
        env=environment,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise CommandError(f"pg_dump failed: {result.stderr.strip()}")


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        add_target_arguments(parser)
        parser.add_argument("--output", required=True, help="Manifest to write, as JSON")
        parser.add_argument("--backup", help="Also write a pg_dump backup to this file")

    def handle(self, *args, **options):
        manifest_path = outside_repository(options["output"])
        backup_path = outside_repository(options["backup"]) if options["backup"] else None
        try:
            check_target(
                options["database_host"],
                options["database_name"],
                options["repository"],
                options["branch"],
            )
            manifest = build_inventory(Repository())
        except ResetError as error:
            raise CommandError(str(error)) from error

        # reset_dialogue_data --execute checks that this backup is still there, unchanged.
        manifest["backup"] = None
        if backup_path:
            dump_database(backup_path)
            manifest["backup"] = {"path": str(backup_path), "sha256": file_sha256(backup_path)}
        write_private_json(manifest_path, manifest)

        self.stdout.write(f"Database: {options['database_host']} / {options['database_name']}")
        self.stdout.write(f"Repository: {options['repository']} @ {options['branch']}")
        self.stdout.write(f"Branch HEAD: {manifest['head']}")
        self.stdout.write("Rows to clear:")
        for table in manifest["tables_to_clear"]:
            self.stdout.write(f"  {table}: {manifest['tables'][table]}")
        self.stdout.write(f"Files to delete: {len(manifest['files_to_delete'])}")
        self.stdout.write(f"Files to keep: {sorted(manifest['files_to_keep'])}")
        for label, key in (
            ("Unclassified tables", "unclassified_tables"),
            ("Unapplied migrations", "unapplied_migrations"),
            ("Saved paths missing from the branch", "saved_paths_missing_from_branch"),
        ):
            if manifest[key]:
                self.stdout.write(self.style.WARNING(f"{label}: {manifest[key]}"))
        self.stdout.write(f"Manifest: {manifest_path}")
        if backup_path:
            self.stdout.write(f"Backup: {backup_path}")
        else:
            self.stdout.write(
                self.style.WARNING("No backup: reset_dialogue_data --execute will refuse this manifest.")
            )
