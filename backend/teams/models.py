from django.conf import settings
from django.db import models


class Team(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    def has_member(self, user):
        if user is None or not user.is_authenticated:
            return False
        return self.memberships.filter(user=user).exists()


class TeamMembership(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="team_memberships"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["team", "user"], name="unique_team_user"),
        ]

    def __str__(self):
        return f"{self.user} in {self.team}"