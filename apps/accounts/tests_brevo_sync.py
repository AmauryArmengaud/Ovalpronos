from io import StringIO
from unittest.mock import Mock, patch

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from apps.leagues.models import League

from .models import CustomUser, Invitation

PUT = 'apps.accounts.management.commands.sync_brevo_contacts.requests.put'


def ok(status=204):
    return Mock(status_code=status, raise_for_status=Mock())


def sent_attributes(mock_put):
    return {c.args[0].rsplit('/', 1)[1]: c.kwargs['json']['attributes'] for c in mock_put.call_args_list}


@override_settings(ANYMAIL={'BREVO_API_KEY': 'test-key'})
class SyncBrevoContactsTest(TestCase):

    def setUp(self):
        self.player = CustomUser.objects.create_user('pepito', 'pepito@test.local', 'Str0ng!Pass99')
        Invitation.objects.create(email='pepito@test.local', pseudo='Pepito', user=self.player)

    def run_command(self):
        call_command('sync_brevo_contacts', stdout=StringIO(), stderr=StringIO())

    def make_league(self, name, members):
        league = League.objects.create(name=name, creator=members[0])
        league.members.add(*members)
        return league

    @patch(PUT, return_value=ok())
    def test_sends_largest_league(self, mock_put):
        friends = [CustomUser.objects.create_user(f'f{i}', f'f{i}@test.local', 'x') for i in range(3)]
        self.make_league('Les piliers de comptoir', [self.player, *friends])
        self.make_league('Ligue du bureau', [self.player, friends[0]])

        self.run_command()

        self.assertEqual(sent_attributes(mock_put)['pepito%40test.local'], {
            'INSCRIT_V2': True, 'LIGUE_NOM': 'Les piliers de comptoir', 'NB_MEMBRES_LIGUE': 4,
        })
        call = mock_put.call_args
        self.assertEqual(call.kwargs['headers'], {'api-key': 'test-key'})
        self.assertEqual(call.kwargs['params'], {'identifierType': 'email_id'})

    @patch(PUT, return_value=ok())
    def test_player_without_league_gets_empty_league(self, mock_put):
        self.run_command()

        self.assertEqual(sent_attributes(mock_put)['pepito%40test.local'], {
            'INSCRIT_V2': True, 'LIGUE_NOM': '', 'NB_MEMBRES_LIGUE': 0,
        })

    @patch(PUT, return_value=ok())
    def test_includes_2023_player_who_signed_up_without_link(self, mock_put):
        Invitation.objects.create(email='sanslien@test.local', pseudo='SansLien')
        CustomUser.objects.create_user('sanslien', 'SansLien@Test.local', 'x')

        self.run_command()

        self.assertIn('sanslien%40test.local', sent_attributes(mock_put))

    @patch(PUT, return_value=ok())
    def test_ignores_new_players_and_unused_invitations(self, mock_put):
        CustomUser.objects.create_user('nouveau', 'nouveau@test.local', 'x')
        Invitation.objects.create(email='pas.revenu@test.local', pseudo='PasRevenu')

        self.run_command()

        self.assertEqual(list(sent_attributes(mock_put)), ['pepito%40test.local'])

    @patch(PUT, return_value=ok(404))
    def test_contact_missing_from_brevo_is_not_a_failure(self, mock_put):
        out = StringIO()
        call_command('sync_brevo_contacts', stdout=out, stderr=StringIO())

        self.assertIn('1 absent(s) de Brevo', out.getvalue())

    @patch(PUT)
    def test_failure_keeps_going_then_fails_the_command(self, mock_put):
        Invitation.objects.create(email='autre@test.local', pseudo='Autre')
        CustomUser.objects.create_user('autre', 'autre@test.local', 'x')
        mock_put.side_effect = [requests.ConnectionError('boom'), ok()]

        with self.assertRaisesMessage(CommandError, '1 contact(s) mis à jour, 0 absent(s) de Brevo, 1 échec(s)'):
            self.run_command()
        self.assertEqual(mock_put.call_count, 2)

    @override_settings(ANYMAIL={'BREVO_API_KEY': ''})
    @patch(PUT)
    def test_missing_api_key_sends_nothing(self, mock_put):
        with self.assertRaises(CommandError):
            self.run_command()
        mock_put.assert_not_called()
