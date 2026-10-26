from django.test import TestCase

from apps.matches.tests import make_competition, make_match, make_prediction, make_team
from .models import CustomUser

CHANGELIST = '/admin/accounts/customuser/'


class UserAdminAttributionTest(TestCase):

    def setUp(self):
        self.admin = CustomUser.objects.create_superuser('boss', 'boss@test.local', 'x')
        self.client.force_login(self.admin)
        self.active = CustomUser.objects.create_user('active', 'active@test.local', 'x', signup_source='whatsapp')
        self.idle = CustomUser.objects.create_user('idle', 'idle@test.local', 'x', signup_source='linkedin')
        comp = make_competition(code='ADM', is_active=True)
        make_prediction(self.active, make_match(comp, make_team(), make_team()))

    def test_activated_filter(self):
        response = self.client.get(CHANGELIST, {'activated': 'yes'})
        self.assertContains(response, '>active<')
        self.assertNotContains(response, '>idle<')
        response = self.client.get(CHANGELIST, {'activated': 'no'})
        self.assertContains(response, '>idle<')
        self.assertNotContains(response, '>active<')

    def test_csv_export_has_attribution_and_no_email(self):
        response = self.client.post(CHANGELIST, {
            'action': 'export_attribution_csv',
            '_selected_action': [self.active.pk, self.idle.pk],
        })
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        body = response.content.decode('utf-8-sig')
        self.assertIn('Source;', body.splitlines()[0])
        self.assertIn(';whatsapp;', body)
        self.assertNotIn('@test.local', body)
