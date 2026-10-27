import datetime as dt
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from .models import Match
from .tests import make_competition


class UpdateOddsActionTest(TestCase):
    def setUp(self):
        from .models import Team
        comp = make_competition(code='ODDS', is_active=True)
        home = Team.objects.create(external_id=9101, slug='odds-a', name='Odds A')
        away = Team.objects.create(external_id=9102, slug='odds-b', name='Odds B')
        now = timezone.now()
        common = dict(competition=comp, home_team=home, away_team=away, status=Match.STATUS_SCHEDULED)
        self.with_odds = Match.objects.create(external_id=9201, datetime=now + dt.timedelta(days=2),
                                              cote_home=20, cote_draw=250, cote_away=20, **common)
        self.without = Match.objects.create(external_id=9202, datetime=now + dt.timedelta(days=3), **common)
        self.far = Match.objects.create(external_id=9203, datetime=now + dt.timedelta(days=20), **common)
        self.client.force_login(get_user_model().objects.create_superuser('boss', 'boss@test.local', 'x'))

    def _run(self, matches):
        with patch('decouple.config', side_effect=lambda key, default=None, **kw: 'key' if key == 'GOOGLE_API_KEY' else default), \
                patch('subprocess.Popen') as popen:
            self.client.post('/admin/matches/match/', {
                'action': 'update_odds_action', '_selected_action': [m.pk for m in matches]})
        return popen

    def test_selected_matches_are_sent_even_with_odds_or_beyond_7_days(self):
        started = Match.objects.create(
            external_id=9204, datetime=timezone.now() - dt.timedelta(hours=1),
            competition=self.far.competition, home_team=self.far.home_team, away_team=self.far.away_team,
            status=Match.STATUS_SCHEDULED)
        popen = self._run([self.with_odds, self.without, self.far, started])
        args = popen.call_args.args[0]
        sent = set(map(int, args[args.index('--match-ids') + 1].split(',')))
        self.assertEqual(sent, {self.with_odds.pk, self.without.pk, self.far.pk})

    def test_nothing_started_when_no_match_is_eligible(self):
        self.far.is_hidden = True
        self.far.save()
        popen = self._run([self.far])
        popen.assert_not_called()
