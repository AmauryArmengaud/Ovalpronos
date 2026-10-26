import secrets

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _


class CustomUser(AbstractUser):
    """
    Modèle utilisateur étendu.
    On hérite de AbstractUser (qui gère déjà username, email, password,
    first_name, last_name, is_active, is_staff, date_joined, etc.)
    et on ajoute nos champs spécifiques à Oval'Pronos.
    """

    # Override email to make it required and unique
    email = models.EmailField(
        unique=True,
        verbose_name=_("Email address")
    )

    # Public nickname shown in rankings (may differ from username)
    display_name = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Display name")
    )

    # Optional avatar
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        verbose_name=_("Profile picture")
    )

    # Favourite rugby club (informational, for future UI personalisation)
    favorite_team = models.ForeignKey(
        'matches.Team',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='fans',
        verbose_name=_("Favourite team")
    )

    # Acquisition source, kept on the account because analytics only run with consent
    signup_source = models.CharField(max_length=100, blank=True, verbose_name=_("Signup source"))
    signup_campaign = models.CharField(max_length=100, blank=True, verbose_name=_("Signup campaign"))
    signup_medium = models.CharField(max_length=100, blank=True, verbose_name=_("Signup medium"))
    signup_content = models.CharField(max_length=100, blank=True, verbose_name=_("Signup content"))
    signup_landing_path = models.CharField(max_length=200, blank=True, verbose_name=_("Signup landing page"))

    last_reminder_sent = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Last reminder sent"),
    )

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self):
        return self.get_display_name()

    def get_display_name(self):
        """Retourne le pseudo public, ou le username en fallback."""
        return self.display_name or self.username


def _new_invitation_token():
    return secrets.token_urlsafe(16)


class Invitation(models.Model):
    """Pre-filled sign-up link for a player of the 2023 app, sent in the relaunch campaign"""

    token = models.CharField(max_length=32, unique=True, default=_new_invitation_token, editable=False)
    email = models.EmailField(unique=True)
    pseudo = models.CharField(max_length=50, blank=True)
    first_name = models.CharField(max_length=30, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    cohort = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    user = models.OneToOneField(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='invitation',
    )

    def __str__(self):
        return self.email


@receiver(post_delete, sender=CustomUser)
def _delete_avatar_file(sender, instance, **kwargs):
    # ImageField never removes its file; a deleted account must not leave a photo behind
    if instance.avatar:
        instance.avatar.delete(save=False)
