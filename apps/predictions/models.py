from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from apps.matches.models import Match


class Prediction(models.Model):
    RESULT_EXACT = 'EXACT'
    RESULT_GAP = 'GAP'
    RESULT_WIN = 'WIN'
    RESULT_MISS = 'MISS'
    RESULT_CANCELLED = 'CANCELLED'

    RESULT_TYPE_CHOICES = [
        (RESULT_EXACT, _('Exact score')),
        (RESULT_GAP, _('Good gap')),
        (RESULT_WIN, _('Correct winner')),
        (RESULT_MISS, _('Missed')),
        (RESULT_CANCELLED, _('Cancelled')),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='predictions',
        verbose_name=_("Player")
    )
    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name='predictions',
        verbose_name=_("Match")
    )

    predicted_home_score = models.IntegerField(verbose_name=_("Predicted home score"))
    predicted_away_score = models.IntegerField(verbose_name=_("Predicted away score"))

    points_earned = models.IntegerField(null=True, blank=True, verbose_name=_("Points earned"))
    result_type = models.CharField(
        max_length=20,
        choices=RESULT_TYPE_CHOICES,
        null=True,
        blank=True,
        verbose_name=_("Result type")
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Prediction")
        verbose_name_plural = _("Predictions")
        unique_together = ('user', 'match')
        ordering = ['-created_at']

    def __str__(self):
        return (
            f"{self.user} → {self.match.home_team} "
            f"{self.predicted_home_score}-{self.predicted_away_score} "
            f"{self.match.away_team}"
        )

    @property
    def predicted_result(self):
        if self.predicted_home_score > self.predicted_away_score:
            return 'home'
        elif self.predicted_away_score > self.predicted_home_score:
            return 'away'
        else:
            return 'draw'

    @property
    def predicted_cote(self):
        """Return the cote (raw ×10 integer) for the predicted winner."""
        result = self.predicted_result
        if result == 'home':
            return self.match.cote_home
        elif result == 'away':
            return self.match.cote_away
        return self.match.cote_draw

    @property
    def potential_points(self):
        """Return potential points dict {exact, gap, win} for the predicted winner."""
        cote = self.predicted_cote
        if cote is None:
            return None
        return {'exact': cote * 3, 'gap': cote * 2, 'win': cote}
