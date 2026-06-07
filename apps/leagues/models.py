import random
import string

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


def _generate_invite_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))


class League(models.Model):
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    invite_code = models.CharField(
        max_length=5,
        unique=True,
        default=_generate_invite_code,
        verbose_name=_("Invite code"),
    )
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_leagues',
        verbose_name=_("Creator"),
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='leagues',
        verbose_name=_("Members"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("League")
        verbose_name_plural = _("Leagues")
        ordering = ['name']

    def __str__(self):
        return self.name
