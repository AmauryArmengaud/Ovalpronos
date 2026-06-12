from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from apps.rankings.models import UserScore

User = get_user_model()


def _build_leaderboard(score_qs, all_users_qs, current_user_pk):
    """Build a ranked list merging UserScore data with all relevant users (0 pts if no score yet)."""
    scores_by_user = {
        s.user_id: s
        for s in score_qs.select_related('user')
    }
    entries = []
    for user in all_users_qs:
        score = scores_by_user.get(user.pk)
        entries.append({
            'user': user,
            'total_points': score.points if score else 0,
            'count_predictions': score.prediction_count if score else 0,
            'count_exact': score.exact_count if score else 0,
            'count_gap': score.gap_count if score else 0,
            'count_win': score.win_count if score else 0,
        })
    entries.sort(key=lambda e: (-e['total_points'], -e['count_exact'], -e['count_gap']))
    ranked = []
    for rank, entry in enumerate(entries, start=1):
        entry['rank'] = rank
        entry['is_current_user'] = entry['user'].pk == current_user_pk
        ranked.append(entry)
    return ranked


class RankingsView(LoginRequiredMixin, TemplateView):
    template_name = 'rankings/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        global_qs = UserScore.objects.filter(competition=None, league=None)
        all_users = User.objects.filter(is_active=True)
        ctx['leaderboard'] = _build_leaderboard(global_qs, all_users, self.request.user.pk)
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
                league_members = User.objects.filter(pk__in=member_ids)
                league_leaderboard = _build_leaderboard(league_qs, league_members, self.request.user.pk)
            except League.DoesNotExist:
                pass

        ctx['selected_league'] = selected_league
        ctx['league_leaderboard'] = league_leaderboard
        ctx['active_tab'] = 'league' if selected_league else 'global'
        return ctx
