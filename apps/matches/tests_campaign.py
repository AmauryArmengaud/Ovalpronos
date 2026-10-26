from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.leagues.models import League
from apps.matches.models import LandingView
from apps.matches.services import campaign_report
from .tests import make_competition, make_match, make_prediction, make_team, make_user

URL = '/competitions/nations/'


class LandingViewCounterTest(TestCase):

    def setUp(self):
        self.comp = make_competition(name='Nations Championship', code='NATIONS', is_active=True)

    def counts(self):
        return dict(LandingView.objects.values_list('source', 'count'))

    def test_counts_per_source_and_day(self):
        self.client.get(URL + '?utm_source=WhatsApp ')
        self.client.get(URL + '?utm_source=whatsapp')
        self.client.get(URL, HTTP_REFERER='https://www.linkedin.com/feed/')
        self.client.get(URL)
        self.assertEqual(self.counts(), {'whatsapp': 2, 'linkedin': 1, 'direct': 1})
        self.assertEqual(LandingView.objects.get(source='direct').day, timezone.localdate())

    def test_link_previews_and_head_are_not_views(self):
        self.client.get(URL, HTTP_USER_AGENT='WhatsApp/2.24.1 A')
        self.client.get(URL, HTTP_USER_AGENT='LinkedInBot/1.0 (compatible; Mozilla/5.0)')
        self.client.get(URL, HTTP_USER_AGENT='facebookexternalhit/1.1')
        self.client.head(URL)
        self.assertEqual(self.counts(), {})

    def test_logged_in_players_are_not_counted(self):
        self.client.force_login(make_user())
        self.client.get(URL)
        self.assertEqual(self.counts(), {})


class CampaignReportTest(TestCase):

    def setUp(self):
        self.comp = make_competition(name='Nations Championship', code='NATIONS', is_active=True)
        today = timezone.localdate()
        LandingView.objects.create(competition=self.comp, day=today, source='whatsapp', count=40)
        LandingView.objects.create(competition=self.comp, day=today, source='linkedin', count=10)
        match = make_match(self.comp, make_team(), make_team())

        def signup(source, landing=URL):
            user = make_user()
            user.signup_source, user.signup_landing_path = source, landing
            user.save()
            return user

        active = signup('whatsapp')
        make_prediction(active, match)
        League.objects.create(name='Les potes', creator=active).competitions.add(self.comp)
        signup('whatsapp')
        signup('direct', landing='/')

    def test_service_splits_landing_and_outside_signups(self):
        report = campaign_report(self.comp)
        self.assertEqual(report['since'], timezone.localdate())
        self.assertEqual(report['landing']['rows'], [
            {'source': 'whatsapp', 'views': 40, 'signups': 2, 'conversion': 0.05, 'activated': 1, 'leagues': 1},
            {'source': 'linkedin', 'views': 10, 'signups': 0, 'conversion': 0.0, 'activated': 0, 'leagues': 0},
        ])
        self.assertEqual(report['landing']['total']['views'], 50)
        self.assertEqual(report['other']['rows'], [
            {'source': 'direct', 'views': None, 'signups': 1, 'conversion': None, 'activated': 0, 'leagues': 0},
        ])

    def test_since_excludes_older_signups_and_views(self):
        report = campaign_report(self.comp, timezone.localdate() + timedelta(days=1))
        self.assertEqual(report['landing']['rows'], [])
        self.assertEqual(report['other']['rows'], [])

    def test_command_prints_both_sections_in_french(self):
        out = StringIO()
        call_command('report_campaign', 'nations', stdout=out)
        lines = [line.split() for line in out.getvalue().splitlines()]
        self.assertIn(['whatsapp', '40', '2', '5.0%', '1', '1'], lines)
        self.assertIn(['direct', '1', '0', '0'], lines)
        self.assertIn('Hors landing', out.getvalue())

    def test_command_rejects_unknown_competition_and_bad_date(self):
        with self.assertRaises(CommandError):
            call_command('report_campaign', 'nope')
        with self.assertRaises(CommandError):
            call_command('report_campaign', 'nations', since='26/10/2026')


class CampaignReportAdminViewTest(TestCase):

    def setUp(self):
        self.comp = make_competition(name='Nations Championship', code='NATIONS', is_active=True)
        LandingView.objects.create(competition=self.comp, day=timezone.localdate(), source='whatsapp', count=40)
        self.url = reverse('admin_campaign_report', args=[self.comp.pk])

    def test_staff_sees_report(self):
        self.client.force_login(get_user_model().objects.create_superuser('boss', 'boss@test.local', 'x'))
        response = self.client.get(self.url)
        self.assertContains(response, 'Nations Championship')
        self.assertContains(response, '<th scope="row">whatsapp</th>', html=False)
        self.assertContains(response, 'Hors landing')

    def test_invalid_since_falls_back_to_campaign_start(self):
        self.client.force_login(get_user_model().objects.create_superuser('boss', 'boss@test.local', 'x'))
        for value in ('garbage', '2026-02-30'):
            self.assertEqual(self.client.get(self.url, {'since': value}).status_code, 200)

    def test_players_are_sent_to_admin_login(self):
        self.client.force_login(make_user())
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response['Location'])

    def test_competition_list_links_to_report(self):
        self.client.force_login(get_user_model().objects.create_superuser('boss', 'boss@test.local', 'x'))
        self.assertContains(self.client.get('/admin/matches/competition/'), f'href="{self.url}"')
