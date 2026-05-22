from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.db.models import Sum, Count, Q
from apps.predictions.models import Prediction
from django.contrib.auth import get_user_model

User = get_user_model()


class RankingsView(LoginRequiredMixin, TemplateView):
    template_name = 'rankings/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Aggregate points and result_type counts per user
        leaderboard = (
            User.objects.filter(predictions__points_earned__isnull=False)
            .annotate(
                total_points=Sum('predictions__points_earned'),
                count_predictions=Count('predictions'),
                count_exact=Count('predictions', filter=Q(predictions__result_type='EXACT')),
                count_gap=Count('predictions', filter=Q(predictions__result_type='GAP')),
                count_win=Count('predictions', filter=Q(predictions__result_type='WIN')),
            )
            .order_by('-total_points', '-count_exact', '-count_gap')
        )

        # Add rank manually (no window function needed for V1)
        ranked = []
        for rank, user in enumerate(leaderboard, start=1):
            ranked.append({
                'rank': rank,
                'user': user,
                'total_points': user.total_points or 0,
                'count_predictions': user.count_predictions,
                'count_exact': user.count_exact,
                'count_gap': user.count_gap,
                'count_win': user.count_win,
                'is_current_user': user.pk == self.request.user.pk,
            })

        ctx['leaderboard'] = ranked
        return ctx
