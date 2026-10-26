from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import resolve

from .admin_views import CompetitionImportView
from .tests import make_competition, make_user


class CompetitionImportRouteTest(TestCase):
    """Regression: admin.site.urls' catch-all used to swallow this route, so the page never opened"""

    def setUp(self):
        self.comp = make_competition(code='TOP14', is_active=True)
        self.url = f'/admin/matches/competition/{self.comp.pk}/import/'

    def test_route_reaches_the_import_view(self):
        self.assertIs(resolve(self.url).func.view_class, CompetitionImportView)

    def test_staff_sees_confirmation_then_sync_runs(self):
        self.client.force_login(get_user_model().objects.create_superuser('boss', 'boss@test.local', 'x'))
        self.assertTemplateUsed(self.client.get(self.url), 'admin/matches/import.html')
        with patch('apps.matches.admin_views.sync_competition_matches', return_value={'created': 2, 'updated': 3}) as sync:
            response = self.client.post(self.url)
        sync.assert_called_once_with('TOP14')
        self.assertRedirects(response, f'/admin/matches/competition/{self.comp.pk}/change/', fetch_redirect_response=False)

    def test_players_are_sent_to_admin_login(self):
        self.client.force_login(make_user())
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])
