"""Temporary account routes until US-31b replaces these pages."""

from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import TemporaryLoginView, register

app_name = "accounts"

urlpatterns = [
    path("login/", TemporaryLoginView.as_view(), name="login"),
    path("register/", register, name="register"),
    path("logout/", LogoutView.as_view(http_method_names=["post"]), name="logout"),
]
