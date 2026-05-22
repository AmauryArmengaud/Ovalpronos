from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Competition(models.Model):
    """
    Représente une compétition de rugby (Top 14, Champions Cup, 6 Nations).
    Les données viennent de api-sports.io / Rugby API.
    """

    external_id = models.IntegerField(verbose_name=_("API ID"))
    name = models.CharField(max_length=100, verbose_name=_("Name"))
    code = models.CharField(
        max_length=20,
        verbose_name=_("Short code"),
        help_text=_("e.g. TOP14, CHAMP_CUP, SIX_NATIONS")
    )
    country = models.CharField(max_length=100, verbose_name=_("Country / Zone"))
    logo_url = models.URLField(blank=True, verbose_name=_("Logo URL"))
    season = models.CharField(
        max_length=20,
        verbose_name=_("Season"),
        help_text=_("e.g. 2024-2025")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active competition")
    )
    scoring_system = models.CharField(
        max_length=10,
        default='COTES',
        verbose_name=_("Scoring system"),
        help_text=_("COTES = odds-based, FIXED = flat points")
    )
    good_gap_pts = models.IntegerField(
        default=3,
        verbose_name=_("Good gap threshold (pts)")
    )

    class Meta:
        verbose_name = _("Competition")
        verbose_name_plural = _("Competitions")
        ordering = ['name']
        unique_together = [('external_id', 'season')]

    def __str__(self):
        return f"{self.name} ({self.season})"


class Team(models.Model):
    """
    Représente une équipe de rugby (club ou équipe nationale).
    """

    external_id = models.IntegerField(
        unique=True,
        verbose_name=_("API ID")
    )
    slug = models.SlugField(unique=True, blank=True, verbose_name=_("Slug"))
    name = models.CharField(max_length=100, verbose_name=_("Full name"))
    short_name = models.CharField(
        max_length=20,
        blank=True,
        verbose_name=_("Short name"),
        help_text=_("e.g. STA, ASM, LOU")
    )
    logo_url = models.URLField(blank=True, verbose_name=_("Logo URL"))
    country = models.CharField(max_length=100, blank=True, verbose_name=_("Country"))

    class Meta:
        verbose_name = _("Team")
        verbose_name_plural = _("Teams")
        ordering = ['name']

    def __str__(self):
        return self.name


class Match(models.Model):
    """
    Représente un match de rugby.

    Le champ `status` suit le cycle de vie d'un match :
    - SCHEDULED  : match planifié, les pronos sont ouverts
    - IN_PLAY    : match en cours, les pronos sont verrouillés
    - FINISHED   : match terminé, les points sont calculés
    - POSTPONED  : match reporté (traité comme SCHEDULED)
    - CANCELLED  : match annulé (pronos remboursés = 0 pts)
    """

    STATUS_SCHEDULED = 'SCHEDULED'
    STATUS_IN_PLAY = 'IN_PLAY'
    STATUS_FINISHED = 'FINISHED'
    STATUS_POSTPONED = 'POSTPONED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (STATUS_SCHEDULED, _('Scheduled')),
        (STATUS_IN_PLAY, _('In play')),
        (STATUS_FINISHED, _('Finished')),
        (STATUS_POSTPONED, _('Postponed')),
        (STATUS_CANCELLED, _('Cancelled')),
    ]

    external_id = models.IntegerField(
        unique=True,
        verbose_name=_("API ID")
    )
    competition = models.ForeignKey(
        Competition,
        on_delete=models.CASCADE,
        related_name='matches',
        verbose_name=_("Competition")
    )
    home_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='home_matches',
        verbose_name=_("Home team")
    )
    away_team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name='away_matches',
        verbose_name=_("Away team")
    )

    # Schedule info
    round = models.CharField(
        max_length=50,
        blank=True,
        verbose_name=_("Round"),
        help_text=_("e.g. 1, 22, Semi-final, Final")
    )
    datetime = models.DateTimeField(verbose_name=_("Kickoff date and time"))
    venue = models.CharField(max_length=200, blank=True, verbose_name=_("Venue"))

    # Status and score
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_SCHEDULED,
        verbose_name=_("Status")
    )
    is_hidden = models.BooleanField(
        default=False,
        verbose_name=_("Hidden"),
        help_text=_("If True, this match is not shown to users in the prediction UI.")
    )
    home_score = models.IntegerField(null=True, blank=True, verbose_name=_("Home score"))
    away_score = models.IntegerField(null=True, blank=True, verbose_name=_("Away score"))
    cote_home = models.IntegerField(null=True, blank=True, verbose_name=_("Home odds (×10)"))
    cote_draw = models.IntegerField(null=True, blank=True, verbose_name=_("Draw odds (×10)"))
    cote_away = models.IntegerField(null=True, blank=True, verbose_name=_("Away odds (×10)"))

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Match")
        verbose_name_plural = _("Matches")
        ordering = ['datetime']

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} — {self.datetime.strftime('%d/%m/%Y %H:%M')}"

    @property
    def is_locked(self):
        """
        Un match est verrouillé si l'heure de coup d'envoi est passée.
        Cette propriété est vérifiée côté serveur lors de la soumission d'un prono.
        """
        return timezone.now() >= self.datetime

    @property
    def result(self):
        """Retourne le résultat : 'home', 'away', 'draw', ou None si pas fini."""
        if self.home_score is None or self.away_score is None:
            return None
        if self.home_score > self.away_score:
            return 'home'
        elif self.away_score > self.home_score:
            return 'away'
        else:
            return 'draw'

    @property
    def score_display(self):
        """Affichage du score pour les templates."""
        if self.home_score is not None and self.away_score is not None:
            return f"{self.home_score} - {self.away_score}"
        return "- : -"

    @property
    def has_odds(self):
        return self.cote_home is not None and self.cote_draw is not None and self.cote_away is not None

    @property
    def closes_soon(self):
        """True if match starts within the next 24 hours and is not yet locked."""
        if self.is_locked:
            return False
        import datetime
        from django.utils import timezone
        return self.datetime - timezone.now() <= datetime.timedelta(hours=24)

    @property
    def time_until_kickoff(self):
        """Returns timedelta until kickoff, or None if already locked."""
        if self.is_locked:
            return None
        from django.utils import timezone
        return self.datetime - timezone.now()
