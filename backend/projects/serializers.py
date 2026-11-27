import math

from rest_framework import serializers


class ProjectCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    team_id = serializers.IntegerField(min_value=1)


class PositionSerializer(serializers.Serializer):
    x = serializers.FloatField()
    y = serializers.FloatField()

    def validate(self, attrs):
        if not all(math.isfinite(value) for value in attrs.values()):
            raise serializers.ValidationError("Coordinates must be finite numbers.")
        return attrs


class LayoutNodeSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=200)
    position = PositionSerializer()


class LayoutSerializer(serializers.Serializer):
    nodes = LayoutNodeSerializer(many=True)

    def validate_nodes(self, nodes):
        ids = [node["id"] for node in nodes]
        if len(ids) != len(set(ids)):
            raise serializers.ValidationError("Each node ID can appear only once.")
        return nodes


class ProjectSaveSerializer(serializers.Serializer):
    markdown_source = serializers.CharField(allow_blank=True, trim_whitespace=False)
    layout_data = LayoutSerializer()
    base_revision = serializers.IntegerField(min_value=1)


class ProjectExportSerializer(serializers.Serializer):
    markdown_source = serializers.CharField(allow_blank=True, trim_whitespace=False)


COMMENT_MAX_LENGTH = 5000


class CommentUpdateSerializer(serializers.Serializer):
    body = serializers.CharField(max_length=COMMENT_MAX_LENGTH)


class CommentCreateSerializer(CommentUpdateSerializer):
    node_id = serializers.CharField(max_length=200)


def comment_payload(comment):
    return {
        "comment_id": comment.pk,
        "project_id": comment.project_id,
        "node_id": comment.node_id,
        "author_id": comment.author_id,
        "author_name": comment.author.display_name,
        "body": comment.body,
        "created_at": comment.created_at,
        "edited_at": comment.edited_at,
    }
