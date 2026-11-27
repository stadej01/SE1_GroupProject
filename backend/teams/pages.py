"""Team pages: create a team, and view, add, remove, or leave its members."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from accounts.token_cookie import token_login_required
from projects.pages import home_response

from . import services
from .forms import AddMemberForm, NewTeamForm
from .models import Team


def home_team_url(team_id):
    return f"{reverse('pages:home')}#team-{team_id}"


def forbidden(request):
    return render(request, "teams/forbidden.html", status=403)


def team_response(request, team, form=None, error=None, status=200, unknown_email=False):
    memberships = list(
        team.memberships.select_related("user").order_by("user__display_name", "user__email")
    )
    return render(request, "teams/detail.html", {
        "team": team,
        "memberships": memberships,
        "project_count": team.projects.count(),
        "suggestions": services.other_teammates(request.user, team),
        "form": form or AddMemberForm(),
        "error": error,
        "unknown_email": unknown_email,
        "home_url": home_team_url(team.pk),
    }, status=status)


def member_team(request, team_id):
    """The team, or None when the signed-in user is not on it."""
    team = get_object_or_404(Team, pk=team_id)
    return team if team.has_member(request.user) else None


@token_login_required
@require_POST
def create(request):
    form = NewTeamForm(request.POST)
    if not form.is_valid():
        return home_response(request, team_form=form, status=400)
    team = services.create_team(request.user, form.cleaned_data["name"])
    messages.success(request, f"Created {team.name}.")
    return redirect(home_team_url(team.pk))


@never_cache
@token_login_required
@require_GET
def detail(request, team_id):
    team = member_team(request, team_id)
    if team is None:
        return forbidden(request)
    return team_response(request, team)


@token_login_required
@require_POST
def add_member(request, team_id):
    team = get_object_or_404(Team, pk=team_id)
    form = AddMemberForm(request.POST)
    if not team.has_member(request.user):
        return forbidden(request)
    if not form.is_valid():
        return team_response(request, team, form=form, status=400)
    try:
        membership = services.add_member(request.user, team.pk, form.cleaned_data["email"])
    except services.NotAMember:
        return forbidden(request)
    except services.UnknownEmail:
        form.add_error("email", "No account uses this email. Send them the sign-up link first.")
        return team_response(request, team, form=form, status=400, unknown_email=True)
    except services.AlreadyMember as duplicate:
        form.add_error("email", str(duplicate))
        return team_response(request, team, form=form, status=400)
    messages.success(request, f"Added {membership.user.display_name}.", extra_tags=f"member-{membership.pk}")
    return redirect("teams:detail", team_id=team.pk)


def _remove(request, team, user_id):
    leaving = user_id == request.user.pk
    try:
        removed = services.remove_member(request.user, team.pk, user_id)
    except services.NotAMember:
        return forbidden(request)
    except services.NoLongerMember:
        return team_response(
            request, team, error="That person is no longer a member of this team.", status=409
        )
    except services.LastMember:
        error = ("You are the only member, so you cannot leave this team." if leaving
                 else "A team needs at least one member.")
        return team_response(request, team, error=error, status=409)
    if leaving:
        messages.success(request, f"You left {team.name}.")
        return redirect("pages:home")
    messages.success(request, f"Removed {removed.display_name}.")
    return redirect("teams:detail", team_id=team.pk)


@token_login_required
@require_POST
def remove_member(request, team_id, user_id):
    team = get_object_or_404(Team, pk=team_id)
    return _remove(request, team, user_id)


@token_login_required
@require_POST
def leave(request, team_id):
    team = get_object_or_404(Team, pk=team_id)
    return _remove(request, team, request.user.pk)
