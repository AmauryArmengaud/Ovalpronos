"""
Tests for sync_competition_matches(): the RapidAPI sync imports the calendar
but never writes scores or IN_PLAY/FINISHED status (scores come from
scripts/sync_live_scores.py via /api/update-scores/).
"""
import datetime as dt
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.matches.models import Competition, Match, Team
from apps.matches.services import sync_competition_matches
from apps.predictions.models import Prediction

User = get_user_model()


def _game(game_id=1001, status='Not Started', home_score=None, away_score=None, date=None):
    return {
        'id': game_id,
        'home': 'Home FC', 'home_id': 9001,
        'away': 'Away FC', 'away_id': 9002,
        'status': status,
        'date': date or '2026-11-07T15:00:00+00:00',
        'home_score': home_score,
        'away_score': away_score,
        'game_week': 9,
        'venue': 'Stade',
    }


class SyncDoesNotWriteScoresTest(TestCase):
    def setUp(self):
        self.comp = Competition.objects.create(
            external_id=1, name='Test', code='SYNCTEST', country='France', season='2026'
        )
        self.home = Team.objects.create(external_id=9001, slug='home-fc', name='Home FC')
        self.away = Team.objects.create(external_id=9002, slug='away-fc', name='Away FC')

    def _match(self, **kwargs):
        defaults = dict(
            external_id=1001, competition=self.comp, home_team=self.home, away_team=self.away,
            datetime=timezone.now() - dt.timedelta(days=1),
            status=Match.STATUS_SCHEDULED, cote_home=20, cote_draw=200, cote_away=30,
        )
        defaults.update(kwargs)
        return Match.objects.create(**defaults)

    def _sync(self, games):
        with patch('apps.matches.services._get_fixtures', return_value=games), \
                patch('apps.matches.services.requests.get') as http_get:
            result = sync_competition_matches('SYNCTEST')
        return result, http_get

    def test_finished_score_is_not_overwritten(self):
        match = self._match(status=Match.STATUS_FINISHED, home_score=24, away_score=17)
        self._sync([_game(status='Full Time', home_score=3, away_score=40)])
        match.refresh_from_db()
        self.assertEqual((match.status, match.home_score, match.away_score), ('FINISHED', 24, 17))

    def test_api_full_time_does_not_finish_or_score_match(self):
        match = self._match()
        user = User.objects.create_user(username='u1', password='x', email='u1@test.local')
        prediction = Prediction.objects.create(
            user=user, match=match, predicted_home_score=20, predicted_away_score=10
        )
        self._sync([_game(status='Full Time', home_score=20, away_score=10)])
        match.refresh_from_db()
        prediction.refresh_from_db()
        self.assertEqual(match.status, Match.STATUS_SCHEDULED)
        self.assertIsNone(match.home_score)
        self.assertIsNone(prediction.points_earned)

    def test_api_in_play_does_not_change_status(self):
        match = self._match()
        self._sync([_game(status='Second Half', home_score=10, away_score=7)])
        match.refresh_from_db()
        self.assertEqual(match.status, Match.STATUS_SCHEDULED)
        self.assertIsNone(match.home_score)

    def test_calendar_fields_still_updated(self):
        match = self._match(datetime=timezone.now() + dt.timedelta(days=3))
        self._sync([_game(status='Postponed', date='2026-12-12T20:00:00+00:00')])
        match.refresh_from_db()
        self.assertEqual(match.status, Match.STATUS_POSTPONED)
        self.assertEqual(match.datetime, dt.datetime(2026, 12, 12, 20, 0, tzinfo=dt.timezone.utc))
        self.assertEqual(match.round, '9')

    def test_cancelled_still_applied_and_scored(self):
        match = self._match(datetime=timezone.now() + dt.timedelta(days=3))
        user = User.objects.create_user(username='u2', password='x', email='u2@test.local')
        prediction = Prediction.objects.create(
            user=user, match=match, predicted_home_score=20, predicted_away_score=10
        )
        self._sync([_game(status='Cancelled')])
        match.refresh_from_db()
        prediction.refresh_from_db()
        self.assertEqual(match.status, Match.STATUS_CANCELLED)
        self.assertEqual((prediction.points_earned, prediction.result_type), (0, 'CANCELLED'))

    def test_new_past_match_keeps_api_result(self):
        # a brand-new match has no predictions, so importing its result is harmless
        result, _ = self._sync([_game(game_id=2002, status='Full Time', home_score=30, away_score=12)])
        match = Match.objects.get(external_id=2002)
        self.assertEqual(result['created'], 1)
        self.assertEqual((match.status, match.home_score, match.away_score), ('FINISHED', 30, 12))

    def test_no_per_match_live_api_calls(self):
        self._match()
        past = (timezone.now() - dt.timedelta(hours=1)).isoformat()
        _, http_get = self._sync([_game(date=past)])
        http_get.assert_not_called()
