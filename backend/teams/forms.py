from django import forms

from .models import Team


class NewTeamForm(forms.ModelForm):
    prefix = "team"

    class Meta:
        model = Team
        fields = ("name",)
        labels = {"name": "Team name"}
        error_messages = {"name": {"required": "Enter a team name."}}


class AddMemberForm(forms.Form):
    email = forms.EmailField(
        label="Registered email",
        max_length=254,
        error_messages={"required": "Enter the email of a registered user."},
        widget=forms.EmailInput(attrs={"autocomplete": "off"}),
    )
