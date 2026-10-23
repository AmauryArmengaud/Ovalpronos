"""Phase 1b tests for the Bearer endpoints fed by the Gemini scripts."""
import datetime as dt
import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.matches.models import Competition, Match, Team
from apps.predictions.models import Prediction

User = get_user_model()
TOKEN = 'test-token'
AUTH = {'HTTP_AUTHORIZATION': f'Bearer {TOKEN}'}


@override_settings(SYNC_SECRET_TOKEN=TOKEN)
class ApiBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.comp = Competition.objects.create(
            external_id=601, name='Top 14', code='API1', country='France', season='2026'
        )
        cls.home = Team.objects.create(external_id=6001, slug='api-a', name='Api A')
        cls.away = Team.objects.create(external_id=6002, slug='api-b', name='Api B')
        cls._ext = 60000

    @classmethod
    def make_match(cls, hours, **kwargs):
        cls._ext += 1
        defaults = dict(
            external_id=cls._ext, competition=cls.comp, home_team=cls.home, away_team=cls.away,
            datetime=timezone.now() + dt.timedelta(hours=hours), status=Match.STATUS_SCHEDULED,
        )
        defaults.update(kwargs)
        return Match.objects.create(**defaults)

    def post_json(self, url, payload):
        return self.client.post(url, json.dumps(payload), content_type='application/json', **AUTH)


class UpdateOddsApiTest(ApiBase):
    URL = '/api/update-odds/'

    def _odds(self, match_id, home=18, draw=250, away=22):
        return {'match_id': match_id, 'cote_home': home, 'cote_draw': draw, 'cote_away': away}

    def test_valid_odds_are_written(self):
        m = self.make_match(48)
        resp = self.post_json(self.URL, {'odds': [self._odds(m.pk)]})
        m.refresh_from_db()
        self.assertEqual(resp.json()['updated'], [m.pk])
        self.assertEqual((m.cote_home, m.cote_draw, m.cote_away), (18, 250, 22))

    def test_existing_odds_are_overwritten(self):
        m = self.make_match(48, cote_home=20, cote_draw=250, cote_away=20)
        self.post_json(self.URL, {'odds': [self._odds(m.pk, home=45, away=13)]})
        m.refresh_from_db()
        self.assertEqual(m.cote_home, 45)

    def test_regression_malformed_entries_do_not_crash(self):
        resp = self.post_json(self.URL, {'odds': ['oops', {'match_id': 'abc'}, None]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['updated'], [])
        self.assertEqual(len(resp.json()['skipped']), 3)

    def test_match_outside_upcoming_window_is_rejected(self):
        far = self.make_match(24 * 10)
        hidden = self.make_match(48, is_hidden=True)
        finished = self.make_match(48, status=Match.STATUS_FINISHED)
        resp = self.post_json(self.URL, {'odds': [self._odds(m.pk) for m in (far, hidden, finished)]})
        self.assertEqual(resp.json()['updated'], [])
        self.assertEqual({s['reason'] for s in resp.json()['skipped']}, {'not_allowed'})

    def test_inconsistent_odds_are_rejected(self):
        m = self.make_match(48)
        # 1.0 / 1.0 / 1.0: every outcome "certain", implied probabilities sum to 300 %
        resp = self.post_json(self.URL, {'odds': [self._odds(m.pk, 10, 10, 10)]})
        self.assertEqual(resp.json()['skipped'][0]['reason'], 'inconsistent_odds')
        m.refresh_from_db()
        self.assertIsNone(m.cote_home)


class UpdateScoresApiTest(ApiBase):
    URL = '/api/update-scores/'

    def _score(self, match_id, home=24, away=17, status='finished'):
        return {'match_id': match_id, 'home_score': home, 'away_score': away, 'status': status}

    def _with_prediction(self, match):
        user = User.objects.create_user(username=f'p{match.pk}', password='x', email=f'p{match.pk}@t.local')
        return Prediction.objects.create(user=user, match=match, predicted_home_score=24, predicted_away_score=17)

    def test_live_match_is_scored(self):
        m = self.make_match(-1, cote_home=18, cote_draw=250, cote_away=22)
        pred = self._with_prediction(m)
        resp = self.post_json(self.URL, {'scores': [self._score(m.pk)]})
        pred.refresh_from_db()
        self.assertEqual(resp.json()['updated'], [m.pk])
        self.assertEqual(pred.result_type, 'EXACT')

    def test_regression_malformed_entries_do_not_crash(self):
        resp = self.post_json(self.URL, {'scores': ['oops', {'match_id': 'abc', 'home_score': 1,
                                                              'away_score': 2, 'status': 'finished'}]})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.json()['skipped']), 2)

    def test_match_outside_live_window_is_rejected(self):
        future = self.make_match(48)
        old = self.make_match(-24)
        resp = self.post_json(self.URL, {'scores': [self._score(future.pk), self._score(old.pk)]})
        self.assertEqual(resp.json()['updated'], [])
        self.assertEqual({s['reason'] for s in resp.json()['skipped']}, {'not_allowed'})

    def test_absurd_score_is_rejected(self):
        m = self.make_match(-1)
        resp = self.post_json(self.URL, {'scores': [self._score(m.pk, home=250)]})
        self.assertEqual(resp.json()['skipped'][0]['reason'], 'invalid_data')

    def test_finished_match_can_be_corrected_within_window(self):
        m = self.make_match(-4, status=Match.STATUS_FINISHED, home_score=20, away_score=17,
                            cote_home=18, cote_draw=250, cote_away=22)
        pred = self._with_prediction(m)
        pred.points_earned, pred.result_type = 36, 'GAP'
        pred.save()
        resp = self.post_json(self.URL, {'scores': [self._score(m.pk, 24, 17)]})
        m.refresh_from_db()
        pred.refresh_from_db()
        self.assertEqual(resp.json()['updated'], [m.pk])
        self.assertEqual((m.home_score, m.away_score), (24, 17))
        self.assertEqual((pred.points_earned, pred.result_type), (54, 'EXACT'))

    def test_finished_match_locked_after_window(self):
        m = self.make_match(-6, status=Match.STATUS_FINISHED, home_score=20, away_score=17)
        resp = self.post_json(self.URL, {'scores': [self._score(m.pk, 24, 17)]})
        self.assertEqual(resp.json()['skipped'][0]['reason'], 'not_allowed')

    def test_finished_match_cannot_go_back_in_play(self):
        m = self.make_match(-4, status=Match.STATUS_FINISHED, home_score=20, away_score=17)
        resp = self.post_json(self.URL, {'scores': [self._score(m.pk, 24, 17, status='in_play')]})
        self.assertEqual(resp.json()['skipped'][0]['reason'], 'already_finished')
        m.refresh_from_db()
        self.assertEqual(m.status, Match.STATUS_FINISHED)


class LiveWindowApiTest(ApiBase):
    def test_recently_finished_match_is_sent_to_gemini(self):
        m = self.make_match(-4, status=Match.STATUS_FINISHED, home_score=20, away_score=17)
        self.make_match(-6, status=Match.STATUS_FINISHED, home_score=3, away_score=0)
        ids = [e['match_id'] for e in self.client.get('/api/live-matches/', **AUTH).json()]
        self.assertEqual(ids, [m.pk])
        self.assertTrue(self.client.get('/api/has-live-matches/', **AUTH).json()['live'])
