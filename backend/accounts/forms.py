from django.contrib.auth.forms import AdminUserCreationForm, BaseUserCreationForm, UserChangeForm

from .models import User


class RegistrationForm(BaseUserCreationForm):
    """Temporary registration form until the US-31b account pages are ready."""

    class Meta(BaseUserCreationForm.Meta):
        model = User
        fields = ("email", "display_name")

    def clean_email(self):
        return User.objects.normalize_email(self.cleaned_data["email"])


class AccountCreationForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ("email", "display_name")


class AccountChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"
