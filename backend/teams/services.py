"""Team changes made through the app.

Every membership change locks the Team row first, so changes to one team run
one at a time. That keeps the last-member check true when two members leave or
remove each other at the same moment.
"""

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from .models import Team, TeamMembership


class TeamChangeError(Exception):
    """A membership change that cannot be made."""


class NotAMember(TeamChangeError):
    """The person asking is not on the team."""


class UnknownEmail(TeamChangeError):
    """No active account uses the email."""


class AlreadyMember(TeamChangeError):
    def __init__(self, user):
        super().__init__(f"{user.display_name} is already a member of this team.")
        self.user = user


class NoLongerMember(TeamChangeError):
    """The person to remove left or was removed already."""


class LastMember(TeamChangeError):
    """A team keeps at least one member."""


def create_team(user, name):
    """Create a team with its creator as the only member."""
    with transaction.atomic():
        team = Team.objects.create(name=name)
        TeamMembership.objects.create(team=team, user=user)
    return team


def other_teammates(actor, team):
    other_teams = TeamMembership.objects.filter(user=actor).exclude(team=team).values("team")
    colleagues = TeamMembership.objects.filter(team__in=other_teams).values("user")
    return get_user_model().objects.filter(is_active=True, pk__in=colleagues).exclude(
        pk__in=team.memberships.values("user")
    ).only("display_name", "email").order_by("display_name", "email")


def _locked_team_for(actor, team_id):
    """Lock the team and confirm the actor still belongs to it. Call inside a transaction."""
    team = Team.objects.select_for_update().get(pk=team_id)
    if not team.memberships.filter(user=actor).exists():
        raise NotAMember()
    return team


def _ensure_not_last(team):
    if team.memberships.count() <= 1:
        raise LastMember()


def add_member(actor, team_id, email):
    """Add the registered user with this email. Returns the new membership."""
    User = get_user_model()
    with transaction.atomic():
        team = _locked_team_for(actor, team_id)
        user = User.objects.filter(
            email=User.objects.normalize_email(email.strip()), is_active=True
        ).first()
        if user is None:
            raise UnknownEmail()
        if team.memberships.filter(user=user).exists():
            raise AlreadyMember(user)
        try:
            with transaction.atomic():
                return TeamMembership.objects.create(team=team, user=user)
        except IntegrityError:
            raise AlreadyMember(user) from None


def remove_member(actor, team_id, user_id):
    """Remove a member, or the actor themself when user_id is theirs.

    Any member may remove any other member. The last member stays.
    Returns the removed user.
    """
    with transaction.atomic():
        team = _locked_team_for(actor, team_id)
        membership = (
            team.memberships.select_related("user").filter(user_id=user_id).first()
        )
        if membership is None:
            raise NoLongerMember()
        _ensure_not_last(team)
        membership.delete()
    return membership.user


def leave_team(actor, team_id):
    return remove_member(actor, team_id, actor.pk)
