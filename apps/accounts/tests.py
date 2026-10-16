from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from apps.leagues.models import League
from apps.matches.models import Competition


def _make_comp(code, active=True):
    return Competition.objects.create(
        name=f'Comp {code}',
        code=code,
        external_id=-(hash(code) % 90000 + 10000),
        season='2025',
        scoring_system='FIXED',
        good_gap_pts=3,
        is_active=active,
    )


REGISTER_URL = reverse('accounts:register')

VALID_FORM = {
    'username': 'newuser',
    'email': 'newuser@test.local',
    'first_name': 'New',
    'last_name': 'User',
    'display_name': '',
    'password1': 'Str0ng!Pass99',
    'password2': 'Str0ng!Pass99',
    'cf-turnstile-response': 'mock',
}


class RegisterAutoLoginTest(TestCase):
    """After successful registration, user is logged in and redirected to predictions."""

    @patch('apps.accounts.views._verify_turnstile', return_value=True)
    def test_register_logs_in_and_redirects_to_predictions(self, _mock):
        response = self.client.post(REGISTER_URL, VALID_FORM)
        self.assertRedirects(response, reverse('predictions:index'), fetch_redirect_response=False)
        # Session should contain auth info — user is logged in
        self.assertIn('_auth_user_id', self.client.session)

    @patch('apps.accounts.views._verify_turnstile', return_value=True)
    def test_register_with_next_redirects_to_next(self, _mock):
        next_url = '/some-safe-path/'
        response = self.client.post(
            REGISTER_URL + f'?next={next_url}',
            {**VALID_FORM, 'next': next_url},
        )
        self.assertRedirects(response, next_url, fetch_redirect_response=False)

    @patch('apps.accounts.views._verify_turnstile', return_value=False)
    def test_register_captcha_failure_preserves_next(self, _mock):
        """CAPTCHA failure re-renders form; next_url is in context for hidden field."""
        next_url = '/leagues/invite/ABCDE/'
        response = self.client.post(
            REGISTER_URL + f'?next={next_url}',
            {**VALID_FORM, 'next': next_url},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['next_url'], next_url)


class RegisterThenJoinLeagueTest(TestCase):
    """Full registration → auto-login → invite URL → auto-join flow."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        cls.creator = User.objects.create_user(
            username='reg_creator', password='pass', email='rc@test.local'
        )
        cls.comp = _make_comp('REGTEST')
        cls.league = League.objects.create(name='Reg Test League', creator=cls.creator)
        cls.league.competitions.add(cls.comp)
        cls.league.members.add(cls.creator)

    @patch('apps.accounts.views._verify_turnstile', return_value=True)
    def test_register_then_joins_league(self, _mock):
        """User registers with ?next=invite URL, ends up in the league."""
        invite_url = reverse('leagues:public_invite', kwargs={'code': self.league.invite_code})
        response = self.client.post(
            REGISTER_URL + f'?next={invite_url}',
            {
                **VALID_FORM,
                'username': 'league_joiner',
                'email': 'lj@test.local',
                'next': invite_url,
            },
        )
        # Should redirect to invite URL (which then auto-joins and redirects to detail)
        self.assertRedirects(response, invite_url, fetch_redirect_response=False)

        # Follow through to confirm auto-join
        response2 = self.client.get(invite_url)
        self.assertRedirects(
            response2,
            reverse('leagues:detail', kwargs={'pk': self.league.pk}),
            fetch_redirect_response=False,
        )
        from django.contrib.auth import get_user_model
        User = get_user_model()
        joiner = User.objects.get(username='league_joiner')
        self.assertTrue(self.league.members.filter(pk=joiner.pk).exists())
