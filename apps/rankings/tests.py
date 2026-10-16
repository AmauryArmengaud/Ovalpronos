from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.rankings.views import _assign_ranks


def _e(*specs):
    """Build an entries list from (points, exact, gap) tuples."""
    return [{'total_points': p, 'count_exact': e, 'count_gap': g} for p, e, g in specs]


class AssignRanksTest(SimpleTestCase):
    def test_no_ties(self):
        entries = _e((10, 2, 1), (8, 1, 1), (6, 0, 0))
        _assign_ranks(entries)
        self.assertEqual([e['rank'] for e in entries], [1, 2, 3])

    def test_tie_at_top(self):
        entries = _e((10, 2, 1), (10, 2, 1), (8, 1, 0))
        _assign_ranks(entries)
        self.assertEqual([e['rank'] for e in entries], [1, 1, 3])

    def test_tie_in_middle(self):
        entries = _e((10, 2, 1), (8, 1, 1), (8, 1, 1), (5, 0, 0))
        _assign_ranks(entries)
        self.assertEqual([e['rank'] for e in entries], [1, 2, 2, 4])

    def test_three_way_tie_at_top(self):
        entries = _e((5, 1, 0), (5, 1, 0), (5, 1, 0))
        _assign_ranks(entries)
        self.assertEqual([e['rank'] for e in entries], [1, 1, 1])

    def test_zero_pts_tie(self):
        entries = _e((5, 1, 0), (0, 0, 0), (0, 0, 0))
        _assign_ranks(entries)
        self.assertEqual([e['rank'] for e in entries], [1, 2, 2])

    def test_single_entry(self):
        entries = _e((10, 1, 0))
        _assign_ranks(entries)
        self.assertEqual(entries[0]['rank'], 1)

    def test_tie_broken_by_exact(self):
        entries = _e((10, 2, 0), (10, 1, 0))
        _assign_ranks(entries)
        self.assertEqual([e['rank'] for e in entries], [1, 2])

    def test_tie_broken_by_gap(self):
        entries = _e((10, 1, 2), (10, 1, 1))
        _assign_ranks(entries)
        self.assertEqual([e['rank'] for e in entries], [1, 2])

    def test_mutates_in_place(self):
        entries = _e((10, 1, 0), (5, 0, 0))
        result = _assign_ranks(entries)
        self.assertIs(result, entries)

    def test_multiple_tie_groups(self):
        # 1,1,3,3,5
        entries = _e((10, 2, 0), (10, 2, 0), (8, 1, 0), (8, 1, 0), (5, 0, 0))
        _assign_ranks(entries)
        self.assertEqual([e['rank'] for e in entries], [1, 1, 3, 3, 5])


class RankingsViewTest(TestCase):
    """Smoke tests — catch template errors (TemplateSyntaxError, missing context) early."""

    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model
        from apps.matches.models import Competition
        from apps.leagues.models import League

        User = get_user_model()
        cls.user = User.objects.create_user(
            username='test_ranker', password='pass', email='ranker@test.local'
        )
        cls.comp = Competition.objects.create(
            name='Test Cup', code='TESTCUP', external_id=-9001, season='2025',
            scoring_system='FIXED', good_gap_pts=3, is_active=True,
        )
        # Duplicate-name competition — triggers chip_label season disambiguation
        cls.comp2 = Competition.objects.create(
            name='Test Cup', code='TESTCUP2', external_id=-9002, season='2024',
            scoring_system='FIXED', good_gap_pts=3, is_active=True,
        )
        cls.league = League.objects.create(name='Test League', creator=cls.user)
        cls.league.competitions.add(cls.comp)
        cls.league.members.add(cls.user)

    def setUp(self):
        self.client.force_login(self.user)

    def test_rankings_page_renders(self):
        response = self.client.get(reverse('rankings:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Cup')

    def test_rankings_comp_filter_renders(self):
        response = self.client.get(reverse('rankings:index'), {'comp': self.comp.pk})
        self.assertEqual(response.status_code, 200)

    def test_rankings_league_tab_renders(self):
        response = self.client.get(reverse('rankings:index'), {'league': self.league.pk})
        self.assertEqual(response.status_code, 200)

    def test_duplicate_comp_names_show_season(self):
        # chip_label must include season when the same name appears twice
        response = self.client.get(reverse('rankings:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Test Cup 2025')
        self.assertContains(response, 'Test Cup 2024')

    def test_unknown_comp_pk_does_not_crash(self):
        response = self.client.get(reverse('rankings:index'), {'comp': 99999})
        self.assertEqual(response.status_code, 200)
