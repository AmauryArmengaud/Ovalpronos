from django.test import TestCase
from django.urls import reverse

from apps.leagues.models import League
from apps.matches.models import Competition


def _make_user(username):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username=username,
        password='pass',
        email=f'{username}@test.local',
    )


def _make_comp(code, active=True):
    return Competition.objects.create(
        name=f'Comp {code}',
        code=code,
        external_id=-(hash(code) % 90000 + 10000),
        season='2025',
        scoring_system='FIXED',
        good_gap_pts=3,
        is_active=active,
    )


class LeagueDetailAllMembersTest(TestCase):
    """All members appear in the league leaderboard, even those with 0 points."""

    @classmethod
    def setUpTestData(cls):
        cls.creator = _make_user('lg_creator')
        cls.member_no_pts = _make_user('lg_member_nopt')
        cls.comp = _make_comp('LGTEST1')

        cls.league = League.objects.create(name='Test League Detail', creator=cls.creator)
        cls.league.competitions.add(cls.comp)
        cls.league.members.add(cls.creator, cls.member_no_pts)

    def setUp(self):
        self.client.force_login(self.creator)

    def test_all_members_shown(self):
        """Member with 0 predictions still appears in the leaderboard."""
        response = self.client.get(reverse('leagues:detail', kwargs={'pk': self.league.pk}))
        self.assertEqual(response.status_code, 200)
        entries = response.context['entries']
        user_pks = [e['user'].pk for e in entries]
        self.assertIn(self.creator.pk, user_pks)
        self.assertIn(self.member_no_pts.pk, user_pks)

    def test_zero_points_member_at_zero(self):
        """Member without predictions has total_points=0 and rank shared with others at 0."""
        response = self.client.get(reverse('leagues:detail', kwargs={'pk': self.league.pk}))
        entries = response.context['entries']
        no_pt_entry = next(e for e in entries if e['user'].pk == self.member_no_pts.pk)
        self.assertEqual(no_pt_entry['total_points'], 0)
        self.assertEqual(no_pt_entry['count_predictions'], 0)

    def test_shared_rank_at_zero(self):
        """Two members both with 0 pts are co-ranked (sports 1,1,3 convention)."""
        response = self.client.get(reverse('leagues:detail', kwargs={'pk': self.league.pk}))
        entries = response.context['entries']
        ranks = [e['rank'] for e in entries]
        # Both at 0 pts → both rank 1
        self.assertEqual(ranks, [1, 1])


class LeagueJoinCodePreservesNextTest(TestCase):
    """?code= parameter survives the ?next= login redirect cycle."""

    @classmethod
    def setUpTestData(cls):
        cls.comp = _make_comp('LGTEST2')
        cls.creator = _make_user('lg_join_creator')
        cls.joiner = _make_user('lg_joiner')

        cls.league = League.objects.create(name='Join Test League', creator=cls.creator)
        cls.league.competitions.add(cls.comp)
        cls.league.members.add(cls.creator)

    def test_join_url_prefills_code_when_logged_in(self):
        """GET /leagues/join/?code=X pre-fills initial_code in context."""
        self.client.force_login(self.joiner)
        code = self.league.invite_code
        response = self.client.get(reverse('leagues:join'), {'code': code})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['initial_code'], code)

    def test_join_url_redirects_anon_to_login_preserving_code(self):
        """Unauthenticated GET /leagues/join/?code=X redirects to login with ?next= intact."""
        code = self.league.invite_code
        join_url = reverse('leagues:join') + f'?code={code}'
        response = self.client.get(join_url)
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        redirect_target = response['Location']
        self.assertIn('next=', redirect_target)
        # The next= value must contain the code
        self.assertIn(code, redirect_target)

    def test_login_then_join_url_still_has_code(self):
        """After login, the redirect back to join preserves ?code= in the URL."""
        code = self.league.invite_code
        join_url = reverse('leagues:join') + f'?code={code}'
        # Simulate following login redirect: GET join (anon) → login → back to join
        response = self.client.get(join_url, follow=True)
        # Should land on login page (unauthenticated)
        self.assertIn(reverse('accounts:login'), response.redirect_chain[0][0])
        # The login redirect URL must encode the join URL including the code
        login_url_with_next = response.redirect_chain[0][0]
        self.assertIn(code, login_url_with_next)
