from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from apps.leagues.models import League
from apps.matches.models import LandingView
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

    def test_report_by_source_with_outside_landing_section(self):
        out = StringIO()
        call_command('campaign_report', 'nations', stdout=out)
        lines = [line.split() for line in out.getvalue().splitlines()]
        self.assertIn(['whatsapp', '40', '2', '5.0%', '1', '1'], lines)
        self.assertIn(['linkedin', '10', '0', '0.0%', '0', '0'], lines)
        self.assertIn(['direct', '1', '0', '0'], lines)
        self.assertIn('Hors landing', out.getvalue())
