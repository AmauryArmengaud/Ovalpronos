"""
Integration tests for _calculate_points_for_match() and refresh_user_scores_for_match().

These use Django TestCase (real DB, rolled back per test) to catch bugs that
mock-based unit tests cannot — e.g. the production bug where already-scored
predictions were skipped when a match score was corrected after a premature
FINISHED status.

Run:
    python manage.py test apps.matches.tests
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.matches.models import Competition, Match, Team
from apps.matches.services import _calculate_points_for_match, refresh_user_scores_for_match
from apps.predictions.models import Prediction
from apps.rankings.models import UserScore

User = get_user_model()

_comp_counter = 0
_team_counter = 0
_match_counter = 0
_user_counter = 0


def make_competition(**kwargs):
    global _comp_counter
    _comp_counter += 1
    defaults = dict(
        external_id=_comp_counter,
        name='Test Comp',
        code='TEST',
        country='France',
        season='2025',
        scoring_system='COTES',
        good_gap_pts=3,
    )
    defaults.update(kwargs)
    return Competition.objects.create(**defaults)


def make_team():
    global _team_counter
    _team_counter += 1
    return Team.objects.create(
        external_id=_team_counter,
        name=f'Team {_team_counter}',
        slug=f'team-{_team_counter}',
    )


def make_match(competition, home_team, away_team, **kwargs):
    global _match_counter
    _match_counter += 1
    defaults = dict(
        external_id=_match_counter,
        competition=competition,
        home_team=home_team,
        away_team=away_team,
        round='1',
        datetime=timezone.now(),
        status='FINISHED',
        home_score=17,
        away_score=22,
        cote_home=18,
        cote_draw=30,
        cote_away=63,
    )
    defaults.update(kwargs)
    return Match.objects.create(**defaults)


def make_user():
    global _user_counter
    _user_counter += 1
    username = f'user{_user_counter}'
    return User.objects.create_user(username=username, password='x', email=f'{username}@test.com')


def make_prediction(user, match, home=10, away=20, **kwargs):
    return Prediction.objects.create(
        user=user,
        match=match,
        predicted_home_score=home,
        predicted_away_score=away,
        **kwargs,
    )


class CalculatePointsForMatchTests(TestCase):

    def setUp(self):
        self.comp = make_competition()
        self.home = make_team()
        self.away = make_team()

    def _make_match(self, **kwargs):
        return make_match(self.comp, self.home, self.away, **kwargs)

    def test_finished_match_scores_all_predictions(self):
        """Baseline: FINISHED match scores every prediction with correct points."""
        match = self._make_match(home_score=17, away_score=22, cote_away=63)
        user1 = make_user()
        user2 = make_user()
        make_prediction(user1, match, home=17, away=22)  # exact away
        make_prediction(user2, match, home=5, away=30)   # away win, big gap

        _calculate_points_for_match(match)

        p1 = Prediction.objects.get(user=user1, match=match)
        self.assertEqual(p1.points_earned, 189)  # 63 × 3
        self.assertEqual(p1.result_type, 'EXACT')

        p2 = Prediction.objects.get(user=user2, match=match)
        self.assertEqual(p2.points_earned, 63)   # 63 × 1
        self.assertEqual(p2.result_type, 'WIN')

    def test_score_correction_recalculates_already_scored_predictions(self):
        """
        Regression test for the production bug (fixed in b24d0fa).

        Scenario:
        1. Live sync marks match FINISHED with wrong provisional score (home wins).
        2. _calculate_points_for_match() scores the prediction as EXACT (54 pts).
        3. Next sync corrects the score (away actually wins).
        4. _calculate_points_for_match() is called again.

        Pre-fix code filtered points_earned__isnull=True, so step 4 skipped the
        already-scored prediction and the wrong points were permanently locked in.
        Post-fix code recalculates all predictions regardless, so step 4 corrects them.
        """
        # Step 1: wrong provisional score — home wins
        match = self._make_match(home_score=20, away_score=10, cote_home=18, cote_away=63)
        user = make_user()
        make_prediction(user, match, home=20, away=10)  # predicts home win

        # Step 2: score with wrong provisional result
        _calculate_points_for_match(match)
        pred = Prediction.objects.get(user=user, match=match)
        self.assertEqual(pred.points_earned, 54)   # 18 × 3 — EXACT on wrong score
        self.assertEqual(pred.result_type, 'EXACT')

        # Step 3: correct the score — away actually won
        match.home_score = 17
        match.away_score = 22
        match.save(update_fields=['home_score', 'away_score'])

        # Step 4: re-run scoring with corrected score
        _calculate_points_for_match(match)
        pred.refresh_from_db()
        self.assertEqual(pred.points_earned, 0)    # predicted home, away won → MISS
        self.assertEqual(pred.result_type, 'MISS')

    def test_no_unnecessary_writes_when_score_unchanged(self):
        """Calling the service twice with the same score must not touch already-correct rows."""
        match = self._make_match()
        user = make_user()
        make_prediction(user, match, home=17, away=22)

        _calculate_points_for_match(match)
        pred_after_first = Prediction.objects.get(user=user, match=match)
        updated_at_after_first = pred_after_first.updated_at

        _calculate_points_for_match(match)
        pred_after_second = Prediction.objects.get(user=user, match=match)

        self.assertEqual(pred_after_second.updated_at, updated_at_after_first)

    def test_cancelled_match_sets_all_predictions_to_zero(self):
        """CANCELLED match → every prediction gets (0, 'CANCELLED')."""
        match = self._make_match(status='CANCELLED', home_score=None, away_score=None)
        user1 = make_user()
        user2 = make_user()
        make_prediction(user1, match, home=20, away=10)
        make_prediction(user2, match, home=5, away=30)

        _calculate_points_for_match(match)

        for user in (user1, user2):
            pred = Prediction.objects.get(user=user, match=match)
            self.assertEqual(pred.points_earned, 0)
            self.assertEqual(pred.result_type, 'CANCELLED')

    def test_cancelled_overwrites_previously_scored_predictions(self):
        """Already-scored predictions are reset to (0, 'CANCELLED') if match is cancelled."""
        match = self._make_match()
        user = make_user()
        # Simulate a prediction already scored as WIN
        make_prediction(user, match, home=5, away=30, points_earned=63, result_type='WIN')

        match.status = 'CANCELLED'
        match.home_score = None
        match.away_score = None
        match.save(update_fields=['status', 'home_score', 'away_score'])

        _calculate_points_for_match(match)

        pred = Prediction.objects.get(user=user, match=match)
        self.assertEqual(pred.points_earned, 0)
        self.assertEqual(pred.result_type, 'CANCELLED')

    def test_no_odds_skips_scoring(self):
        """Match with no odds → predictions are left untouched."""
        match = self._make_match(cote_home=None, cote_draw=None, cote_away=None)
        user = make_user()
        make_prediction(user, match)

        _calculate_points_for_match(match)

        pred = Prediction.objects.get(user=user, match=match)
        self.assertIsNone(pred.points_earned)

    def test_no_predictions_runs_cleanly(self):
        """FINISHED match with no predictions must not raise."""
        match = self._make_match()
        _calculate_points_for_match(match)  # should not raise


class RefreshUserScoresForMatchTests(TestCase):

    def setUp(self):
        self.comp = make_competition()
        self.home = make_team()
        self.away = make_team()

    def _make_match(self, comp=None, **kwargs):
        return make_match(comp or self.comp, self.home, self.away, **kwargs)

    def test_creates_global_user_score_row(self):
        """After scoring, a global UserScore (competition=None) is created with correct totals."""
        match = self._make_match(home_score=17, away_score=22, cote_away=63)
        user = make_user()
        # EXACT: 63×3=189 and WIN: 63×1=63
        make_prediction(user, match, home=17, away=22, points_earned=189, result_type='EXACT')
        make_prediction(user, self._make_match(), home=5, away=30, points_earned=63, result_type='WIN')

        refresh_user_scores_for_match(match)

        score = UserScore.objects.get(user=user, competition=None, league=None)
        self.assertEqual(score.points, 252)
        self.assertEqual(score.prediction_count, 2)
        self.assertEqual(score.exact_count, 1)
        self.assertEqual(score.win_count, 1)

    def test_creates_per_competition_user_score_row(self):
        """Per-competition UserScore aggregates only predictions in that competition."""
        comp_b = make_competition()
        match_a = self._make_match()
        match_b = make_match(comp_b, self.home, self.away)
        user = make_user()
        make_prediction(user, match_a, points_earned=63, result_type='WIN')
        make_prediction(user, match_b, points_earned=100, result_type='WIN')

        refresh_user_scores_for_match(match_a)

        score = UserScore.objects.get(user=user, competition=self.comp, league=None)
        self.assertEqual(score.points, 63)  # only match_a's prediction

    def test_updates_existing_user_score_row(self):
        """Re-running the function updates the stale row instead of creating a duplicate."""
        match = self._make_match()
        user = make_user()
        make_prediction(user, match, points_earned=63, result_type='WIN')

        refresh_user_scores_for_match(match)
        refresh_user_scores_for_match(match)

        self.assertEqual(UserScore.objects.filter(user=user, competition=None, league=None).count(), 1)

    def test_no_scored_predictions_skips_user_score_update(self):
        """No scored predictions → no UserScore row created."""
        match = self._make_match()
        user = make_user()
        make_prediction(user, match)  # points_earned=None

        refresh_user_scores_for_match(match)

        self.assertEqual(UserScore.objects.filter(user=user).count(), 0)

    def test_score_correction_updates_user_score(self):
        """Full chain: wrong score → UserScore=54, corrected score → UserScore=0."""
        match = self._make_match(home_score=20, away_score=10, cote_home=18, cote_away=63)
        user = make_user()
        make_prediction(user, match, home=20, away=10)

        # First pass with wrong score
        _calculate_points_for_match(match)
        score = UserScore.objects.get(user=user, competition=None, league=None)
        self.assertEqual(score.points, 54)  # 18×3

        # Correct the score
        match.home_score = 17
        match.away_score = 22
        match.save(update_fields=['home_score', 'away_score'])

        _calculate_points_for_match(match)
        score.refresh_from_db()
        self.assertEqual(score.points, 0)  # predicted home, away won → MISS