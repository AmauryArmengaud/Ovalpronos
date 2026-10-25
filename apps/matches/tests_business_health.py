"""check_business_health: exits non-zero (Healthchecks alert) when match data needs attention."""
import datetime as dt
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone

from apps.matches.models import Competition, Match, Team
from apps.predictions.models import Prediction

User = get_user_model()
HEALTHY_DISK = (100, 50, 50)  # total, used, free


@patch('shutil.disk_usage', return_value=HEALTHY_DISK)
class BusinessHealthTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.comp = Competition.objects.create(external_id=801, name='Top 14', code='BH', country='F', season='2026')
        cls.home = Team.objects.create(external_id=8001, slug='bh-a', name='Toulouse')
        cls.away = Team.objects.create(external_id=8002, slug='bh-b', name='Clermont')
        cls._ext = 80000

    def make_match(self, hours, **kwargs):
        type(self)._ext += 1
        defaults = dict(
            external_id=self._ext, competition=self.comp, home_team=self.home, away_team=self.away,
            datetime=timezone.now() + dt.timedelta(hours=hours), status=Match.STATUS_SCHEDULED,
            cote_home=18, cote_draw=250, cote_away=22,
        )
        defaults.update(kwargs)
        return Match.objects.create(**defaults)

    def run_check(self):
        out = StringIO()
        try:
            call_command('check_business_health', stdout=out)
        except CommandError as e:
            return False, out.getvalue() + str(e)
        return True, out.getvalue()

    def test_healthy_data_passes(self, _):
        self.make_match(72)
        self.make_match(-24, status=Match.STATUS_FINISHED, home_score=20, away_score=10)
        ok, out = self.run_check()
        self.assertTrue(ok, out)

    def test_match_never_scored_by_gemini_is_reported(self, _):
        self.make_match(-8)
        self.make_match(-2)  # still within the live window, not stuck yet
        ok, out = self.run_check()
        self.assertFalse(ok)
        self.assertIn('Toulouse vs Clermont', out)
        self.assertEqual(out.count('Toulouse vs Clermont'), 1)

    def test_finished_match_with_unscored_predictions_is_reported(self, _):
        m = self.make_match(-24, status=Match.STATUS_FINISHED, home_score=20, away_score=10)
        user = User.objects.create_user(username='bh', password='x', email='bh@t.local')
        Prediction.objects.create(user=user, match=m, predicted_home_score=1, predicted_away_score=0)
        ok, out = self.run_check()
        self.assertFalse(ok)
        self.assertIn('sans points', out)

    def test_match_within_48h_without_odds_is_reported(self, _):
        self.make_match(30, cote_home=None, cote_draw=None, cote_away=None)
        self.make_match(30, cote_home=None, cote_draw=None, cote_away=None, is_hidden=True)
        ok, out = self.run_check()
        self.assertFalse(ok)
        self.assertEqual(out.count('sans cotes'), 1)

    def test_full_disk_is_reported(self, disk):
        disk.return_value = (100, 85, 15)
        ok, out = self.run_check()
        self.assertFalse(ok)
        self.assertIn('85 %', out)
