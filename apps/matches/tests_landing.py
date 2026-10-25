from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .tests import make_competition, make_match, make_team


class CompetitionLandingViewTest(TestCase):

    def setUp(self):
        self.comp = make_competition(name='Nations Championship', code='NATIONS', is_active=True)
        self.url = reverse('matches:competition_landing', kwargs={'code': 'nations'})

    def test_lists_upcoming_matches_with_winner_points(self):
        make_match(self.comp, make_team(), make_team(), status='SCHEDULED',
                   datetime=timezone.now() + timedelta(days=3), home_score=None, away_score=None)
        make_match(self.comp, make_team(), make_team())  # finished, not shown
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['upcoming']), 1)
        self.assertContains(response, '63 pts')

    def test_unknown_or_inactive_competition_is_404(self):
        make_competition(code='OLD', is_active=False)
        self.assertEqual(self.client.get(reverse('matches:competition_landing', kwargs={'code': 'old'})).status_code, 404)
        self.assertEqual(self.client.get(reverse('matches:competition_landing', kwargs={'code': 'nope'})).status_code, 404)

    def test_signup_links_carry_utm(self):
        response = self.client.get(self.url, {'utm_source': 'whatsapp', 'utm_campaign': 'relance_cdn', 'fbclid': 'x'})
        self.assertContains(response, 'href="/accounts/register/?utm_source=whatsapp&amp;utm_campaign=relance_cdn"', count=2)

    def test_logged_in_user_goes_to_predictions(self):
        user = get_user_model().objects.create_user(username='u', email='u@test.local', password='x')
        self.client.force_login(user)
        self.assertRedirects(self.client.get(self.url), reverse('predictions:index'), fetch_redirect_response=False)
