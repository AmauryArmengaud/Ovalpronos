"""
Prediction scoring service.

calculate_points(prediction, match) -> (int, str) | None

Returns a tuple (points_earned, result_type) or None if preconditions are not met.

Odds convention: cote_home/draw/away are stored as integers = real odds × 10
(e.g. Unibet 6.30 → stored as 63). The stored integer is used as-is in the
scoring formula — no division by 10 is applied.
"""


def calculate_points(prediction, match):
    """
    Calculate points earned for a prediction given the final match result.

    Returns (points: int, result_type: str) or None if preconditions are not met.
    Preconditions: match.status in (FINISHED, CANCELLED) and match.has_odds.
    """

    def sign(n):
        if n > 0:
            return 1
        elif n < 0:
            return -1
        return 0

    # Precondition: odds must be available
    if not match.has_odds:
        return None

    # Step 1: cancelled match
    if match.status == 'CANCELLED':
        return (0, 'CANCELLED')

    # Step 2: must be finished
    if match.status != 'FINISHED':
        return None

    # Step 3: compute gaps
    real_gap = match.home_score - match.away_score
    pred_gap = prediction.predicted_home_score - prediction.predicted_away_score

    # Step 4: select the winning cote
    if real_gap > 0:
        winning_cote = match.cote_home
    elif real_gap < 0:
        winning_cote = match.cote_away
    else:
        winning_cote = match.cote_draw

    # Determine multipliers based on scoring system
    competition = match.competition
    use_fixed = (competition.scoring_system == 'FIXED')

    def pts(multiplier):
        """Return points: stored_cote × multiplier (COTES mode). stored_cote = real odds × 10, used as-is."""
        if use_fixed:
            # FIXED: 3→5, 2→3, 1→1, 0→0
            fixed_map = {3: 5, 2: 3, 1: 1, 0: 0}
            return fixed_map.get(multiplier, 0)
        return winning_cote * multiplier

    # Step 5: draw special case (real_gap == 0)
    if real_gap == 0:
        if pred_gap == 0:
            # Check for exact score
            if (prediction.predicted_home_score == match.home_score and
                    prediction.predicted_away_score == match.away_score):
                return (pts(3), 'EXACT')
            else:
                return (pts(2), 'GAP')
        else:
            # Predicted a winner, but it was a draw
            return (0, 'MISS')

    # Steps 6–9 only when real_gap != 0

    # Step 6: wrong winner
    if sign(pred_gap) != sign(real_gap):
        return (0, 'MISS')

    # Step 7: exact score
    if (prediction.predicted_home_score == match.home_score and
            prediction.predicted_away_score == match.away_score):
        return (pts(3), 'EXACT')

    # Step 8: gap within threshold
    good_gap_pts = competition.good_gap_pts
    if abs(pred_gap - real_gap) <= good_gap_pts:
        return (pts(2), 'GAP')

    # Step 9: correct winner only
    return (pts(1), 'WIN')


def get_example_points(scoring_system='COTES', good_gap_pts=3):
    """
    Points for the canonical Clermont–Perpignan example (real 17-22, cote_away=63).
    Used by both the home page and the rules page — single source of truth.
    """
    import types

    comp = types.SimpleNamespace(scoring_system=scoring_system, good_gap_pts=good_gap_pts)
    match = types.SimpleNamespace(
        status='FINISHED', has_odds=True,
        home_score=17, away_score=22,
        cote_home=18, cote_draw=30, cote_away=63,
        competition=comp,
    )

    def pred(home, away):
        return types.SimpleNamespace(predicted_home_score=home, predicted_away_score=away)

    return {
        'exact_pts': calculate_points(pred(17, 22), match)[0],
        'gap_pts':   calculate_points(pred(15, 22), match)[0],
        'win_pts':   calculate_points(pred(14, 25), match)[0],
        'miss_pts':  calculate_points(pred(20, 10), match)[0],
    }
