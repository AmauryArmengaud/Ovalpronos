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
        self.assertContains(
            response,
            'href="/accounts/register/?next=%2Fcompetitions%2Fnations%2F&amp;utm_source=whatsapp'
            '&amp;utm_campaign=relance_cdn&amp;landing=%2Fcompetitions%2Fnations%2F"',
        )
        self.assertNotContains(response, 'fbclid=x&amp;')

    def test_logged_in_player_in_a_league_goes_to_predictions(self):
        from apps.leagues.models import League
        user = get_user_model().objects.create_user(username='u', email='u@test.local', password='x')
        league = League.objects.create(name='Potes', creator=user)
        league.members.add(user)
        league.competitions.add(self.comp)
        self.client.force_login(user)
        self.assertRedirects(self.client.get(self.url), reverse('predictions:index'), fetch_redirect_response=False)

    def test_logged_in_player_without_league_is_sent_to_create_one(self):
        user = get_user_model().objects.create_user(username='u', email='u@test.local', password='x')
        self.client.force_login(user)
        self.assertRedirects(
            self.client.get(self.url), reverse('leagues:create') + '?competition=NATIONS', fetch_redirect_response=False
        )
        form = self.client.get(reverse('leagues:create'), {'competition': 'nations'}).context['form']
        self.assertEqual(form.initial['competitions'], [self.comp])

    def test_login_link_returns_to_competition(self):
        response = self.client.get(self.url)
        self.assertContains(response, 'href="/accounts/login/?next=%2Fcompetitions%2Fnations%2F')


class CompetitionLandingConversionTest(TestCase):

    def setUp(self):
        self.comp = make_competition(name='Nations Championship', code='NATIONS', is_active=True)
        self.url = reverse('matches:competition_landing', kwargs={'code': 'NATIONS'})

    def _upcoming(self, days):
        return make_match(self.comp, make_team(), make_team(), status='SCHEDULED',
                          datetime=timezone.now() + timedelta(days=days, hours=1), home_score=None, away_score=None)

    def test_deadline_counts_days_to_first_match(self):
        self._upcoming(12)
        response = self.client.get(self.url)
        self.assertEqual(response.context['kickoff_days'], 12)
        self.assertFalse(response.context['competition_started'])
        self.assertContains(response, 'landing-urgency')

    def test_no_deadline_without_upcoming_match(self):
        self.assertNotContains(self.client.get(self.url), 'landing-urgency')

    def test_social_proof_hidden_below_threshold(self):
        from apps.leagues.models import League
        from .views import SOCIAL_PROOF_MIN_PLAYERS
        User = get_user_model()
        league = League.objects.create(name='Potes', creator=User.objects.create_user('c', 'c@t.local', 'x'))
        league.competitions.add(self.comp)
        league.members.add(*[User.objects.create_user(f'p{i}', f'p{i}@t.local', 'x')
                             for i in range(SOCIAL_PROOF_MIN_PLAYERS - 1)])
        self.assertNotContains(self.client.get(self.url), 'landing-proof')
        league.members.add(league.creator)
        response = self.client.get(self.url)
        self.assertEqual(response.context['player_count'], SOCIAL_PROOF_MIN_PLAYERS)
        self.assertContains(response, 'landing-proof')

    def test_create_league_cta_returns_to_prefilled_league_form(self):
        self.assertContains(
            self.client.get(self.url),
            'href="/accounts/register/?next=%2Fleagues%2Fcreate%2F%3Fcompetition%3DNATIONS&amp;landing=',
        )

    def test_jsonld_lists_upcoming_matches_and_escapes_markup(self):
        match = self._upcoming(3)
        match.venue = '</script><b>'
        match.save()
        response = self.client.get(self.url)
        self.assertContains(response, '"@type": "SportsEvent"')
        self.assertNotContains(response, '</script><b>')

    def test_consent_banner_below_hero(self):
        html = self.client.get(self.url).content.decode()
        self.assertEqual(html.count('id="consent-banner"'), 1)
        self.assertLess(html.index('landing-hero'), html.index('id="consent-banner"'))


class CompetitionLandingShareTagsTest(TestCase):

    def setUp(self):
        self.comp = make_competition(name='Nations Championship', code='NATIONS', is_active=True)

    def test_canonical_and_og_url_drop_utm(self):
        response = self.client.get('/competitions/nations/?utm_source=whatsapp&fbclid=abc')
        self.assertContains(response, '<link rel="canonical" href="http://testserver/competitions/nations/">')
        self.assertContains(response, '<meta property="og:url" content="http://testserver/competitions/nations/">')
        self.assertContains(response, 'og:locale')
        self.assertContains(response, '<meta name="twitter:card" content="summary_large_image">')

    def test_og_image_falls_back_then_uses_competition_image(self):
        url = '/competitions/nations/'
        self.assertContains(self.client.get(url), 'img/og-img.png')
        self.comp.og_image = 'og/nations.png'
        self.comp.save()
        self.assertContains(self.client.get(url), 'content="http://testserver/media/og/nations.png"')
