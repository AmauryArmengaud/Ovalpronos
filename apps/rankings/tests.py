from django.test import SimpleTestCase

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
