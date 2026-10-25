"""
Daily data sanity check, run from cron through scripts/ops/cron_wrap.sh.
Exits non-zero when something needs attention, so Healthchecks.io emails the
list (the command output is sent with the failure ping).

    python manage.py check_business_health
"""
import datetime as dt
import shutil

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils import timezone

from apps.matches.models import Match

# sync_live_scores.py stops following a match 5h after kickoff
STUCK_AFTER = dt.timedelta(hours=6)
ODDS_HORIZON = dt.timedelta(hours=48)
DISK_ALERT_RATIO = 0.80


def _label(m):
    local = timezone.localtime(m.datetime).strftime('%d/%m %Hh%M')
    return f"{m.home_team.name} vs {m.away_team.name} ({m.competition.name}, {local})"


class Command(BaseCommand):
    help = "Vérifie que les données de match sont saines (scores, points, cotes, disque)"

    def handle(self, *args, **options):
        now = timezone.now()
        problems = []
        visible = Match.objects.filter(is_hidden=False).select_related('home_team', 'away_team', 'competition')

        stuck = visible.filter(
            status__in=[Match.STATUS_SCHEDULED, Match.STATUS_IN_PLAY],
            datetime__lte=now - STUCK_AFTER,
            datetime__gte=now - dt.timedelta(days=7),
        )
        problems += [f"Match joué mais jamais terminé (score à saisir dans l'admin) : {_label(m)}" for m in stuck]

        unscored = visible.filter(
            status=Match.STATUS_FINISHED,
            # same filter() call so both conditions apply to the same prediction row;
            # without isnull=False a match with no prediction at all would match too
            predictions__isnull=False,
            predictions__points_earned__isnull=True,
        ).exclude(Q(cote_home__isnull=True) | Q(cote_draw__isnull=True) | Q(cote_away__isnull=True)).distinct()
        problems += [f"Match terminé avec des pronos sans points (\"Recalculer les points\") : {_label(m)}" for m in unscored]

        no_odds = visible.filter(
            status__in=[Match.STATUS_SCHEDULED, Match.STATUS_POSTPONED],
            datetime__gt=now,
            datetime__lte=now + ODDS_HORIZON,
        ).filter(Q(cote_home__isnull=True) | Q(cote_draw__isnull=True) | Q(cote_away__isnull=True))
        problems += [f"Match dans moins de 48h sans cotes : {_label(m)}" for m in no_odds]

        total, used, _free = shutil.disk_usage('/')
        if used / total >= DISK_ALERT_RATIO:
            problems.append(f"Disque du serveur rempli à {used * 100 // total} %")

        if not problems:
            self.stdout.write("Tout est en ordre.")
            return
        for p in problems:
            self.stdout.write(f"- {p}")
        raise CommandError(f"{len(problems)} problème(s) à traiter")
