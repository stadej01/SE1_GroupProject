"""Project Services: open and save projects."""

from django.db import transaction

from .models import NodePosition, Project


class StaleRevision(Exception):
    """The save was based on an older revision than the stored one."""

    def __init__(self, current_revision):
        super().__init__(f"The project is at revision {current_revision}.")
        self.current_revision = current_revision


def read_markdown(project, store):
    if not project.head_commit_sha:
        return ""
    return store.read(project.github_path, project.head_commit_sha)


def read_project_snapshot(project):
    """Read the saved version and positions while holding the Project lock."""
    with transaction.atomic():
        project = Project.objects.select_for_update().get(pk=project.pk)
        positions = list(project.positions.order_by("node_id"))
    return project, positions


def save_project(project, user, markdown, nodes, base_revision, store):
    """Save Markdown and node positions as the project's next revision.

    The project row stays locked for the whole save, so the revision check,
    the Markdown write, and the database update cannot interleave with another
    save. Markdown is written only when it differs from the saved version.
    """
    with transaction.atomic():
        project = Project.objects.select_for_update().get(pk=project.pk)
        if project.revision != base_revision:
            raise StaleRevision(project.revision)

        changed = markdown != read_markdown(project, store)
        if changed:
            message = (
                f"Save {project.name} ({project.pk}) "
                f"revision {project.revision + 1} by {user.email}"
            )
            project.head_commit_sha = store.write(
                project.github_path, markdown, message
            )

        for node in nodes:
            NodePosition.objects.update_or_create(
                project=project,
                node_id=node["id"],
                defaults={"x": node["position"]["x"], "y": node["position"]["y"]},
            )
        project.revision += 1
        project.save(update_fields=["head_commit_sha", "revision", "updated_at"])
    return project
