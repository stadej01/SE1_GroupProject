from django.contrib import admin

from .models import Comment, NodePosition, Project

# Register your models here.


class NodePositionInline(admin.TabularInline):
    model = NodePosition
    extra = 0


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    fields = ("node_id", "author", "body", "created_at", "edited_at")
    readonly_fields = ("author", "created_at", "edited_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "team", "revision", "updated_at")
    list_filter = ("team",)
    search_fields = ("name",)
    readonly_fields = (
        "id",
        "github_path",
        "head_commit_sha",
        "revision",
        "created_at",
        "updated_at",
    )
    inlines = (NodePositionInline, CommentInline)
