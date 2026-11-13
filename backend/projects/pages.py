"""Temporary server-rendered project pages for US-37b stage 1."""

from django import forms
from django.conf import settings
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from accounts.token_cookie import token_login_required
from editor.assets import frontend_assets
from teams.models import Team

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


def home_response(request, form=None, status=200):
    teams = Team.objects.filter(memberships__user=request.user).order_by("pk").prefetch_related("projects")
    if form is None:
        form = NewProjectForm(teams=teams)
    return render(request, "projects/home.html", {"teams": teams, "form": form}, status=status)


@never_cache
@token_login_required
@require_GET
def home(request):
    return home_response(request)


@token_login_required
@require_POST
def create(request):
    teams = Team.objects.filter(memberships__user=request.user).order_by("pk")
    form = NewProjectForm(request.POST, teams=teams)
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
        "sync_url": reverse("sync"),
        "open_url": reverse("project-detail", args=[project.pk]),
        "save_url": reverse("project-save", args=[project.pk]),
        "export_url": reverse("project-export", args=[project.pk]),
    })
