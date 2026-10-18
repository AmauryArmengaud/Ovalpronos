"""
Preview email templates in the browser without sending anything.
Only available when DEBUG=True.

Usage:
    python manage.py preview_emails

Writes HTML files to /tmp/ovalpronos_emails/ and prints the paths.
Open them in your browser to inspect the rendered output.
"""
import os
import tempfile

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.template.loader import render_to_string


_FAKE_SITE_URL = 'http://localhost:8000'

_FAKE_RESET_LINK = '/accounts/password-reset-confirm/NA/fake-token/'

_FAKE_RESET_CONTEXT = {
    'site_url': _FAKE_SITE_URL,
    'protocol': 'http',
    'domain': 'localhost:8000',
    'uid': 'NA',
    'token': 'fake-token-0000',
    'timeout_hours': settings.PASSWORD_RESET_TIMEOUT // 3600,
    'user': type('User', (), {'get_display_name': lambda self: 'Thomas Ramos', 'email': 'thomas@example.com'})(),
}


class _FakePrediction:
    def __init__(self, home, away, ph, pa, rh, ra, result_type, pts):
        home_team = type('T', (), {
            'name': home, 'short_name': home[:3].upper(),
        })()
        away_team = type('T', (), {
            'name': away, 'short_name': away[:3].upper(),
        })()
        self.match = type('M', (), {
            'home_team': home_team,
            'away_team': away_team,
            'home_score': rh,
            'away_score': ra,
        })()
        self.predicted_home_score = ph
        self.predicted_away_score = pa
        self.result_type = result_type
        self.points_earned = pts

    def get_result_type_display(self):
        return self.result_type


_FAKE_PREDICTIONS = [
    _FakePrediction('Toulouse', 'Racing 92', 24, 10, 27, 10, 'WIN', 18),
    _FakePrediction('Bordeaux-Bègles', 'Stade Français', 17, 20, 17, 20, 'EXACT', 63),
    _FakePrediction('Clermont', 'Lyon', 15, 12, 21, 8, 'GAP', 42),
    _FakePrediction('Bayonne', 'Toulon', 18, 18, 24, 7, 'MISS', 0),
]

_FAKE_SUMMARY_CONTEXT = {
    'site_url': _FAKE_SITE_URL,
    'user': type('User', (), {'get_display_name': lambda self: 'Thomas Ramos'})(),
    'competition_name': 'Top 14',
    'round_label': '26',
    'predictions': _FAKE_PREDICTIONS,
    'round_points': sum(p.points_earned for p in _FAKE_PREDICTIONS),
}

_EMAILS = [
    ('password_reset', 'emails/password_reset.html', _FAKE_RESET_CONTEXT),
    ('results_summary', 'emails/results_summary.html', _FAKE_SUMMARY_CONTEXT),
]


class Command(BaseCommand):
    help = 'Render email templates to /tmp/ovalpronos_emails/ for browser preview. DEBUG only.'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('preview_emails is only available when DEBUG=True.')

        out_dir = os.path.join(tempfile.gettempdir(), 'ovalpronos_emails')
        os.makedirs(out_dir, exist_ok=True)

        # Rewrite http://localhost:8000/static/... → file:///project/static/...
        # so images render without a running dev server.
        static_file_root = os.path.join(settings.BASE_DIR, 'static')
        static_file_url = f'file://{static_file_root}'
        localhost_static = f'{_FAKE_SITE_URL}/static'

        for name, template, context in _EMAILS:
            html = render_to_string(template, context)
            html = html.replace(localhost_static, static_file_url)
            html = html.replace(
                '/accounts/password-reset-confirm/NA/fake-token-0000/',
                '#preview-link',
            )
            path = os.path.join(out_dir, f'{name}.html')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(html)
            self.stdout.write(f'file://{path}')
