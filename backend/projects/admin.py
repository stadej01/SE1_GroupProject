from django.contrib import admin

from .models import NodePosition, Project

# Register your models here.


class NodePositionInline(admin.TabularInline):
    model = NodePosition
    extra = 0


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
    inlines = (NodePositionInline,)
