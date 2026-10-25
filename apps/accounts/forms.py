from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordResetForm
from django.core.mail import EmailMultiAlternatives
from django.template import loader
from django.utils.translation import gettext_lazy as _
from .models import CustomUser


class TrackingFreePasswordResetForm(PasswordResetForm):
    """
    Disables Brevo click/open tracking on the password reset email.
    Tracking must be off so that the reset link is not rewritten.
    """
    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        subject = loader.render_to_string(subject_template_name, context)
        subject = "".join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)
        msg = EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_email_template_name is not None:
            html_body = loader.render_to_string(html_email_template_name, context)
            msg.attach_alternative(html_body, "text/html")
        # Brevo-native tracking flags via esp_extra — prevent link rewriting.
        # Anymail passes these through to the Brevo API as-is.
        # Ignored silently by the console backend in development.
        msg.esp_extra = {'trackClicks': False, 'trackOpens': False}
        msg.send()


class EmailOrUsernameAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label=_("Email address or username"))


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


class AccountDeleteForm(forms.Form):
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data['password']
        if not self.user.check_password(password):
            raise forms.ValidationError(_("Incorrect password."))
        return password
