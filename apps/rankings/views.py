from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from apps.rankings.models import UserScore


def _build_leaderboard(score_qs, current_user_pk):
    """Build a ranked list from a UserScore queryset."""
    scores = list(
        score_qs.select_related('user')
        .order_by('-points', '-exact_count', '-gap_count')
    )
    ranked = []
    for rank, score in enumerate(scores, start=1):
        ranked.append({
            'rank': rank,
            'user': score.user,
            'total_points': score.points,
            'count_predictions': score.prediction_count,
            'count_exact': score.exact_count,
            'count_gap': score.gap_count,
            'count_win': score.win_count,
            'is_current_user': score.user_id == current_user_pk,
        })
    return ranked


class RankingsView(LoginRequiredMixin, TemplateView):
    template_name = 'rankings/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        global_qs = UserScore.objects.filter(competition=None, league=None)
        ctx['leaderboard'] = _build_leaderboard(global_qs, self.request.user.pk)
        ctx['user_leagues'] = self.request.user.leagues.all()

        league_pk = self.request.GET.get('league')
        selected_league = None
        league_leaderboard = []
        if league_pk:
            from apps.leagues.models import League
            try:
                selected_league = self.request.user.leagues.get(pk=league_pk)
                member_ids = selected_league.members.values_list('pk', flat=True)
                league_qs = UserScore.objects.filter(
                    competition=None, league=None, user_id__in=member_ids
                )
                league_leaderboard = _build_leaderboard(league_qs, self.request.user.pk)
            except League.DoesNotExist:
                pass

        ctx['selected_league'] = selected_league
        ctx['league_leaderboard'] = league_leaderboard
        ctx['active_tab'] = 'league' if selected_league else 'global'
        return ctx
