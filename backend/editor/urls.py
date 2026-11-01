from django.urls import path
from . import views
app_name = "editor"
urlpatterns = [path("", views.index, name="index"),
               path("sync", views.sync, name="sync"),
               path("save", views.save, name="save")]
