from collections import defaultdict

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.matches.models import Match
from .models import Prediction


class PredictionsView(LoginRequiredMixin, TemplateView):
    template_name = 'predictions/index.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tab = self.request.GET.get('tab', 'upcoming')

        if tab == 'upcoming':
            matches = Match.objects.filter(
                status__in=['SCHEDULED', 'POSTPONED']
            ).select_related('competition', 'home_team', 'away_team').order_by('datetime')
        elif tab == 'live':
            matches = Match.objects.filter(
                status='IN_PLAY'
            ).select_related('competition', 'home_team', 'away_team').order_by('datetime')
        else:  # past
            matches = Match.objects.filter(
                status__in=['FINISHED', 'CANCELLED']
            ).select_related('competition', 'home_team', 'away_team').order_by('-datetime')

        # Build predictions dict for current user
        match_ids = list(matches.values_list('pk', flat=True))
        user_predictions = {
            p.match_id: p
            for p in Prediction.objects.filter(
                user=self.request.user, match_id__in=match_ids
            )
        }

        # Group matches by competition then round
        grouped = defaultdict(lambda: defaultdict(list))
        for match in matches:
            grouped[match.competition][match.round].append({
                'match': match,
                'prediction': user_predictions.get(match.pk),
            })

        # Convert to sorted list of (competition, [round_dicts])
        competitions_data = []
        for competition, rounds in grouped.items():
            rounds_data = [
                {
                    'name': round_name,
                    'items': items,
                    'total': len(items),
                    'predicted': sum(1 for item in items if item['prediction'] is not None),
                }
                for round_name, items in rounds.items()
            ]
            competitions_data.append((competition, rounds_data))

        ctx['competitions_data'] = competitions_data
        ctx['active_tab'] = tab
        ctx['has_live_matches'] = Match.objects.filter(status='IN_PLAY').exists()
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
