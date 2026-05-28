from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _
from .models import CustomUser


class ProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ('display_name', 'avatar', 'favorite_team')
        labels = {
            'display_name': _("Display name"),
            'avatar': _("Profile picture"),
            'favorite_team': _("Favourite team"),
        }


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label=_("Email address"))
    first_name = forms.CharField(max_length=30, required=True, label=_("First name"))
    last_name = forms.CharField(max_length=150, required=True, label=_("Last name"))
    display_name = forms.CharField(
        max_length=50,
        required=False,
        label=_("Display name"),
        help_text=_("Public nickname shown in rankings. Defaults to your username."),
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'email', 'first_name', 'last_name', 'display_name', 'password1', 'password2')
