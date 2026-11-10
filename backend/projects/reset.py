"""Inventory and reset of one environment's application data.

Only the management commands that name a target explicitly use this module.
The app, its setup and start scripts, and its migrations never do.
"""

import hashlib
import json
import re
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor

from .models import Project
from .storage import GITHUB_API

RESET_COMMIT_MESSAGE = "chore(storage): reset dialogue data for Sprint 4"
RESTORE_COMMIT_MESSAGE = "chore(storage): restore dialogue data after reset"

# Cleared one at a time, children first. A table that also references something
# not listed here makes its DELETE fail and rolls the whole reset back.
BUSINESS_TABLES = (
    "django_admin_log",
    "django_session",
    "projects_nodeposition",
    "projects_project",
    "teams_teammembership",
    "teams_team",
    "accounts_user_groups",
    "accounts_user_user_permissions",
    "accounts_user",
)
FRAMEWORK_TABLES = (
    "auth_group",
    "auth_group_permissions",
    "auth_permission",
    "django_content_type",
    "django_migrations",
)

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
APP_FILE = re.compile(rf"^(teams/\d+/)?projects/{_UUID}\.md$")


class ResetError(Exception):
    """The reset must stop here; the message says what to check."""


def check_target(database_host, database_name, repository, branch):
    """The caller names its target; the loaded configuration must be that target."""
    database = connection.settings_dict
    expected = {
        "database host": (database_host, database["HOST"]),
        "database name": (database_name, database["NAME"]),
        "repository": (repository, settings.GITHUB_REPOSITORY),
        "branch": (branch, settings.GITHUB_BRANCH),
    }
    different = [name for name, (given, loaded) in expected.items() if given != loaded]
    if different:
        raise ResetError(
            f"The loaded configuration does not match the named {', '.join(different)}."
        )


class Repository:
    """The Git operations a reset needs, on the configured repository and branch."""

    def __init__(self, repository=None, token=None, branch=None, timeout=20):
        self.repository = repository or settings.GITHUB_REPOSITORY
        self.token = token or settings.GITHUB_TOKEN
        self.branch = branch or settings.GITHUB_BRANCH
        self.timeout = timeout

    def _request(self, method, path, body=None):
        request = Request(
            f"{GITHUB_API}/repos/{self.repository}/{path}",
            data=None if body is None else json.dumps(body).encode(),
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return json.load(response)
        except HTTPError as error:
            raise ResetError(f"GitHub answered {error.code} to {method} {path}.") from error
        except OSError as error:
            raise ResetError(
                f"GitHub did not answer {method} {path}: {error}. "
                "The request may still have succeeded: check the branch before retrying."
            ) from error

    def head(self):
        ref = self._request("GET", f"git/ref/heads/{quote(self.branch, safe='')}")
        return ref["object"]["sha"]

    def tree_sha(self, commit_sha):
        return self._request("GET", f"git/commits/{commit_sha}")["tree"]["sha"]

    def files(self, commit_sha):
        """Every file at this commit, as {path: {"blob_sha": ..., "mode": ...}}."""
        tree = self._request("GET", f"git/trees/{commit_sha}?recursive=1")
        if tree.get("truncated"):
            raise ResetError("GitHub truncated the file list, so it cannot be trusted.")
        return {
            item["path"]: {"blob_sha": item["sha"], "mode": item["mode"]}
            for item in tree["tree"]
            if item["type"] == "blob"
        }

    def commit_tree_changes(self, parent, changes, message):
        """Add one ordinary commit on top of ``parent``; never overwrite the branch."""
        tree = self._request(
            "POST", "git/trees", {"base_tree": self.tree_sha(parent), "tree": changes}
        )
        commit = self._request(
            "POST",
            "git/commits",
            {"message": message, "tree": tree["sha"], "parents": [parent]},
        )
        self._request(
            "PATCH",
            f"git/refs/heads/{quote(self.branch, safe='')}",
            {"sha": commit["sha"], "force": False},
        )
        return commit["sha"]


def classify_files(files, project_paths):
    """Only files the app wrote are cleared; every other file stays and is listed."""
    delete, keep = {}, []
    for path, file in sorted(files.items()):
        if path in project_paths or APP_FILE.match(path):
            delete[path] = file
        else:
            keep.append(path)
    return delete, keep


def _table_counts(cursor):
    cursor.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE' "
        "ORDER BY table_name"
    )
    counts = {}
    for (table,) in cursor.fetchall():
        cursor.execute(f"SELECT count(*) FROM {connection.ops.quote_name(table)}")
        counts[table] = cursor.fetchone()[0]
    return counts


def _sequences(cursor):
    cursor.execute(
        "SELECT sequencename, last_value FROM pg_sequences "
        "WHERE schemaname = current_schema() AND last_value IS NOT NULL "
        "ORDER BY sequencename"
    )
    return dict(cursor.fetchall())


def _unapplied_migrations():
    executor = MigrationExecutor(connection)
    plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
    return [str(migration) for migration, _ in plan]


def build_inventory(repository):
    """A read-only list of the target. It holds no credentials and no Markdown."""
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("SELECT current_schema()")
            schema = cursor.fetchone()[0]
            tables = _table_counts(cursor)
            sequences = _sequences(cursor)
        projects = [
            {
                "id": str(project["id"]),
                "github_path": project["github_path"],
                "head_commit_sha": project["head_commit_sha"],
                "revision": project["revision"],
            }
            for project in Project.objects.values(
                "id", "github_path", "head_commit_sha", "revision"
            ).order_by("created_at")
        ]

    head = repository.head()
    files = repository.files(head)
    project_paths = {project["github_path"] for project in projects}
    delete, keep = classify_files(files, project_paths)
    return {
        "database": {
            "host": connection.settings_dict["HOST"],
            "name": connection.settings_dict["NAME"],
            "schema": schema,
        },
        "unapplied_migrations": _unapplied_migrations(),
        "tables": tables,
        "tables_to_clear": [table for table in BUSINESS_TABLES if table in tables],
        "unclassified_tables": sorted(
            set(tables) - set(BUSINESS_TABLES) - set(FRAMEWORK_TABLES)
        ),
        "sequences": sequences,
        "projects": projects,
        "repository": {"name": repository.repository, "branch": repository.branch},
        "head": head,
        "files_to_delete": delete,
        "files_to_keep": {path: files[path] for path in keep},
        "saved_paths_missing_from_branch": sorted(
            project["github_path"]
            for project in projects
            if project["head_commit_sha"] and project["github_path"] not in files
        ),
    }


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as backup:
        for chunk in iter(lambda: backup.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_backup(manifest):
    """A reset deletes every account, so it needs the inventory's backup, unchanged."""
    backup = manifest.get("backup")
    if not backup:
        raise ResetError("The manifest records no backup. Run reset_inventory again with --backup.")
    path = Path(backup["path"])
    if not path.is_file():
        raise ResetError(f"The backup {path} is missing. Run reset_inventory again with --backup.")
    if file_sha256(path) != backup["sha256"]:
        raise ResetError(
            f"The backup {path} changed after the inventory. Run reset_inventory again with --backup."
        )


def _check_still_matches(manifest, current):
    if current != manifest:
        different = sorted(key for key in manifest if manifest[key] != current.get(key))
        raise ResetError(
            f"The target changed after the inventory ({', '.join(different)}). "
            "Stop writers and take a new inventory."
        )
    if current["unclassified_tables"]:
        raise ResetError(
            "Decide who owns these tables first: " + ", ".join(current["unclassified_tables"])
        )
    if current["unapplied_migrations"]:
        raise ResetError("The target has unapplied migrations. Resolve them first.")


def delete_files(repository, manifest):
    """Commit the removal, then prove the result. Returns the new commit, if any."""
    head = manifest["head"]
    delete = manifest["files_to_delete"]
    if not delete:
        return None
    changes = [
        {"path": path, "mode": file["mode"], "type": "blob", "sha": None}
        for path, file in delete.items()
    ]
    commit = repository.commit_tree_changes(head, changes, RESET_COMMIT_MESSAGE)

    remaining = repository.files(commit)
    still_there = sorted(set(delete) & set(remaining))
    if still_there:
        raise ResetError(f"These files are still on the branch: {', '.join(still_there)}")
    if remaining != manifest["files_to_keep"]:
        raise ResetError("A file that should have stayed was changed. Database not cleared.")
    if not set(delete) <= set(repository.files(head)):
        raise ResetError("The old commit no longer shows the deleted files.")
    return commit


def clear_database(manifest):
    """Clear the listed tables in one transaction; any failure leaves them all."""
    with transaction.atomic():
        with connection.cursor() as cursor:
            for table in manifest["tables_to_clear"]:
                cursor.execute(f"DELETE FROM {connection.ops.quote_name(table)}")
            counts = _table_counts(cursor)
            sequences = _sequences(cursor)
        not_empty = [table for table in manifest["tables_to_clear"] if counts[table]]
        if not_empty:
            raise ResetError(f"Rows remain in: {', '.join(not_empty)}")
        for table in FRAMEWORK_TABLES:
            if table in counts and counts[table] != manifest["tables"][table]:
                raise ResetError(f"{table} changed. Nothing was cleared.")
        for name, value in manifest["sequences"].items():
            if sequences.get(name, value) < value:
                raise ResetError(f"Sequence {name} went backwards. Nothing was cleared.")
    return {"tables": counts, "sequences": sequences}


def reset(repository, manifest):
    """Check the backup, re-check the target, delete the files, then clear the database.

    Any failure stops the reset there.
    """
    check_backup(manifest)
    inventory = {key: value for key, value in manifest.items() if key != "backup"}
    _check_still_matches(inventory, build_inventory(repository))
    commit = delete_files(repository, manifest)
    database = clear_database(manifest)
    return {
        "head_before": manifest["head"],
        "reset_commit": commit,
        "deleted_files": sorted(manifest["files_to_delete"]),
        **database,
    }


def restore_files(repository, manifest):
    """Put the deleted files back with a new commit; history stays as it is."""
    changes = [
        {"path": path, "mode": file["mode"], "type": "blob", "sha": file["blob_sha"]}
        for path, file in manifest["files_to_delete"].items()
    ]
    return repository.commit_tree_changes(
        repository.head(), changes, RESTORE_COMMIT_MESSAGE
    )
