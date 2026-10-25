import random
import string

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


def _generate_invite_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))


def hand_over_or_delete(collector, field, sub_objs, using):
    """on_delete for League.creator: a league outlives its creator.

    It passes to its oldest remaining member (membership rows are created in
    join order, so the lowest pk joined first) and is only deleted when the
    creator was its last member.
    """
    membership = League.members.through
    alone = []
    for league in sub_objs:
        heir_id = (
            membership.objects.using(using)
            .filter(league_id=league.pk)
            .exclude(customuser_id=league.creator_id)
            .order_by('pk')
            .values_list('customuser_id', flat=True)
            .first()
        )
        if heir_id is None:
            alone.append(league)
        else:
            collector.add_field_update(field, heir_id, [league])
    if alone:
        models.CASCADE(collector, field, alone, using)


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
        on_delete=hand_over_or_delete,
        related_name='created_leagues',
        verbose_name=_("Creator"),
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='leagues',
        verbose_name=_("Members"),
    )
    competitions = models.ManyToManyField(
        'matches.Competition',
        related_name='leagues',
        verbose_name=_("Competitions"),
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def is_active(self):
        return self.competitions.filter(is_active=True).exists()

    class Meta:
        verbose_name = _("League")
        verbose_name_plural = _("Leagues")
        ordering = ['name']

    def __str__(self):
        return self.name
