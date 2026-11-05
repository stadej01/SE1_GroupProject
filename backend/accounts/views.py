from django.contrib.auth import authenticate, login
from django.contrib.auth import views as auth_views
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from teams.models import Team, TeamMembership

from .forms import RegistrationForm
from .serializers import LoginSerializer
from .tokens import create_token


def teams_dashboard(user):
    teams = (
        Team.objects.filter(memberships__user=user)
        .prefetch_related("projects")
        .order_by("name")
    )
    return [
        {
            "team_id": team.pk,
            "name": team.name,
            "projects": [
                {
                    "project_id": project.pk,
                    "name": project.name,
                    "revision": project.revision,
                    "updated_at": project.updated_at,
                }
                for project in sorted(team.projects.all(), key=lambda p: p.name)
            ],
        }
        for team in teams
    ]


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)  
        user = authenticate(
            request,
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(
            {
                "token": create_token(user),
                "user": {
                    "id": user.pk,
                    "name": user.display_name,
                    "email": user.email,
                },
                "teams": teams_dashboard(user),
            }
        )


class TemporaryLoginView(auth_views.LoginView):
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
