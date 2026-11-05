"""Routes for the shared accounts, projects, and editor service."""

from django.contrib import admin
from django.urls import include, path

from .views import health, sync


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health/", health, name="health"),
    path("api/v1/", include("projects.urls")),
    path("api/v1/", include("accounts.urls")),
    path("accounts/", include("accounts.page_urls")),
    path("sync", sync, name="sync"),
    path("", include("projects.page_urls")),
]
