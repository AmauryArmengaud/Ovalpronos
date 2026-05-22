"""
Scoring tests for calculate_points().

All tests use MagicMock — no database access required.
"""
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from apps.predictions.services import calculate_points


def make_match(
    status='FINISHED',
    has_odds=True,
    home_score=17,
    away_score=22,
    cote_home=18,
    cote_draw=30,
    cote_away=63,
    scoring_system='COTES',
    good_gap_pts=3,
):
    match = MagicMock()
    match.status = status
    match.has_odds = has_odds
    match.home_score = home_score
    match.away_score = away_score
    match.cote_home = cote_home
    match.cote_draw = cote_draw
    match.cote_away = cote_away
    match.competition.scoring_system = scoring_system
    match.competition.good_gap_pts = good_gap_pts
    return match


def make_pred(home, away):
    pred = MagicMock()
    pred.predicted_home_score = home
    pred.predicted_away_score = away
    return pred


class CalculatePointsTests(SimpleTestCase):
    """11 scoring unit tests — no DB needed."""

    def test_exact_score(self):
        """Exact prediction: pred 17-22, real 17-22, cote_away=63 → EXACT, 189 pts."""
        match = make_match(home_score=17, away_score=22, cote_away=63)
        pred = make_pred(17, 22)
        result = calculate_points(pred, match)
        self.assertEqual(result, (189, 'EXACT'))

    def test_good_gap(self):
        """Gap diff = 2 ≤ 3 → GAP, cote_away × 2 = 126."""
        # real gap = 17-22 = -5, pred gap = 15-22 = -7, diff = |-7 - (-5)| = 2
        match = make_match(home_score=17, away_score=22, cote_away=63)
        pred = make_pred(15, 22)
        result = calculate_points(pred, match)
        self.assertEqual(result, (126, 'GAP'))

    def test_good_gap_boundary(self):
        """Gap diff exactly = 3 (boundary) → GAP."""
        # real gap = -5, pred gap = -8 → diff = 3
        match = make_match(home_score=17, away_score=22, cote_away=63)
        pred = make_pred(14, 22)
        result = calculate_points(pred, match)
        self.assertEqual(result, (126, 'GAP'))

    def test_good_gap_over(self):
        """Gap diff exactly = 4 (> 3) → WIN, cote_away × 1 = 63."""
        # real gap = -5, pred gap = -9 → diff = 4
        match = make_match(home_score=17, away_score=22, cote_away=63)
        pred = make_pred(13, 22)
        result = calculate_points(pred, match)
        self.assertEqual(result, (63, 'WIN'))

    def test_win_only(self):
        """Correct winner, gap diff way over threshold → WIN."""
        match = make_match(home_score=17, away_score=22, cote_away=63)
        pred = make_pred(5, 30)
        result = calculate_points(pred, match)
        self.assertEqual(result, (63, 'WIN'))

    def test_miss(self):
        """Wrong winner prediction → MISS, 0 pts."""
        # real: away wins (17-22), pred: home wins (25-10)
        match = make_match(home_score=17, away_score=22, cote_away=63)
        pred = make_pred(25, 10)
        result = calculate_points(pred, match)
        self.assertEqual(result, (0, 'MISS'))

    def test_draw_exact(self):
        """Real draw 15-15, pred 15-15 → EXACT, cote_draw × 3 = 90."""
        match = make_match(home_score=15, away_score=15, cote_draw=30)
        pred = make_pred(15, 15)
        result = calculate_points(pred, match)
        self.assertEqual(result, (90, 'EXACT'))

    def test_draw_gap(self):
        """Real draw 15-15, pred 10-10 (pred_gap=0, not exact) → GAP, cote_draw × 2 = 60."""
        match = make_match(home_score=15, away_score=15, cote_draw=30)
        pred = make_pred(10, 10)
        result = calculate_points(pred, match)
        self.assertEqual(result, (60, 'GAP'))

    def test_draw_miss(self):
        """Real draw 15-15, pred winner 20-10 (pred_gap != 0) → MISS, 0 pts."""
        match = make_match(home_score=15, away_score=15, cote_draw=30)
        pred = make_pred(20, 10)
        result = calculate_points(pred, match)
        self.assertEqual(result, (0, 'MISS'))

    def test_cancelled(self):
        """Cancelled match → (0, 'CANCELLED') regardless of prediction."""
        match = make_match(status='CANCELLED')
        pred = make_pred(15, 10)
        result = calculate_points(pred, match)
        self.assertEqual(result, (0, 'CANCELLED'))

    def test_no_odds(self):
        """has_odds=False → None (service refuses to score)."""
        match = make_match(has_odds=False)
        pred = make_pred(15, 10)
        result = calculate_points(pred, match)
        self.assertIsNone(result)
