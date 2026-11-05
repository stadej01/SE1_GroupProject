"""Temporary account pages for the shared service."""

from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from teams.models import Team, TeamMembership

from .forms import RegistrationForm


class TemporaryLoginView(LoginView):
    template_name = "accounts/login.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("pages:home")
        return super().dispatch(request, *args, **kwargs)


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("pages:home")
    form = RegistrationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            team = Team.objects.create(name=f"{user.display_name}'s team")
            TeamMembership.objects.create(user=user, team=team)
        login(request, user)
        return redirect("pages:home")
    return render(request, "accounts/register.html", {"form": form})
