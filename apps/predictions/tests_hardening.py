"""Phase 1b regression tests: hidden matches, score bounds, reminder scoping."""
import datetime as dt

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.leagues.models import League
from apps.matches.models import Competition, Match, Team
from apps.predictions.models import Prediction
from apps.predictions.tasks import send_deadline_reminders

User = get_user_model()


class HardeningBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(username='hard', password='x', email='hard@test.local')
        cls.comp = Competition.objects.create(
            external_id=501, name='Top 14', code='HARD1', country='France', season='2026'
        )
        cls.other_comp = Competition.objects.create(
            external_id=502, name='Other Cup', code='HARD2', country='Europe', season='2026'
        )
        league = League.objects.create(name='L', creator=cls.user)
        league.competitions.add(cls.comp)
        league.members.add(cls.user)
        cls.home = Team.objects.create(external_id=5001, slug='hard-a', name='Hard A')
        cls.away = Team.objects.create(external_id=5002, slug='hard-b', name='Hard B')
        cls._ext = 50000

    @classmethod
    def make_match(cls, comp=None, hours=48, **kwargs):
        cls._ext += 1
        defaults = dict(
            external_id=cls._ext, competition=comp or cls.comp,
            home_team=cls.home, away_team=cls.away,
            datetime=timezone.now() + dt.timedelta(hours=hours),
            status=Match.STATUS_SCHEDULED, cote_home=18, cote_draw=250, cote_away=22,
        )
        defaults.update(kwargs)
        return Match.objects.create(**defaults)


class HiddenMatchTest(HardeningBase):
    def setUp(self):
        self.client.force_login(self.user)

    def test_regression_hidden_match_not_listed(self):
        visible = self.make_match()
        hidden = self.make_match(is_hidden=True)
        resp = self.client.get(reverse('predictions:index'))
        shown = [i['match'].pk for i in resp.context['items']]
        self.assertIn(visible.pk, shown)
        self.assertNotIn(hidden.pk, shown)

    def test_regression_hidden_match_cannot_be_predicted(self):
        hidden = self.make_match(is_hidden=True)
        resp = self.client.post(
            reverse('predictions:submit', kwargs={'match_pk': hidden.pk}),
            {'score_h': '20', 'score_a': '10'},
        )
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(Prediction.objects.filter(match=hidden).exists())


class ScoreBoundTest(HardeningBase):
    def setUp(self):
        self.client.force_login(self.user)
        self.match = self.make_match()

    def _post(self, home, away):
        return self.client.post(
            reverse('predictions:submit', kwargs={'match_pk': self.match.pk}),
            {'score_h': home, 'score_a': away},
        )

    def test_regression_huge_score_is_not_saved(self):
        # used to overflow PostgreSQL integer and raise a 500
        resp = self._post('99999999999', '3')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Prediction.objects.filter(match=self.match).exists())

    def test_score_above_200_is_not_saved(self):
        self._post('201', '3')
        self.assertFalse(Prediction.objects.filter(match=self.match).exists())

    def test_score_of_200_is_saved(self):
        self._post('200', '3')
        self.assertTrue(Prediction.objects.filter(match=self.match).exists())


class DeadlineReminderScopeTest(HardeningBase):
    def test_reminder_lists_only_matches_from_user_competitions(self):
        mine = self.make_match(hours=30)
        self.make_match(comp=self.other_comp, hours=30)
        self.make_match(hours=31, is_hidden=True)
        send_deadline_reminders()
        self.assertEqual(len(mail.outbox), 1)
        listed = mail.outbox[0].merge_global_data['matches']
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]['competition'], mine.competition.name)

    def test_user_without_league_gets_no_reminder(self):
        User.objects.create_user(username='noleague', password='x', email='nl@test.local')
        self.make_match(hours=30)
        send_deadline_reminders()
        self.assertEqual([m.to for m in mail.outbox], [['hard@test.local']])


@override_settings(SITE_URL='https://ovalpronos.com')
class EmailTeamLogoTest(HardeningBase):
    """Regression: admin-uploaded logos (Nations Championship) were missing from emails"""

    def _reminder_logos(self):
        self.make_match(hours=30)
        send_deadline_reminders()
        listed = mail.outbox[0].merge_global_data['matches'][0]
        return listed['home_logo'], listed['away_logo']

    def test_regression_uploaded_logo_used_in_reminder(self):
        Team.objects.filter(pk=self.home.pk).update(logo='teams/france.png')
        home_logo, _ = self._reminder_logos()
        self.assertEqual(home_logo, 'https://ovalpronos.com/media/teams/france.png')

    def test_static_png_used_when_no_upload(self):
        Team.objects.filter(pk=self.home.pk).update(slug='bayonne')
        home_logo, _ = self._reminder_logos()
        self.assertTrue(home_logo.startswith('https://ovalpronos.com/static/img/teams/bayonne'))

    def test_app_logo_when_team_has_no_logo(self):
        _, away_logo = self._reminder_logos()
        self.assertTrue(away_logo.startswith('https://ovalpronos.com/static/img/logo'))

    def test_results_summary_shows_uploaded_logo(self):
        from apps.predictions.tasks import send_results_summary
        Team.objects.filter(pk=self.home.pk).update(logo='teams/france.png')
        match = self.make_match(hours=-5, round='1', status=Match.STATUS_FINISHED, home_score=20, away_score=10)
        Prediction.objects.create(
            user=self.user, match=match, predicted_home_score=20, predicted_away_score=10,
            points_earned=54, result_type='EXACT',
        )
        send_results_summary(competition_id=self.comp.pk, round_label='1')
        html = next(c for c, ct in mail.outbox[0].alternatives if ct == 'text/html')
        self.assertIn('https://ovalpronos.com/media/teams/france.png', html)
