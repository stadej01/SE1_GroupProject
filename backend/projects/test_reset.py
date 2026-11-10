"""Rules of the reset tools. Their real effect is rehearsed on PostgreSQL and GitHub."""

import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from .reset import (
    BUSINESS_TABLES,
    FRAMEWORK_TABLES,
    RESET_COMMIT_MESSAGE,
    ResetError,
    _check_still_matches,
    check_backup,
    check_target,
    classify_files,
    delete_files,
    file_sha256,
    reset,
)

UUID = "3f2a9c1b-7d10-4e55-9aca-7749e5f6bba1"
TEAM_FILE = f"teams/12/projects/{UUID}.md"
OLD_FILE = f"projects/{UUID}.md"


def file(sha="a" * 40):
    return {"blob_sha": sha, "mode": "100644"}


class ClassifyFilesTests(SimpleTestCase):
    def test_only_files_the_app_wrote_are_deleted(self):
        files = {
            TEAM_FILE: file(),
            OLD_FILE: file(),
            "README.md": file(),
            "docs/notes.md": file(),
            "projects/readme.md": file(),
            f"elsewhere/projects/{UUID}.md": file(),
            f"teams/x/projects/{UUID}.md": file(),
        }

        delete, keep = classify_files(files, project_paths=set())

        self.assertEqual(set(delete), {TEAM_FILE, OLD_FILE})
        self.assertEqual(
            keep,
            sorted(
                [
                    "README.md",
                    "docs/notes.md",
                    "projects/readme.md",
                    f"elsewhere/projects/{UUID}.md",
                    f"teams/x/projects/{UUID}.md",
                ]
            ),
        )

    def test_a_path_a_project_row_names_is_deleted_whatever_it_looks_like(self):
        delete, keep = classify_files(
            {"odd/name.md": file(), "README.md": file()}, {"odd/name.md"}
        )

        self.assertEqual(set(delete), {"odd/name.md"})
        self.assertEqual(keep, ["README.md"])


class ClearedTablesTests(SimpleTestCase):
    def test_framework_definitions_are_never_cleared(self):
        self.assertEqual(set(BUSINESS_TABLES) & set(FRAMEWORK_TABLES), set())
        self.assertIn("django_migrations", FRAMEWORK_TABLES)
        self.assertIn("auth_permission", FRAMEWORK_TABLES)
        self.assertIn("django_content_type", FRAMEWORK_TABLES)


@override_settings(GITHUB_REPOSITORY="team6/content", GITHUB_BRANCH="main")
class CheckTargetTests(SimpleTestCase):
    def loaded_database(self):
        return mock.patch(
            "projects.reset.connection",
            mock.Mock(settings_dict={"HOST": "db.example", "NAME": "appdb"}),
        )

    def test_matching_target_passes(self):
        with self.loaded_database():
            check_target("db.example", "appdb", "team6/content", "main")

    def test_any_difference_stops_and_names_what_differs(self):
        cases = {
            "database host": ("other.example", "appdb", "team6/content", "main"),
            "database name": ("db.example", "other", "team6/content", "main"),
            "repository": ("db.example", "appdb", "team6/other", "main"),
            "branch": ("db.example", "appdb", "team6/content", "drafts"),
        }
        for name, target in cases.items():
            with self.subTest(name=name), self.loaded_database():
                with self.assertRaisesMessage(ResetError, name):
                    check_target(*target)


class ManifestCheckTests(SimpleTestCase):
    MANIFEST = {
        "head": "a" * 40,
        "tables": {"accounts_user": 4},
        "unclassified_tables": [],
        "unapplied_migrations": [],
    }

    def test_unchanged_target_passes(self):
        _check_still_matches(self.MANIFEST, dict(self.MANIFEST))

    def test_a_changed_target_stops_the_reset(self):
        cases = {
            "head": {"head": "b" * 40},
            "tables": {"tables": {"accounts_user": 5}},
        }
        for name, change in cases.items():
            with self.subTest(name=name):
                with self.assertRaisesMessage(ResetError, name):
                    _check_still_matches(self.MANIFEST, {**self.MANIFEST, **change})

    def test_unknown_tables_and_pending_migrations_stop_the_reset(self):
        for key, value in (
            ("unclassified_tables", ["old_demo"]),
            ("unapplied_migrations", ["projects.0002"]),
        ):
            with self.subTest(key=key):
                manifest = {**self.MANIFEST, key: value}
                with self.assertRaises(ResetError):
                    _check_still_matches(manifest, dict(manifest))


class DeleteFilesTests(SimpleTestCase):
    MANIFEST = {
        "head": "a" * 40,
        "files_to_delete": {TEAM_FILE: file("1" * 40)},
        "files_to_keep": {"README.md": file("2" * 40)},
    }

    def repository(self, after=None):
        repository = mock.Mock()
        repository.commit_tree_changes.return_value = "c" * 40
        repository.files.side_effect = lambda commit: (
            {**self.MANIFEST["files_to_delete"], **self.MANIFEST["files_to_keep"]}
            if commit == "a" * 40
            else (self.MANIFEST["files_to_keep"] if after is None else after)
        )
        return repository

    def test_one_ordinary_commit_on_the_listed_head_removes_only_listed_files(self):
        repository = self.repository()

        self.assertEqual(delete_files(repository, self.MANIFEST), "c" * 40)

        repository.commit_tree_changes.assert_called_once_with(
            "a" * 40,
            [{"path": TEAM_FILE, "mode": "100644", "type": "blob", "sha": None}],
            RESET_COMMIT_MESSAGE,
        )

    def test_nothing_to_delete_makes_no_commit(self):
        repository = self.repository()

        result = delete_files(repository, {**self.MANIFEST, "files_to_delete": {}})

        self.assertIsNone(result)
        repository.commit_tree_changes.assert_not_called()

    def test_a_file_left_behind_stops_before_the_database(self):
        left_behind = {**self.MANIFEST["files_to_keep"], TEAM_FILE: file("1" * 40)}

        with self.assertRaisesMessage(ResetError, TEAM_FILE):
            delete_files(self.repository(after=left_behind), self.MANIFEST)

    def test_a_changed_kept_file_stops_before_the_database(self):
        with self.assertRaisesMessage(ResetError, "should have stayed"):
            delete_files(
                self.repository(after={"README.md": file("9" * 40)}), self.MANIFEST
            )


class CommandSafetyTests(SimpleTestCase):
    TARGET = {
        "database_host": "db.example",
        "database_name": "appdb",
        "repository": "team6/content",
        "branch": "main",
    }

    def test_manifest_inside_the_source_repository_is_refused(self):
        inside = Path(settings.BASE_DIR).parent / "manifest.json"

        with self.assertRaisesMessage(CommandError, "outside the source repository"):
            call_command("reset_inventory", output=str(inside), **self.TARGET)

    def test_without_execute_nothing_runs(self):
        with TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text(
                json.dumps({"files_to_delete": {TEAM_FILE: file()}, "tables_to_clear": ["accounts_user"]})
            )
            output = StringIO()
            with (
                mock.patch("projects.management.commands.reset_dialogue_data.check_target"),
                mock.patch("projects.management.commands.reset_dialogue_data.reset") as reset,
            ):
                call_command(
                    "reset_dialogue_data",
                    manifest=str(manifest),
                    result=str(Path(directory) / "result.json"),
                    stdout=output,
                    **self.TARGET,
                )

        reset.assert_not_called()
        self.assertIn("Add --execute", output.getvalue())

    def test_a_wrong_target_stops_the_reset(self):
        with TemporaryDirectory() as directory:
            manifest = Path(directory) / "manifest.json"
            manifest.write_text("{}")
            with (
                mock.patch(
                    "projects.management.commands.reset_dialogue_data.check_target",
                    side_effect=ResetError("does not match"),
                ),
                mock.patch("projects.management.commands.reset_dialogue_data.reset") as reset,
                self.assertRaisesMessage(CommandError, "does not match"),
            ):
                call_command(
                    "reset_dialogue_data",
                    manifest=str(manifest),
                    result=str(Path(directory) / "result.json"),
                    execute=True,
                    **self.TARGET,
                )

        reset.assert_not_called()


class BackupRequiredTests(SimpleTestCase):
    """A reset deletes every account, so --execute needs the inventory's backup."""

    INVENTORY = {
        "head": "a" * 40,
        "tables": {"accounts_user": 2},
        "files_to_delete": {TEAM_FILE: file()},
        "unclassified_tables": [],
        "unapplied_migrations": [],
    }
    TARGET = CommandSafetyTests.TARGET

    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.backup = self.directory / "backup.dump"
        self.backup.write_bytes(b"pg_dump output")

    def manifest(self, **backup):
        recorded = {"path": str(self.backup), "sha256": file_sha256(self.backup), **backup}
        return {**self.INVENTORY, "backup": recorded}

    def steps(self):
        """The reset's real work, replaced so the test can see whether it ran."""
        return (
            mock.patch("projects.reset.build_inventory", return_value=dict(self.INVENTORY)),
            mock.patch("projects.reset.delete_files", return_value="c" * 40),
            mock.patch("projects.reset.clear_database", return_value={"tables": {}, "sequences": {}}),
        )

    def assert_refused(self, manifest, message):
        inventory, delete, clear = self.steps()
        with inventory as read, delete as deleted, clear as cleared:
            with self.assertRaisesMessage(ResetError, message):
                reset(mock.Mock(), manifest)
        read.assert_not_called()
        deleted.assert_not_called()
        cleared.assert_not_called()

    def test_no_recorded_backup_stops_before_anything_changes(self):
        for manifest in (dict(self.INVENTORY), {**self.INVENTORY, "backup": None}):
            with self.subTest(backup=manifest.get("backup", "absent")):
                self.assert_refused(manifest, "records no backup")

    def test_a_missing_or_changed_backup_stops_before_anything_changes(self):
        cases = {
            "missing": ({"path": str(self.directory / "gone.dump")}, "is missing"),
            "changed": ({"sha256": "0" * 64}, "changed after the inventory"),
        }
        for name, (change, message) in cases.items():
            with self.subTest(name=name):
                self.assert_refused(self.manifest(**change), message)

    def test_the_recorded_backup_lets_the_reset_run(self):
        inventory, delete, clear = self.steps()
        with inventory, delete as deleted, clear as cleared:
            result = reset(mock.Mock(), self.manifest())
        deleted.assert_called_once()
        cleared.assert_called_once()
        self.assertEqual(result["reset_commit"], "c" * 40)

    def call_reset_command(self, manifest, **options):
        manifest_path = self.directory / "manifest.json"
        manifest_path.write_text(json.dumps({**manifest, "tables_to_clear": ["accounts_user"]}))
        output = StringIO()
        with mock.patch("projects.management.commands.reset_dialogue_data.check_target"):
            call_command(
                "reset_dialogue_data",
                manifest=str(manifest_path),
                result=str(self.directory / "result.json"),
                stdout=output,
                **self.TARGET,
                **options,
            )
        return output.getvalue()

    def test_execute_without_a_backup_is_refused_by_the_command(self):
        inventory, delete, clear = self.steps()
        with inventory, delete as deleted, clear as cleared:
            with self.assertRaisesMessage(CommandError, "records no backup"):
                self.call_reset_command(self.INVENTORY, execute=True)
        deleted.assert_not_called()
        cleared.assert_not_called()

    def test_preview_without_a_backup_still_works_and_warns(self):
        with mock.patch("projects.management.commands.reset_dialogue_data.reset") as run:
            output = self.call_reset_command(self.INVENTORY)
        run.assert_not_called()
        self.assertIn("Add --execute", output)
        self.assertIn("--execute will refuse", output)

    def call_inventory_command(self, **options):
        inventory = {
            **self.INVENTORY,
            "tables_to_clear": [],
            "files_to_keep": {},
            "saved_paths_missing_from_branch": [],
        }
        command = "projects.management.commands.reset_inventory"
        output = StringIO()
        with (
            mock.patch(f"{command}.check_target"),
            mock.patch(f"{command}.Repository"),
            mock.patch(f"{command}.build_inventory", return_value=inventory),
            mock.patch(
                f"{command}.dump_database",
                side_effect=lambda path: path.write_bytes(b"pg_dump output"),
            ),
        ):
            call_command(
                "reset_inventory",
                output=str(self.directory / "manifest.json"),
                stdout=output,
                **self.TARGET,
                **options,
            )
        return json.loads((self.directory / "manifest.json").read_text()), output.getvalue()

    def test_inventory_records_the_backup_path_and_hash(self):
        backup = (self.directory / "new-backup.dump").resolve()
        manifest, _ = self.call_inventory_command(backup=str(backup))
        self.assertEqual(manifest["backup"], {"path": str(backup), "sha256": file_sha256(backup)})
        check_backup(manifest)

    def test_inventory_without_backup_records_none_and_warns(self):
        manifest, output = self.call_inventory_command()
        self.assertIsNone(manifest["backup"])
        self.assertIn("--execute will refuse this manifest", output)
