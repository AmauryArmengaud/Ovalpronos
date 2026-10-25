"""Account deletion: self-service view, league hand-over, personal data removal."""
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.leagues.models import League
from apps.matches.models import Competition, Match, Team
from apps.predictions.models import Prediction
from apps.rankings.models import UserScore

User = get_user_model()


def make_user(name):
    return User.objects.create_user(username=name, password='pass-1234', email=f'{name}@test.local')


def make_league(creator, *members):
    league = League.objects.create(name=f'League of {creator.username}', creator=creator)
    league.members.add(creator, *members)
    return league


class LeagueHandOverTest(TestCase):
    def test_league_passes_to_oldest_remaining_member(self):
        creator, first, second = make_user('creator'), make_user('first'), make_user('second')
        league = League.objects.create(name='L', creator=creator)
        league.members.add(creator)
        league.members.add(first)
        league.members.add(second)
        creator.delete()
        league.refresh_from_db()
        self.assertEqual(league.creator, first)
        self.assertEqual(set(league.members.all()), {first, second})

    def test_league_is_deleted_when_creator_was_alone(self):
        creator = make_user('alone')
        league = make_league(creator)
        creator.delete()
        self.assertFalse(League.objects.filter(pk=league.pk).exists())

    def test_member_deletion_keeps_league(self):
        creator, member = make_user('owner'), make_user('member')
        league = make_league(creator, member)
        member.delete()
        league.refresh_from_db()
        self.assertEqual(league.creator, creator)
        self.assertEqual(list(league.members.all()), [creator])

    def test_bulk_delete_from_admin_also_hands_over(self):
        creator, member = make_user('bulk-owner'), make_user('bulk-member')
        league = make_league(creator, member)
        User.objects.filter(pk=creator.pk).delete()
        league.refresh_from_db()
        self.assertEqual(league.creator, member)


_media = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=_media)
class AccountDeleteViewTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_media, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.user = make_user('leaver')
        self.client.force_login(self.user)
        self.url = reverse('accounts:delete')

    def test_page_explains_what_is_deleted(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'name="password"')

    def test_wrong_password_deletes_nothing(self):
        resp = self.client.post(self.url, {'password': 'wrong'})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_correct_password_deletes_account_and_personal_data(self):
        self.user.avatar = SimpleUploadedFile('me.png', b'\x89PNG fake', content_type='image/png')
        self.user.save()
        avatar_path = self.user.avatar.path
        comp = Competition.objects.create(external_id=901, name='C', code='DEL', country='F', season='2026')
        match = Match.objects.create(
            external_id=90001, competition=comp,
            home_team=Team.objects.create(external_id=9101, slug='del-a', name='A'),
            away_team=Team.objects.create(external_id=9102, slug='del-b', name='B'),
            datetime='2026-01-01T15:00:00Z', status='FINISHED', home_score=1, away_score=0,
        )
        Prediction.objects.create(user=self.user, match=match, predicted_home_score=1, predicted_away_score=0)
        UserScore.objects.create(user=self.user, points=10)

        resp = self.client.post(self.url, {'password': 'pass-1234'})

        self.assertRedirects(resp, reverse('matches:home'), fetch_redirect_response=False)
        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(Prediction.objects.filter(match=match).exists())
        self.assertFalse(UserScore.objects.exists())
        import os
        self.assertFalse(os.path.exists(avatar_path))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_anonymous_is_sent_to_login(self):
        self.client.logout()
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp['Location'])
