from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import User


class AccountCreationForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ("email", "display_name")


class AccountChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"
