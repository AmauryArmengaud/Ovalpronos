from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.db.models import Sum, Count, Q
from apps.predictions.models import Prediction
from django.contrib.auth import get_user_model

User = get_user_model()


def _build_leaderboard(queryset, current_user_pk):
    """Annotate a user queryset with stats and return a ranked list."""
    users = (
        queryset
        .filter(predictions__points_earned__isnull=False)
        .annotate(
            total_points=Sum('predictions__points_earned'),
            count_predictions=Count('predictions'),
            count_exact=Count('predictions', filter=Q(predictions__result_type='EXACT')),
            count_gap=Count('predictions', filter=Q(predictions__result_type='GAP')),
            count_win=Count('predictions', filter=Q(predictions__result_type='WIN')),
        )
        .order_by('-total_points', '-count_exact', '-count_gap')
    )
    ranked = []
    for rank, user in enumerate(users, start=1):
        ranked.append({
            'rank': rank,
            'user': user,
            'total_points': user.total_points or 0,
            'count_predictions': user.count_predictions,
            'count_exact': user.count_exact,
            'count_gap': user.count_gap,
            'count_win': user.count_win,
            'is_current_user': user.pk == current_user_pk,
        })
    return ranked


class RankingsView(LoginRequiredMixin, TemplateView):
    template_name = 'rankings/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        ctx['leaderboard'] = _build_leaderboard(User.objects.all(), self.request.user.pk)
        ctx['user_leagues'] = self.request.user.leagues.all()

        # League tab: show selected league leaderboard
        league_pk = self.request.GET.get('league')
        selected_league = None
        league_leaderboard = []
        if league_pk:
            from apps.leagues.models import League
            try:
                selected_league = self.request.user.leagues.get(pk=league_pk)
                league_leaderboard = _build_leaderboard(
                    selected_league.members.all(), self.request.user.pk
                )
            except League.DoesNotExist:
                pass

        ctx['selected_league'] = selected_league
        ctx['league_leaderboard'] = league_leaderboard
        ctx['active_tab'] = 'league' if selected_league else 'global'
        return ctx
