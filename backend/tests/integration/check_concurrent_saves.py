"""Saves from separate backend processes, on real PostgreSQL and a real test branch.

SQLite and threads cannot prove these locks. From backend/, with the environment
active, a local empty PostgreSQL database, and an existing test branch:

    export INTEGRATION_DATABASE_URL=postgresql://user@127.0.0.1:5432/empty_database
    export INTEGRATION_GITHUB_REPOSITORY=owner/private-test-repository
    export INTEGRATION_GITHUB_TOKEN=...
    export INTEGRATION_GITHUB_BRANCH=test-branch
    python tests/integration/check_concurrent_saves.py

Never point these at a database or branch that holds real data.
"""

import argparse
import http.cookiejar
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))

PASSWORD = f"integration-{uuid.uuid4()}"
PORTS = (8791, 8792)
LOCK_TIMEOUT_SECONDS = 15


class Backend:
    """One signed-in browser against one backend process."""

    def __init__(self, port, email):
        self.base = f"http://127.0.0.1:{port}"
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookies)
        )
        # Like the login page: get the CSRF cookie, then sign in with the token,
        # so the login API also sets the sign-in cookie.
        self.opener.open(f"{self.base}/accounts/login/", timeout=30).read()
        status, body = self.call(
            "POST", "/api/v1/auth/login", {"email": email, "password": PASSWORD}
        )
        signed_in = any(c.name == "se1_neon_token" for c in self.cookies)
        assert status == 200 and signed_in, (status, body)

    def csrf(self):
        return next(c.value for c in self.cookies if c.name == "se1_neon_csrftoken")

    def call(self, method, path, body=None):
        request = urllib.request.Request(
            f"{self.base}{path}",
            data=None if body is None else json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "X-CSRFToken": self.csrf()},
            method=method,
        )
        try:
            with self.opener.open(request, timeout=90) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.load(error)

    def create(self, name, team_id):
        status, body = self.call(
            "POST", "/api/v1/projects", {"name": name, "team_id": team_id}
        )
        assert status == 201, (status, body)
        return body["project_id"]

    def save(self, project_id, markdown, base_revision):
        return self.call(
            "PUT",
            f"/api/v1/projects/{project_id}/save",
            {
                "markdown_source": markdown,
                "layout_data": {"nodes": []},
                "base_revision": base_revision,
            },
        )

    def open(self, project_id):
        return self.call("GET", f"/api/v1/projects/{project_id}")


class GitHub:
    def __init__(self):
        self.repository = os.environ["INTEGRATION_GITHUB_REPOSITORY"]
        self.token = os.environ["INTEGRATION_GITHUB_TOKEN"]
        self.branch = os.environ["INTEGRATION_GITHUB_BRANCH"]

    def get(self, path):
        request = urllib.request.Request(
            f"https://api.github.com/repos/{self.repository}/{path}",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)

    def head(self):
        return self.get(f"git/ref/heads/{self.branch}")["object"]["sha"]

    def commits_since(self, start):
        """Commits after ``start``, oldest first, proving the history stays one line."""
        commits, cursor = [], self.head()
        while cursor != start:
            commit = self.get(f"commits/{cursor}")
            assert len(commit["parents"]) == 1, cursor
            commits.append(commit)
            cursor = commit["parents"][0]["sha"]
        commits.reverse()
        return commits


def at_once(*calls):
    """Run the calls together and return their results in order."""
    barrier = threading.Barrier(len(calls))
    results = [None] * len(calls)

    def run(index, call):
        barrier.wait()
        results[index] = call()

    threads = [
        threading.Thread(target=run, args=(index, call))
        for index, call in enumerate(calls)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def check_same_project(first, second, github, team_id):
    """A8: of two saves from one revision, exactly one wins and the other leaves no trace."""
    project = first.create("Same project", team_id)
    status, _ = first.save(project, "# Node_1\nStart.\n", 1)
    assert status == 200, status
    revision = 2
    for round_number in range(3):
        before = github.head()
        texts = [f"# Node_1\nFrom A {round_number}.\n", f"# Node_1\nFrom B {round_number}.\n"]
        results = at_once(
            lambda: first.save(project, texts[0], revision),
            lambda: second.save(project, texts[1], revision),
        )
        statuses = sorted(result[0] for result in results)
        assert statuses == [200, 409], statuses
        winner = texts[[result[0] for result in results].index(200)]
        revision += 1
        for backend in (first, second):
            _, body = backend.open(project)
            assert body["markdown_source"] == winner and body["revision"] == revision, body
        new_commits = github.commits_since(before)
        assert len(new_commits) == 1, len(new_commits)
    print("A8 passed: 3 rounds, each one 200 and one 409, one commit, winner reopens.")


def check_same_branch(first, second, github, team_id, per_backend=4):
    """A9: saves to different projects on one branch all finish, none overwritten."""
    before = github.head()
    backends = [first] * per_backend + [second] * per_backend
    projects = [
        backend.create(f"Branch project {index}", team_id)
        for index, backend in enumerate(backends)
    ]
    texts = [f"# Node_{index}\nText {index}.\n" for index in range(len(projects))]
    results = at_once(
        *[
            lambda backend=backend, project=project, text=text: backend.save(project, text, 1)
            for backend, project, text in zip(backends, projects, texts)
        ]
    )
    failures = [result for result in results if result[0] != 200]
    assert not failures, failures
    for project, text in zip(projects, texts):
        _, body = first.open(project)
        assert body["markdown_source"] == text, body
    commits = github.commits_since(before)
    assert len(commits) == len(projects), len(commits)
    print(
        f"A9 passed: {len(projects)} saves from 2 backends, all 200, "
        f"{len(commits)} commits in one line, every project reopens its own text."
    )


def check_lock_wait(backend, github, team_id, store_key):
    """A held branch lock makes a save wait, then fail cleanly."""
    from django.db import connections

    project = backend.create("Lock wait", team_id)
    before = github.head()
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [store_key])
        started = time.monotonic()
        status, _ = backend.save(project, "# Node_1\nWaited.\n", 1)
        waited = time.monotonic() - started
        cursor.execute("SELECT pg_advisory_unlock(%s)", [store_key])
    assert status == 503, status
    assert LOCK_TIMEOUT_SECONDS <= waited < LOCK_TIMEOUT_SECONDS + 10, waited
    assert github.head() == before
    _, body = backend.open(project)
    assert body["revision"] == 1 and body["markdown_source"] == "", body
    status, _ = backend.save(project, "# Node_1\nAfter the wait.\n", 1)
    assert status == 200, status
    print(f"Lock wait passed: 503 after {waited:.0f}s with no commit, then the retry saved.")


def check_real_github_behavior(first, second_user_backend, github, team_id, users):
    """A14 and A4: the author address and an empty file, as GitHub really handles them."""
    project = first.create('Named "real" check', team_id)
    start = github.head()
    status, _ = first.save(project, "# Node_1\nFirst.\n", 1)
    assert status == 200, status
    status, _ = second_user_backend.save(project, "# Node_1\nSecond.\n", 2)
    assert status == 200, status
    status, body = first.save(project, "", 3)
    assert status == 200, (status, body)
    _, reopened = first.open(project)
    assert reopened["markdown_source"] == "" and reopened["revision"] == 4, reopened

    created, updated, cleared = github.commits_since(start)
    expected = [
        (created, users[0], 'create "Named \\"real\\" check" r2 by Writer A'),
        (updated, users[1], 'update "Named \\"real\\" check" r3 by Writer B'),
        (cleared, users[0], 'update "Named \\"real\\" check" r4 by Writer A'),
    ]
    committers = set()
    for commit, user, title in expected:
        detail = commit["commit"]
        assert detail["message"] == f"docs(dialogue): {title}", detail["message"]
        assert detail["author"]["email"] == f"user-{user.pk}@dialogue.invalid", detail["author"]
        assert detail["author"]["name"] == user.display_name, detail["author"]
        committers.add(detail["committer"]["email"])
    assert len(committers) == 1, committers
    path = next(file["filename"] for file in cleared["files"])
    assert path == f"teams/{team_id}/projects/{project}.md", path
    size = github.get(f"contents/{path}?ref={cleared['sha']}")["size"]
    assert size == 0, size
    print(
        "A14 passed: GitHub accepted the .invalid author, an empty file reads back empty, "
        "and each account is its own author under one committer."
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--settings",
        default="config.settings_integration",
        help="Settings for the backends. A control run can replace them.",
    )
    parser.add_argument(
        "--only", choices=["same-branch"], help="Run a single check, for a control run."
    )
    options = parser.parse_args()

    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings_integration"
    import django

    django.setup()
    from django.contrib.auth import get_user_model
    from django.core.management import call_command

    from projects.storage import get_content_store
    from teams.models import Team, TeamMembership

    call_command("migrate", verbosity=0, interactive=False)
    users_table = get_user_model().objects
    users = [
        users_table.create_user(
            email=f"writer-{name.lower()}-{uuid.uuid4()}@example.com",
            display_name=f"Writer {name}",
            password=PASSWORD,
        )
        for name in ("A", "B")
    ]
    team = Team.objects.create(name=f"Integration {uuid.uuid4()}")
    for user in users:
        TeamMembership.objects.create(team=team, user=user)

    environment = {**os.environ, "PYTHONUNBUFFERED": "1"}
    processes = [
        subprocess.Popen(
            [
                sys.executable,
                "manage.py",
                "runserver",
                f"127.0.0.1:{port}",
                "--noreload",
                f"--settings={options.settings}",
            ],
            cwd=BACKEND,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for port in PORTS
    ]
    try:
        for port in PORTS:
            for _ in range(60):
                try:
                    urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/accounts/login/", timeout=2
                    ).read()
                    break
                except OSError:
                    time.sleep(0.5)
            else:
                raise RuntimeError(f"The backend on port {port} did not start.")

        github = GitHub()
        first = Backend(PORTS[0], users[0].email)
        second = Backend(PORTS[1], users[0].email)
        second_user = Backend(PORTS[1], users[1].email)

        if options.only == "same-branch":
            check_same_branch(first, second, github, team.pk)
            return
        check_real_github_behavior(first, second_user, github, team.pk, users)
        check_same_project(first, second, github, team.pk)
        check_same_branch(first, second, github, team.pk)
        check_lock_wait(first, github, team.pk, get_content_store().write_lock_key())
        print("All integration checks passed.")
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            process.wait(timeout=10)


if __name__ == "__main__":
    main()
