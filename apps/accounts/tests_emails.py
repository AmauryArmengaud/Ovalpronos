"""
Email template tests.

Verifies for each transactional email:
  - both text and HTML parts are present
  - subject is translated (no raw English subject)
  - no "127.0.0.1" or "localhost" domain leaks into the subject line
  - reset link uses the correct URL pattern (password reset only)
  - subject contains no newlines (injection guard)
"""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

User = get_user_model()

_EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'


@override_settings(EMAIL_BACKEND=_EMAIL_BACKEND, SITE_URL='https://ovalpronos.com')
class PasswordResetEmailTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='hunter2',
        )

    def _send_reset(self):
        self.client.post(
            reverse('accounts:password_reset'),
            {'email': 'test@example.com'},
        )

    def test_sends_one_email(self):
        self._send_reset()
        self.assertEqual(len(mail.outbox), 1)

    def test_has_text_and_html_parts(self):
        self._send_reset()
        msg = mail.outbox[0]
        self.assertTrue(msg.body.strip(), 'text part should not be empty')
        content_types = [ct for _, ct in getattr(msg, 'alternatives', [])]
        self.assertIn('text/html', content_types, 'HTML part missing')

    def test_subject_is_french(self):
        self._send_reset()
        subject = mail.outbox[0].subject
        self.assertIn('mot de passe', subject.lower())

    def test_subject_has_no_domain(self):
        self._send_reset()
        subject = mail.outbox[0].subject
        self.assertNotIn('127.0.0.1', subject)
        self.assertNotIn('localhost', subject)
        self.assertNotIn('example.com', subject)

    def test_subject_has_no_newline(self):
        self._send_reset()
        subject = mail.outbox[0].subject
        self.assertNotIn('\n', subject)
        self.assertNotIn('\r', subject)

    def test_reset_link_in_text_body(self):
        self._send_reset()
        body = mail.outbox[0].body
        # The reset link must contain the confirm path, not a tracking URL.
        self.assertIn('/accounts/password-reset-confirm/', body)

    def test_reset_link_in_html_body(self):
        self._send_reset()
        html = next(
            content for content, ct in mail.outbox[0].alternatives
            if ct == 'text/html'
        )
        self.assertIn('/accounts/password-reset-confirm/', html)

    def test_timeout_hours_in_body(self):
        with override_settings(PASSWORD_RESET_TIMEOUT=86400):
            self._send_reset()
        body = mail.outbox[0].body
        self.assertIn('24', body)


@override_settings(
    EMAIL_BACKEND=_EMAIL_BACKEND,
    SITE_URL='https://ovalpronos.com',
    LANGUAGE_CODE='fr',
)
class ResultsSummaryEmailTest(TestCase):
    def _fake_prediction(self, result_type='WIN', pts=18):
        home = MagicMock()
        home.name = 'Toulouse'
        home.short_name = 'TLO'
        away = MagicMock()
        away.name = 'Racing 92'
        away.short_name = 'RAC'
        match = MagicMock()
        match.home_team = home
        match.away_team = away
        match.home_score = 24
        match.away_score = 10
        p = MagicMock()
        p.match = match
        p.predicted_home_score = 24
        p.predicted_away_score = 8
        p.result_type = result_type
        p.points_earned = pts
        p.get_result_type_display.return_value = result_type
        return p

    def _call_send(self):
        from apps.predictions.tasks import send_results_summary
        from apps.matches.models import Match, Competition
        from apps.predictions.models import Prediction

        user = User.objects.create_user(
            username='player1', email='player@example.com', password='x',
        )
        comp = Competition.objects.create(
            name='Top 14', code='TOP14', season=2025,
            external_id=999,
            scoring_system='COTES', good_gap_pts=3,
        )
        match = Match.objects.create(
            competition=comp,
            home_team=_make_team('Toulouse', 'toulouse'),
            away_team=_make_team('Racing', 'racing'),
            external_id=88001,
            datetime=_future_dt(),
            round='26',
            status=Match.STATUS_FINISHED,
            home_score=24,
            away_score=10,
            cote_home=18,
            cote_draw=40,
            cote_away=55,
        )
        Prediction.objects.create(
            user=user,
            match=match,
            predicted_home_score=24,
            predicted_away_score=8,
            points_earned=18,
            result_type='WIN',
        )
        send_results_summary(competition_id=comp.pk, round_label='26')
        return user

    def test_sends_email_with_text_and_html(self):
        self._call_send()
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertTrue(msg.body.strip(), 'text part empty')
        content_types = [ct for _, ct in getattr(msg, 'alternatives', [])]
        self.assertIn('text/html', content_types)

    def test_text_and_html_differ(self):
        self._call_send()
        msg = mail.outbox[0]
        html = next(c for c, ct in msg.alternatives if ct == 'text/html')
        self.assertNotEqual(msg.body.strip(), html.strip())

    def test_subject_contains_competition_and_round(self):
        self._call_send()
        subject = mail.outbox[0].subject
        self.assertIn('Top 14', subject)
        self.assertIn('26', subject)

    def test_no_localhost_in_subject(self):
        self._call_send()
        self.assertNotIn('127.0.0.1', mail.outbox[0].subject)


# ── Helpers ───────────────────────────────────────────────────────────────────

_team_counter = 0

def _make_team(name, slug):
    global _team_counter
    from apps.matches.models import Team
    _team_counter += 1
    return Team.objects.get_or_create(
        slug=slug, defaults={'name': name, 'external_id': 9000 + _team_counter},
    )[0]


def _future_dt():
    from django.utils import timezone
    import datetime
    return timezone.now() + datetime.timedelta(days=7)
