"""Account pages. Signing in itself happens in `POST /api/v1/auth/login`."""

from django.urls import path

from .views import login_page, logout, register

app_name = "accounts"

urlpatterns = [
    path("login/", login_page, name="login"),
    path("register/", register, name="register"),
    path("logout/", logout, name="logout"),
]
