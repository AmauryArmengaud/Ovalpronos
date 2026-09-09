from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from django.db.models import Q
import datetime as dt

from apps.matches.models import Match
from apps.matches.services import sync_competition_matches


class Command(BaseCommand):
    help = 'Sync scores only if a match is in play or started within the last 2 hours'

    def handle(self, *args, **options):
        now = timezone.now()
        window_start = now - dt.timedelta(hours=2)
        terminal = [Match.STATUS_FINISHED, Match.STATUS_CANCELLED, Match.STATUS_POSTPONED]

        has_live = Match.objects.filter(
            Q(status=Match.STATUS_IN_PLAY)
            | (Q(datetime__lte=now) & Q(datetime__gte=window_start) & ~Q(status__in=terminal))
        ).exists()

        if not has_live:
            return

        for code in settings.RUGBY_COMPETITIONS:
            r = sync_competition_matches(code)
            self.stdout.write(f"[{code}] {r['created']} créés, {r['updated']} mis à jour")
            for change in r['changes']:
                self.stdout.write(f"  {change}")
