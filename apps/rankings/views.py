from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.views.generic import TemplateView

from apps.matches.models import Competition
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

        competitions = list(Competition.objects.filter(is_active=True))
        ctx['competitions'] = competitions
        ctx['user_leagues'] = self.request.user.leagues.filter(competitions__is_active=True).distinct()

        # League tab
        league_pk = self.request.GET.get('league')
        selected_league = None
        league_leaderboard = []
        if league_pk:
            from apps.leagues.models import League
            try:
                selected_league = self.request.user.leagues.get(pk=league_pk)
                member_ids = selected_league.members.values_list('pk', flat=True)
                league_comp_ids = selected_league.competitions.values_list('pk', flat=True)
                agg = (
                    UserScore.objects
                    .filter(competition__in=league_comp_ids, league=None, user_id__in=member_ids)
                    .values('user_id')
                    .annotate(
                        total=Sum('points'),
                        total_count=Sum('prediction_count'),
                        exact=Sum('exact_count'),
                        gap=Sum('gap_count'),
                        win=Sum('win_count'),
                    )
                )
                agg_by_user = {row['user_id']: row for row in agg}
                league_members = User.objects.filter(pk__in=member_ids)
                for user in league_members:
                    row = agg_by_user.get(user.pk)
                    league_leaderboard.append({
                        'user': user,
                        'total_points': row['total'] if row else 0,
                        'count_predictions': row['total_count'] if row else 0,
                        'count_exact': row['exact'] if row else 0,
                        'count_gap': row['gap'] if row else 0,
                        'count_win': row['win'] if row else 0,
                    })
                league_leaderboard.sort(key=lambda e: (-e['total_points'], -e['count_exact'], -e['count_gap']))
                for rank, entry in enumerate(league_leaderboard, start=1):
                    entry['rank'] = rank
                    entry['is_current_user'] = entry['user'].pk == self.request.user.pk
            except League.DoesNotExist:
                pass

        # Global tab: optional competition filter via ?comp=<pk>
        selected_comp = None
        if not selected_league:
            comp_pk = self.request.GET.get('comp')
            if comp_pk:
                selected_comp = next((c for c in competitions if str(c.pk) == comp_pk), None)
            if selected_comp:
                eligible_users = User.objects.filter(
                    is_active=True, leagues__competitions=selected_comp
                ).distinct()
                score_qs = UserScore.objects.filter(competition=selected_comp, league=None)
            else:
                eligible_users = User.objects.filter(
                    is_active=True, leagues__competitions__is_active=True
                ).distinct()
                score_qs = UserScore.objects.filter(competition=None, league=None)
            ctx['active_leaderboard'] = _build_leaderboard(score_qs, eligible_users, self.request.user.pk)

        ctx['selected_league'] = selected_league
        ctx['league_leaderboard'] = league_leaderboard
        ctx['selected_comp'] = selected_comp
        ctx['active_tab'] = 'league' if selected_league else 'global'
        return ctx
