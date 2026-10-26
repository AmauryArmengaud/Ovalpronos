import csv
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import CustomUser, Invitation

REGISTER_URL = reverse('accounts:register')

VALID_FORM = {
    'username': 'Pepito',
    'email': 'pepito@test.local',
    'first_name': 'Theo',
    'last_name': 'B',
    'display_name': 'Pepito',
    'password1': 'Str0ng!Pass99',
    'password2': 'Str0ng!Pass99',
    'cf-turnstile-response': 'mock',
}


class RegisterInvitationPrefillTest(TestCase):

    def setUp(self):
        self.invitation = Invitation.objects.create(
            email='pepito@test.local', pseudo='Fabien dans la mêlée', first_name='Fabien', last_name='Dupont', cohort='CDM_2023'
        )

    def test_invite_prefills_email_and_pseudo(self):
        response = self.client.get(REGISTER_URL, {'invite': self.invitation.token})
        form = response.context['form']
        self.assertEqual(form.initial['email'], 'pepito@test.local')
        self.assertEqual(form.initial['display_name'], 'Fabien dans la mêlée')
        self.assertEqual(form.initial['username'], 'Fabiendanslamêlée')
        self.assertEqual(form.initial['first_name'], 'Fabien')
        self.assertEqual(form.initial['last_name'], 'Dupont')
        self.assertContains(response, self.invitation.token)

    def test_unknown_token_shows_empty_form(self):
        response = self.client.get(REGISTER_URL, {'invite': 'nope'})
        self.assertNotIn('email', response.context['form'].initial)
        self.assertIsNone(response.context['invitation'])

    def test_used_token_shows_empty_form(self):
        self.invitation.used_at = timezone.now()
        self.invitation.save()
        response = self.client.get(REGISTER_URL, {'invite': self.invitation.token})
        self.assertNotIn('email', response.context['form'].initial)

    @patch('apps.accounts.views._verify_turnstile', return_value=True)
    def test_register_marks_invitation_used(self, _mock):
        self.client.post(REGISTER_URL, {**VALID_FORM, 'invite': self.invitation.token})
        self.invitation.refresh_from_db()
        self.assertIsNotNone(self.invitation.used_at)
        self.assertEqual(self.invitation.user, CustomUser.objects.get(username='Pepito'))


class ImportInvitationsCommandTest(TestCase):

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.contacts = self.tmp / 'contacts.csv'
        self.output = self.tmp / 'tokens.csv'
        with open(self.contacts, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['EMAIL', 'PSEUDO', 'PRENOM', 'NOM', 'COHORTE', 'TYPE'])
            writer.writerow(['Tom@test.local', 'Tom', 'Thomas', 'Montaudran', '6N_2023', 'PERSO'])
            writer.writerow(['already@test.local', 'Old', 'Jean', 'Old', 'CDM_2023', 'PERSO'])
        CustomUser.objects.create_user(username='already', email='already@test.local', password='x')

    def _run(self):
        call_command('import_invitations', str(self.contacts), output=str(self.output), stdout=open('/dev/null', 'w'))
        with open(self.output, newline='', encoding='utf-8') as f:
            return list(csv.DictReader(f))

    def test_creates_invitations_and_skips_registered_emails(self):
        rows = self._run()
        invitation = Invitation.objects.get()
        self.assertEqual(invitation.email, 'tom@test.local')
        self.assertEqual(invitation.cohort, '6N_2023')
        self.assertEqual((invitation.first_name, invitation.last_name), ('Thomas', 'Montaudran'))
        self.assertEqual(rows, [{'EMAIL': 'tom@test.local', 'TOKEN': invitation.token}])

    def test_rerun_keeps_tokens(self):
        first = self._run()
        second = self._run()
        self.assertEqual(first, second)
        self.assertEqual(Invitation.objects.count(), 1)


class RegisterSignupSourceTest(TestCase):

    @patch('apps.accounts.views._verify_turnstile', return_value=True)
    def test_utm_stored_on_account(self, _mock):
        response = self.client.get(REGISTER_URL, {'utm_source': 'whatsapp', 'utm_campaign': 'relance_cdn'})
        self.assertContains(response, 'name="utm_source" value="whatsapp"')
        self.client.post(REGISTER_URL, {**VALID_FORM, 'utm_source': 'whatsapp', 'utm_campaign': 'relance_cdn'})
        user = CustomUser.objects.get(username='Pepito')
        self.assertEqual((user.signup_source, user.signup_campaign), ('whatsapp', 'relance_cdn'))

    @patch('apps.accounts.views._verify_turnstile', return_value=True)
    def test_league_invite_without_utm(self, _mock):
        from apps.leagues.models import League
        creator = CustomUser.objects.create_user(username='creator', email='c@test.local', password='x')
        league = League.objects.create(name='Les potes', creator=creator)
        next_url = reverse('leagues:public_invite', kwargs={'code': league.invite_code})
        self.client.post(REGISTER_URL, {**VALID_FORM, 'next': next_url})
        self.assertEqual(CustomUser.objects.get(username='Pepito').signup_source, 'league_invite')

    @patch('apps.accounts.views._verify_turnstile', return_value=True)
    def test_direct_signup_is_direct(self, _mock):
        self.client.post(REGISTER_URL, VALID_FORM)
        self.assertEqual(CustomUser.objects.get(username='Pepito').signup_source, 'direct')
