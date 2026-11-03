import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from teams.models import Team

from .models import Project
from .serializers import ProjectCreateSerializer, ProjectSaveSerializer
from .services import StaleRevision, read_markdown, read_project_snapshot, save_project
from .storage import ContentStoreError, get_content_store

logger = logging.getLogger(__name__)

CONTENT_UNAVAILABLE = {"detail": "Project content is unavailable. Try again later."}


def get_member_project(request, project_id):
    project = get_object_or_404(Project.objects.select_related("team"), pk=project_id)
    if not project.team.has_member(request.user):
        raise PermissionDenied("You are not a member of this project's team.")
    return project


def layout_data(positions):
    nodes = [
        {"id": position.node_id, "position": {"x": position.x, "y": position.y}}
        for position in positions
    ]
    return {"nodes": nodes}


class ProjectCreateView(APIView):
    def post(self, request):
        serializer = ProjectCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                serializer.errors, status=status.HTTP_422_UNPROCESSABLE_ENTITY
            )
        team = Team.objects.filter(pk=serializer.validated_data["team_id"]).first()
        if team is None or not team.has_member(request.user):
            raise PermissionDenied("You are not a member of this team.")

        project = Project.objects.create(
            team=team, name=serializer.validated_data["name"]
        )
        return Response(
            {
                "project_id": project.pk,
                "name": project.name,
                "markdown_source": "",
                "revision": project.revision,
                "created_at": project.created_at,
            },
            status=status.HTTP_201_CREATED,
        )


class ProjectDetailView(APIView):
    def get(self, request, project_id):
        project = get_member_project(request, project_id)
        project, positions = read_project_snapshot(project)
        try:
            markdown = read_markdown(project, get_content_store())
        except ContentStoreError:
            logger.warning(
                "Could not read Markdown to open project %s.",
                project.pk,
                exc_info=True,
            )
            return Response(
                CONTENT_UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        return Response(
            {
                "project_id": project.pk,
                "team_id": project.team_id,
                "name": project.name,
                "markdown_source": markdown,
                "revision": project.revision,
                "layout_data": layout_data(positions),
                "comments": [],
            }
        )


class ProjectSaveView(APIView):
    def put(self, request, project_id):
        project = get_member_project(request, project_id)
        serializer = ProjectSaveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            project = save_project(
                project,
                request.user,
                markdown=data["markdown_source"],
                nodes=data["layout_data"]["nodes"],
                base_revision=data["base_revision"],
                store=get_content_store(),
            )
        except StaleRevision as conflict:
            return Response(
                {
                    "detail": "The project changed after you opened it. "
                    "Refresh the page before saving.",
                    "revision": conflict.current_revision,
                },
                status=status.HTTP_409_CONFLICT,
            )
        except ContentStoreError:
            logger.warning(
                "Could not store Markdown to save project %s.",
                project.pk,
                exc_info=True,
            )
            return Response(
                CONTENT_UNAVAILABLE, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        return Response(
            {
                "status": "saved",
                "revision": project.revision,
                "updated_at": project.updated_at,
                "diagnostics": [],
            }
        )
