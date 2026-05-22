from django.contrib.auth.models import AbstractUser
from django.db import models
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

    class Meta:
        verbose_name = _("User")
        verbose_name_plural = _("Users")

    def __str__(self):
        return self.get_display_name()

    def get_display_name(self):
        """Retourne le pseudo public, ou le username en fallback."""
        return self.display_name or self.username
