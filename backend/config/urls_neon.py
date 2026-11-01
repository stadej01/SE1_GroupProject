"""Accounts/teams demo routes (Neon database)."""
from django.contrib import admin
from django.urls import path

from .views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health/", health, name="health"),
]
