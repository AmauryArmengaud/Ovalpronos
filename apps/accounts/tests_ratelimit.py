"""Rate limits: keyed per account / per player (REMOTE_ADDR is nginx in prod)."""
import datetime as dt
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.leagues.models import League
from apps.matches.models import Competition, Match, Team

User = get_user_model()


class RateLimitBase(TestCase):
    def setUp(self):
        cache.clear()


@patch('apps.accounts.views._verify_turnstile', return_value=True)
class LoginRateLimitTest(RateLimitBase):
    def _login(self, username):
        return self.client.post(reverse('accounts:login'), {'username': username, 'password': 'wrong'})

    def test_eleventh_attempt_on_same_account_is_blocked(self, _):
        for _i in range(10):
            self.assertNotEqual(self._login('victim').status_code, 429)
        resp = self._login('victim')
        self.assertEqual(resp.status_code, 429)
        self.assertContains(resp, '429', status_code=429)

    def test_case_variants_share_the_same_limit(self, _):
        for i in range(10):
            self._login('Victim@Test.local' if i % 2 else 'victim@test.local')
        self.assertEqual(self._login('VICTIM@test.local').status_code, 429)

    def test_other_accounts_are_not_affected(self, _):
        for _i in range(11):
            self._login('victim')
        self.assertNotEqual(self._login('someone-else').status_code, 429)


class PasswordResetRateLimitTest(RateLimitBase):
    def test_sixth_request_in_an_hour_is_blocked(self):
        url = reverse('accounts:password_reset')
        for _i in range(5):
            self.assertNotEqual(self.client.post(url, {'email': 'a@test.local'}).status_code, 429)
        self.assertEqual(self.client.post(url, {'email': 'A@test.local'}).status_code, 429)


class LeagueJoinRateLimitTest(RateLimitBase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(username='guesser', password='x', email='g@test.local')
        self.client.force_login(self.user)

    def test_code_guessing_is_capped_across_form_and_links(self):
        for i in range(5):
            self.client.post(reverse('leagues:join'), {'invite_code': f'ZZZZ{i}'})
            self.client.get(reverse('leagues:public_invite', kwargs={'code': f'YYYY{i}'}))
        resp = self.client.post(reverse('leagues:join'), {'invite_code': 'ZZZZZ'})
        self.assertEqual(resp.status_code, 429)

    def test_anonymous_invite_page_is_not_limited(self):
        self.client.logout()
        for i in range(12):
            resp = self.client.get(reverse('leagues:public_invite', kwargs={'code': f'XXXX{i % 10}'}))
        self.assertEqual(resp.status_code, 200)


class PredictionRateLimitTest(RateLimitBase):
    def test_sixty_first_save_in_a_minute_is_blocked(self):
        user = User.objects.create_user(username='spammer', password='x', email='s@test.local')
        comp = Competition.objects.create(external_id=701, name='C', code='RL', country='F', season='2026')
        league = League.objects.create(name='RL', creator=user)
        league.competitions.add(comp)
        league.members.add(user)
        match = Match.objects.create(
            external_id=70001, competition=comp,
            home_team=Team.objects.create(external_id=7001, slug='rl-a', name='A'),
            away_team=Team.objects.create(external_id=7002, slug='rl-b', name='B'),
            datetime=timezone.now() + dt.timedelta(days=2),
            cote_home=18, cote_draw=250, cote_away=22,
        )
        self.client.force_login(user)
        url = reverse('predictions:submit', kwargs={'match_pk': match.pk})
        for i in range(60):
            self.assertEqual(self.client.post(url, {'score_h': str(i), 'score_a': '3'}).status_code, 200)
        self.assertEqual(self.client.post(url, {'score_h': '1', 'score_a': '3'}).status_code, 429)
