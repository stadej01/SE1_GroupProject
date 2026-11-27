"""Server-rendered home and project pages."""

from django import forms
from django.conf import settings
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from accounts.token_cookie import token_login_required
from editor.assets import frontend_assets
from teams.forms import NewTeamForm
from teams.models import Team, TeamMembership

from .models import Project


class NewProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ("name", "team")
        labels = {"name": "Project name"}

    def __init__(self, *args, teams, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["team"].queryset = teams
        self.fields["team"].empty_label = None


def member_teams(user):
    return Team.objects.filter(
        pk__in=TeamMembership.objects.filter(user=user).values("team")
    ).order_by("pk")


def home_response(request, form=None, team_form=None, status=200):
    teams = member_teams(request.user).prefetch_related("projects").annotate(
        member_count=Count("memberships")
    )
    if form is None:
        form = NewProjectForm(teams=member_teams(request.user))
    return render(request, "projects/home.html", {
        "teams": teams, "form": form, "team_form": team_form or NewTeamForm(),
    }, status=status)


@never_cache
@token_login_required
@require_GET
def home(request):
    return home_response(request)


@token_login_required
@require_POST
def create(request):
    form = NewProjectForm(request.POST, teams=member_teams(request.user))
    if form.is_valid():
        project = form.save()
        return redirect("pages:project", project_id=project.pk)
    return home_response(request, form=form, status=400)


@never_cache
@token_login_required
@ensure_csrf_cookie
@require_GET
def project(request, project_id):
    project = get_object_or_404(Project.objects.select_related("team"), pk=project_id)
    if not project.team.has_member(request.user):
        return render(request, "projects/forbidden.html", status=403)
    return render(request, "editor/index.html", {
        "project": project,
        "revision": project.revision,
        "assets": frontend_assets(),
        "csrf_cookie_name": settings.CSRF_COOKIE_NAME,
        "login_url": reverse("accounts:login"),
        "home_url": f"{reverse('pages:home')}#team-{project.team_id}",
        "sync_url": reverse("sync"),
        "continuity_url": reverse("continuity"),
        "open_url": reverse("project-detail", args=[project.pk]),
        "save_url": reverse("project-save", args=[project.pk]),
        "export_url": reverse("project-export", args=[project.pk]),
    })
