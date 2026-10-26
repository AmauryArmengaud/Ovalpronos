from collections import defaultdict
from datetime import datetime, time

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Exists, OuterRef, Sum
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from apps.leagues.models import League
from apps.matches.models import Competition, LandingView
from apps.predictions.models import Prediction


def campaign_report(competition, since):
    """Funnel per source for one competition landing, plus sign-ups that entered elsewhere.

    Returns (landing_rows, other_rows); each row: source, views, signups, activated, leagues.
    A sign-up belongs to the landing when its first known page is that landing.
    """
    landing_path = reverse('matches:competition_landing', kwargs={'code': competition.code.lower()})
    views = defaultdict(int)
    for row in (LandingView.objects.filter(competition=competition, day__gte=since)
                .values('source').annotate(total=Sum('count'))):
        views[row['source']] = row['total']

    start = timezone.make_aware(datetime.combine(since, time.min))
    users = get_user_model().objects.filter(date_joined__gte=start).annotate(
        _activated=Exists(Prediction.objects.filter(user=OuterRef('pk'))),
    )
    creators = set(League.objects.filter(competitions=competition, created_at__gte=start)
                   .values_list('creator_id', flat=True))

    def rows(queryset, with_views):
        stats = defaultdict(lambda: {'signups': 0, 'activated': 0, 'leagues': 0})
        for user in queryset.only('pk', 'signup_source'):
            s = stats[user.signup_source or 'direct']
            s['signups'] += 1
            s['activated'] += user._activated
            s['leagues'] += user.pk in creators
        sources = set(stats) | (set(views) if with_views else set())
        return [
            {'source': src, 'views': views[src] if with_views else None, **stats[src]}
            for src in sorted(sources, key=lambda src: (-stats[src]['signups'], src))
        ]

    return rows(users.filter(signup_landing_path=landing_path), True), \
        rows(users.exclude(signup_landing_path=landing_path), False)


class Command(BaseCommand):
    help = "Campaign funnel for a competition landing: views, sign-ups, conversion, activated, leagues, per source."

    def add_arguments(self, parser):
        parser.add_argument('code', help="Competition code, e.g. NATIONS")
        parser.add_argument('--since', help="Start date YYYY-MM-DD (default: first recorded landing view)")

    def handle(self, *args, **options):
        competition = Competition.objects.filter(code__iexact=options['code']).first()
        if competition is None:
            raise CommandError(f"Unknown competition: {options['code']}")
        if options['since']:
            since = datetime.strptime(options['since'], '%Y-%m-%d').date()
        else:
            first = competition.landing_views.order_by('day').first()
            since = first.day if first else timezone.localdate()

        with translation.override(settings.LANGUAGE_CODE):
            landing, other = campaign_report(competition, since)
            self.stdout.write(_("%(name)s campaign since %(date)s") % {'name': competition.name, 'date': since})
            self._table(_("Landing page"), landing, with_views=True)
            self._table(_("Outside the landing page"), other, with_views=False)

    def _table(self, title, rows, with_views):
        head = [_("Source")] + ([_("Views"), _("Sign-ups"), _("Conversion")] if with_views else [_("Sign-ups")]) \
            + [_("Activated"), _("Leagues created")]
        lines = []
        totals = {'views': 0, 'signups': 0, 'activated': 0, 'leagues': 0}
        for row in rows + [None]:
            if row is None:
                row = {'source': _("Total"), **totals}
            else:
                for key in totals:
                    totals[key] += row[key] or 0
            cells = [row['source']]
            if with_views:
                rate = f"{row['signups'] / row['views']:.1%}" if row['views'] else '-'
                cells += [row['views'], row['signups'], rate]
            else:
                cells += [row['signups']]
            cells += [row['activated'], row['leagues']]
            lines.append([str(c) for c in cells])
        widths = [max(len(r[i]) for r in [head] + lines) for i in range(len(head))]
        fmt = lambda r: '  '.join(c.ljust(w) if i == 0 else c.rjust(w) for i, (c, w) in enumerate(zip(r, widths)))
        self.stdout.write(f"\n{title}")
        self.stdout.write(fmt(head))
        for line in lines:
            self.stdout.write(fmt(line))
