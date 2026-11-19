"""Storage for each project's Markdown source and its saved versions."""

import base64
import hashlib
import json
import threading
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import OperationalError, connection

GITHUB_API = "https://api.github.com"
# How long a save waits for other saves to the same branch to finish.
WRITE_LOCK_TIMEOUT_MS = 15_000
POSTGRES_LOCK_NOT_AVAILABLE = "55P03"


class ContentStoreError(Exception):
    """The Markdown store could not complete a read or write."""


class InMemoryContentStore:
    """Keeps saved Markdown in process memory, one entry per saved version.

    It stands in for the GitHub repository: ``write`` returns a commit-style
    SHA, and ``read`` returns the version that SHA names.
    """

    def __init__(self):
        self._versions = {}

    def write(self, path, content, message, author=None):
        seed = f"{path}\n{len(self._versions)}\n{message}\n{content}"
        sha = hashlib.sha1(seed.encode()).hexdigest()
        self._versions[sha] = (path, content)
        return sha

    def read(self, path, sha):
        stored = self._versions.get(sha)
        if stored is None or stored[0] != path:
            raise ContentStoreError(f"No saved version {sha} of {path}.")
        return stored[1]


class GitHubContentStore:
    """Keeps each project's Markdown as a file in a private GitHub repository.

    ``write`` commits the file to the configured branch and returns the
    commit's SHA, and ``read`` returns the file as it was in that commit.
    Writes to one branch run one at a time, because concurrent commits to a
    branch conflict: a PostgreSQL advisory lock covers every backend that
    shares the database, and a process lock covers threads on other databases.
    """

    _write_lock = threading.Lock()

    def __init__(self, repository, token, branch="main", timeout=5):
        self.repository = repository
        self.token = token
        self.branch = branch
        self.timeout = timeout

    def write(self, path, content, message, author=None):
        body = {
            "message": message,
            "content": base64.b64encode(content.encode()).decode(),
            "branch": self.branch,
        }
        if author is not None:
            body["author"] = author
        self._lock_branch_until_transaction_ends()
        with self._write_lock:
            current = self._request("GET", path, ref=self.branch, missing_ok=True)
            if current is not None:
                body["sha"] = json.loads(current)["sha"]
            result = self._request("PUT", path, body=body)
        return json.loads(result)["commit"]["sha"]

    def read(self, path, sha):
        return self._request("GET", path, ref=sha, raw=True).decode()

    def write_lock_key(self):
        """A 64-bit lock key for this branch, the same in every process."""
        scope = f"{self.repository.strip().lower()}\0{self.branch.strip()}"
        digest = hashlib.sha256(scope.encode()).digest()
        return int.from_bytes(digest[:8], "big", signed=True)

    def _lock_branch_until_transaction_ends(self):
        if connection.vendor != "postgresql":
            return
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT set_config('lock_timeout', %s, true)",
                [f"{WRITE_LOCK_TIMEOUT_MS}ms"],
            )
            try:
                cursor.execute(
                    "SELECT pg_advisory_xact_lock(%s)", [self.write_lock_key()]
                )
            except OperationalError as error:
                if getattr(error.__cause__, "sqlstate", "") == POSTGRES_LOCK_NOT_AVAILABLE:
                    raise ContentStoreError(
                        "Timed out waiting for another save to this branch."
                    ) from error
                raise
            cursor.execute("SET LOCAL lock_timeout TO DEFAULT")

    def _request(self, method, path, ref=None, body=None, raw=False, missing_ok=False):
        url = f"{GITHUB_API}/repos/{self.repository}/contents/{quote(path)}"
        if ref is not None:
            url += f"?ref={quote(ref, safe='')}"
        media_type = "raw+json" if raw else "json"
        headers = {
            "Accept": f"application/vnd.github.{media_type}",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"

        request = Request(url, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except HTTPError as error:
            if missing_ok and error.code == 404:
                return None
            raise ContentStoreError(
                f"GitHub answered {error.code} to {method} {path}."
            ) from error
        except OSError as error:
            raise ContentStoreError(f"GitHub is unreachable: {error}") from error


_store = InMemoryContentStore()


def get_content_store():
    """Return the store that settings name. Only test settings choose memory."""
    if settings.CONTENT_STORE == "memory":
        return _store
    return GitHubContentStore(
        settings.GITHUB_REPOSITORY, settings.GITHUB_TOKEN, settings.GITHUB_BRANCH
    )
