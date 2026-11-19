from django.urls import path

from . import pages

app_name = "pages"

urlpatterns = [
    path("", pages.home, name="home"),
    path("projects/new/", pages.create, name="create"),
    path("projects/<uuid:project_id>/", pages.project, name="project"),
]
