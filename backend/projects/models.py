import uuid

from django.conf import settings
from django.db import models

from teams.models import Team

# Create your models here.


class Project(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="projects")
    name = models.CharField(max_length=200)
    github_path = models.CharField(max_length=255, unique=True, editable=False)
    head_commit_sha = models.CharField(max_length=40, blank=True)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(revision__gte=1), name="project_revision_positive"
            ),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.github_path:
            self.github_path = f"teams/{self.team_id}/projects/{self.id}.md"
        super().save(*args, **kwargs)


class NodePosition(models.Model):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="positions"
    )
    node_id = models.CharField(max_length=200)
    x = models.FloatField()
    y = models.FloatField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["project", "node_id"], name="unique_node_position"
            ),
        ]

    def __str__(self):
        return f"{self.node_id} ({self.x}, {self.y})"


class Comment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="comments"
    )
    node_id = models.CharField(max_length=200)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="node_comments",
        editable=False,
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    edited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["project", "node_id"], name="comment_project_node"),
        ]

    def __str__(self):
        return f"Comment on {self.node_id} by {self.author_id}"
