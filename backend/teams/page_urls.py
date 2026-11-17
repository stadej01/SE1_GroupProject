from django.urls import path

from . import pages

app_name = "teams"

urlpatterns = [
    path("new/", pages.create, name="create"),
    path("<int:team_id>/", pages.detail, name="detail"),
    path("<int:team_id>/members/", pages.add_member, name="add-member"),
    path("<int:team_id>/members/<int:user_id>/remove/", pages.remove_member, name="remove-member"),
    path("<int:team_id>/leave/", pages.leave, name="leave"),
]
