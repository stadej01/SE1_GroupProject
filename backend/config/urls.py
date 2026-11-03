"""Dialogue editor routes (local SQLite demo)."""
from django.urls import include, path

urlpatterns = [path("", include("editor.urls"))]
