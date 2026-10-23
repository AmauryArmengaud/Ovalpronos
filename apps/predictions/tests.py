"""
Scoring tests for calculate_points(), and view tests for the progress bar OOB update
and the HX-Retarget fallback for locked / no-odds races.
"""
from datetime import timedelta
from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.matches.models import Competition, Match, Team
from apps.predictions.models import Prediction
from apps.predictions.services import calculate_points, get_example_points

User = get_user_model()


# ── helpers for DB-backed tests ────────────────────────────────────────────────

def _make_user(username):
    return User.objects.create_user(username=username, password='pass', email=f'{username}@test.local')


def _make_comp(code):
    return Competition.objects.create(
        name=f'Comp {code}', code=code,
        external_id=-(hash(code) % 90000 + 10000),
        season='2025', scoring_system='FIXED', good_gap_pts=3, is_active=True,
    )


def _make_team(suffix):
    return Team.objects.create(
        external_id=-(hash(suffix) % 90000 + 50000),
        name=f'Team {suffix}', slug=f'team-{suffix}-prog', country='France',
    )


def _make_match(comp, home, away, external_id):
    return Match.objects.create(
        external_id=external_id, competition=comp,
        home_team=home, away_team=away,
        datetime=timezone.now() + timedelta(days=7),
        status='SCHEDULED',
        cote_home=18, cote_draw=30, cote_away=22,
    )


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


class ExamplePointsTest(SimpleTestCase):
    """get_example_points() values must match calculate_points() — if the formula
    changes these break, forcing an update of the rules and home pages."""

    def test_cotes_values(self):
        example = get_example_points()
        self.assertEqual(example['exact_pts'], 189)  # 63 × 3
        self.assertEqual(example['gap_pts'], 126)    # 63 × 2
        self.assertEqual(example['win_pts'], 63)     # 63 × 1
        self.assertEqual(example['miss_pts'], 0)

    def test_fixed_values(self):
        example = get_example_points(scoring_system='FIXED')
        self.assertEqual(example['exact_pts'], 5)
        self.assertEqual(example['gap_pts'], 3)
        self.assertEqual(example['win_pts'], 1)
        self.assertEqual(example['miss_pts'], 0)


class PredictionProgressOOBTest(TestCase):
    """SubmitPredictionView returns an hx-swap-oob progress bar; count is server-authoritative."""

    @classmethod
    def setUpTestData(cls):
        from apps.leagues.models import League
        cls.user = _make_user('oob_user')
        cls.comp = _make_comp('OOBTEST')
        cls.league = League.objects.create(name='OOB League', creator=cls.user)
        cls.league.competitions.add(cls.comp)
        cls.league.members.add(cls.user)
        cls.team_a = _make_team('oob-a')
        cls.team_b = _make_team('oob-b')
        cls.match1 = _make_match(cls.comp, cls.team_a, cls.team_b, external_id=-88001)
        cls.match2 = _make_match(cls.comp, cls.team_b, cls.team_a, external_id=-88002)

    def setUp(self):
        self.client.force_login(self.user)

    def _submit(self, match, h, a):
        return self.client.post(
            reverse('predictions:submit', kwargs={'match_pk': match.pk}),
            {'score_h': str(h), 'score_a': str(a)},
        )

    def test_response_includes_oob_progress_bar(self):
        """A successful save returns the progress bar fragment with hx-swap-oob."""
        response = self._submit(self.match1, 14, 10)
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('id="predictions-progress"', content)
        self.assertIn('hx-swap-oob="true"', content)

    def test_count_is_1_of_2_after_first_save(self):
        """Progress reflects exactly one saved prediction out of two matches."""
        response = self._submit(self.match1, 14, 10)
        content = response.content.decode()
        self.assertIn('aria-valuenow="1"', content)
        self.assertIn('aria-valuemax="2"', content)

    def test_100_percent_on_last_save(self):
        """Saving the final prediction yields aria-valuenow == total and --complete class."""
        Prediction.objects.create(
            user=self.user, match=self.match1,
            predicted_home_score=14, predicted_away_score=10,
        )
        response = self._submit(self.match2, 20, 15)
        content = response.content.decode()
        self.assertIn('aria-valuenow="2"', content)
        self.assertIn('aria-valuemax="2"', content)
        self.assertIn('prediction-progress-bar--complete', content)

    def test_page_context_shows_correct_initial_count(self):
        """GET /predictions/ exposes the right predicted_with_odds in context."""
        Prediction.objects.create(
            user=self.user, match=self.match1,
            predicted_home_score=14, predicted_away_score=10,
        )
        response = self.client.get(reverse('predictions:index'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['predicted_with_odds'], 1)
        self.assertEqual(response.context['total_with_odds'], 2)

    def test_locked_match_excluded_from_progress(self):
        """A locked match (past kickoff, SCHEDULED) is excluded from the progress bar denominator."""
        from apps.leagues.models import League
        locked_user = _make_user('oob_locked')
        locked_league = League.objects.create(name='Locked League', creator=locked_user)
        locked_league.competitions.add(self.comp)
        locked_league.members.add(locked_user)
        self.client.force_login(locked_user)

        # Match in the past — is_locked returns True; must not appear in denominator
        locked_match = Match.objects.create(
            external_id=-88003, competition=self.comp,
            home_team=self.team_a, away_team=self.team_b,
            datetime=timezone.now() - timedelta(hours=1),
            status='SCHEDULED',
            cote_home=18, cote_draw=30, cote_away=22,
        )
        Prediction.objects.create(
            user=locked_user, match=locked_match,
            predicted_home_score=10, predicted_away_score=5,
        )
        # Also predict the two future matches
        Prediction.objects.create(
            user=locked_user, match=self.match1,
            predicted_home_score=14, predicted_away_score=10,
        )
        # Save the last prediction via view
        response = self._submit(self.match2, 20, 15)
        content = response.content.decode()
        # total = 2 (only future matches), locked match excluded
        self.assertIn('aria-valuenow="2"', content)
        self.assertIn('aria-valuemax="2"', content)
        self.assertIn('prediction-progress-bar--complete', content)


class SubmitPredictionRetargetTest(TestCase):
    """Zone C swap: locked/no-odds races return HX-Retarget so the full card is replaced."""

    @classmethod
    def setUpTestData(cls):
        from apps.leagues.models import League
        cls.user = _make_user('retarget_user')
        cls.comp = _make_comp('RTGTEST')
        cls.league = League.objects.create(name='RTG League', creator=cls.user)
        cls.league.competitions.add(cls.comp)
        cls.league.members.add(cls.user)
        cls.team_a = _make_team('rtg-a')
        cls.team_b = _make_team('rtg-b')

    def setUp(self):
        self.client.force_login(self.user)

    def _submit(self, pk):
        return self.client.post(
            reverse('predictions:submit', kwargs={'match_pk': pk}),
            {'score_h': '10', 'score_a': '5'},
        )

    def test_locked_match_returns_retarget_headers(self):
        """POST on a locked match returns 200 with HX-Retarget pointing at the card."""
        locked = Match.objects.create(
            external_id=-77001, competition=self.comp,
            home_team=self.team_a, away_team=self.team_b,
            datetime=timezone.now() - timedelta(hours=1),
            status='SCHEDULED',
            cote_home=18, cote_draw=30, cote_away=22,
        )
        resp = self._submit(locked.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['HX-Retarget'], f'#match-card-{locked.pk}')
        self.assertEqual(resp['HX-Reswap'], 'outerHTML')
        self.assertIn(f'id="match-card-{locked.pk}"', resp.content.decode())

    def test_no_odds_match_returns_retarget_headers(self):
        """POST on a no-odds match returns 200 with HX-Retarget pointing at the card."""
        no_odds = Match.objects.create(
            external_id=-77002, competition=self.comp,
            home_team=self.team_a, away_team=self.team_b,
            datetime=timezone.now() + timedelta(days=3),
            status='SCHEDULED',
        )
        resp = self._submit(no_odds.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['HX-Retarget'], f'#match-card-{no_odds.pk}')
        self.assertEqual(resp['HX-Reswap'], 'outerHTML')
        self.assertIn(f'id="match-card-{no_odds.pk}"', resp.content.decode())
