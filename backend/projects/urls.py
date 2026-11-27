from django.urls import path

from . import views

urlpatterns = [
    path("projects", views.ProjectCreateView.as_view(), name="project-create"),
    path(
        "projects/<uuid:project_id>",
        views.ProjectDetailView.as_view(),
        name="project-detail",
    ),
    path(
        "projects/<uuid:project_id>/save",
        views.ProjectSaveView.as_view(),
        name="project-save",
    ),
    path(
        "projects/<uuid:project_id>/export",
        views.ProjectExportView.as_view(),
        name="project-export",
    ),
    path(
        "projects/<uuid:project_id>/comments",
        views.ProjectCommentsView.as_view(),
        name="project-comments",
    ),
    path(
        "projects/<uuid:project_id>/comments/<uuid:comment_id>",
        views.ProjectCommentDetailView.as_view(),
        name="project-comment-detail",
    ),
]
