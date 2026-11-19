from django.conf import settings
from django.contrib.auth import authenticate
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from teams.models import Team, TeamMembership

from .forms import RegistrationForm
from .serializers import LoginSerializer
from .token_cookie import clear_token_cookie, has_valid_csrf_token, set_token_cookie, use_token_user
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
        token = create_token(user)
        response = Response(
            {
                "token": token,
                "user": {
                    "id": user.pk,
                    "name": user.display_name,
                    "email": user.email,
                },
                "teams": teams_dashboard(user),
            }
        )
        # Only our login page sends the CSRF token. Scripts get the token without a cookie.
        if has_valid_csrf_token(request):
            set_token_cookie(request, response, token)
        return response


def safe_next(request):
    """Returns the `next` page if it is on this site, or else the home page."""
    url = request.GET.get("next", "")
    if url_has_allowed_host_and_scheme(
        url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return url
    return reverse("pages:home")


@never_cache
@ensure_csrf_cookie
@require_GET
def login_page(request):
    """Shows the login form. The form posts to `POST /api/v1/auth/login`."""
    if use_token_user(request).is_authenticated:
        return redirect("pages:home")
    return render(request, "accounts/login.html", {
        "next": safe_next(request), "csrf_cookie_name": settings.CSRF_COOKIE_NAME,
    })


@require_http_methods(["GET", "POST"])
def register(request):
    if use_token_user(request).is_authenticated:
        return redirect("pages:home")
    form = RegistrationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            team = Team.objects.create(name=f"{user.display_name}'s team")
            TeamMembership.objects.create(user=user, team=team)
        return set_token_cookie(request, redirect("pages:home"), create_token(user))
    return render(request, "accounts/register.html", {"form": form})


@require_POST
def logout(request):
    return clear_token_cookie(redirect("accounts:login"))
