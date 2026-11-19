from django.urls import path

from . import views

urlpatterns = [
    path("auth/login", views.LoginView.as_view(), name="auth-login"),
]