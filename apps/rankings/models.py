from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class UserScore(models.Model):
    """
    Denormalized score cache. One row per (user, scope) where scope is:
      - (competition=None, league=None)  → global
      - (competition=<comp>, league=None) → per competition
    League rankings are derived from global rows filtered to league members.

    Refreshed by refresh_user_scores_for_match() after each match is scored.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='user_scores',
        verbose_name=_("Player"),
    )
    competition = models.ForeignKey(
        'matches.Competition',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Competition"),
    )
    league = models.ForeignKey(
        'leagues.League',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("League"),
    )
    points = models.IntegerField(default=0, verbose_name=_("Points"))
    prediction_count = models.IntegerField(default=0, verbose_name=_("Predictions scored"))
    exact_count = models.IntegerField(default=0, verbose_name=_("Exact scores"))
    gap_count = models.IntegerField(default=0, verbose_name=_("Good gaps"))
    win_count = models.IntegerField(default=0, verbose_name=_("Correct winners"))
    rank = models.IntegerField(null=True, blank=True, verbose_name=_("Rank"))

    class Meta:
        verbose_name = _("User score")
        verbose_name_plural = _("User scores")
        indexes = [
            models.Index(fields=['competition', 'league'], name='userscore_scope_idx'),
        ]

    def __str__(self):
        return f"{self.user} — {self.points} pts"
