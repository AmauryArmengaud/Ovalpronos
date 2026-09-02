from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from django.db.models.functions import TruncDate

from apps.matches.models import Competition, Match
from .models import Prediction


class PredictionsView(LoginRequiredMixin, TemplateView):
    template_name = 'predictions/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tab = self.request.GET.get('tab', 'upcoming')

        user_competition_ids = list(
            Competition.objects.filter(
                is_active=True,
                leagues__members=self.request.user,
            ).distinct().values_list('pk', flat=True)
        )
        ctx['no_leagues'] = not self.request.user.leagues.filter(competitions__is_active=True).exists()

        if tab == 'upcoming':
            matches = Match.objects.filter(
                competition_id__in=user_competition_ids,
                status__in=['SCHEDULED', 'POSTPONED'],
            ).select_related('competition', 'home_team', 'away_team').annotate(
                match_date=TruncDate('datetime')
            ).order_by('match_date', 'competition__name', 'datetime')
        elif tab == 'live':
            matches = Match.objects.filter(
                competition_id__in=user_competition_ids,
                status='IN_PLAY',
            ).select_related('competition', 'home_team', 'away_team').annotate(
                match_date=TruncDate('datetime')
            ).order_by('match_date', 'competition__name', 'datetime')
        else:  # past
            matches = Match.objects.filter(
                competition_id__in=user_competition_ids,
                status__in=['FINISHED', 'CANCELLED'],
            ).select_related('competition', 'home_team', 'away_team').annotate(
                match_date=TruncDate('datetime')
            ).order_by('-match_date', 'competition__name', 'datetime')

        match_ids = list(matches.values_list('pk', flat=True))
        user_predictions = {
            p.match_id: p
            for p in Prediction.objects.filter(user=self.request.user, match_id__in=match_ids)
        }

        items = [{'match': m, 'prediction': user_predictions.get(m.pk)} for m in matches]

        if tab == 'upcoming':
            items_with_odds = [i for i in items if i['match'].has_odds]
            items_without_odds = [i for i in items if not i['match'].has_odds]
            ctx['total_with_odds'] = len(items_with_odds)
            ctx['predicted_with_odds'] = sum(1 for i in items_with_odds if i['prediction'] is not None)
            ctx['items'] = items_with_odds
            ctx['items_without_odds'] = items_without_odds
        else:
            ctx['items'] = items
            ctx['items_without_odds'] = []
        ctx['active_tab'] = tab
        ctx['has_live_matches'] = Match.objects.filter(
            competition_id__in=user_competition_ids, status='IN_PLAY'
        ).exists()
        return ctx


class SubmitPredictionView(LoginRequiredMixin, View):
    def post(self, request, match_pk):
        match = get_object_or_404(
            Match.objects.select_related('competition', 'home_team', 'away_team'),
            pk=match_pk
        )

        if match.is_locked:
            return HttpResponseForbidden("Match is locked.")

        if not match.has_odds:
            return HttpResponseBadRequest("No odds available.")

        home_raw = request.POST.get('home', '').strip()
        away_raw = request.POST.get('away', '').strip()

        # Both fields must be present and valid integers
        if not home_raw or not away_raw:
            prediction = Prediction.objects.filter(user=request.user, match=match).first()
            return render(
                request, 'partials/match_card.html',
                {'match': match, 'prediction': prediction}
            )

        try:
            home = int(home_raw)
            away = int(away_raw)
        except ValueError:
            prediction = Prediction.objects.filter(user=request.user, match=match).first()
            return render(
                request, 'partials/match_card.html',
                {'match': match, 'prediction': prediction}
            )

        if home < 0 or away < 0:
            prediction = Prediction.objects.filter(user=request.user, match=match).first()
            return render(
                request, 'partials/match_card.html',
                {'match': match, 'prediction': prediction}
            )

        prediction, _ = Prediction.objects.update_or_create(
            user=request.user,
            match=match,
            defaults={
                'predicted_home_score': home,
                'predicted_away_score': away,
            }
        )

        return render(
            request, 'partials/match_card.html',
            {'match': match, 'prediction': prediction}
        )
