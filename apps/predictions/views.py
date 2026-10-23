from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from django.db.models.functions import TruncDate

from apps.matches.models import Competition, Match
from .models import Prediction


def _prediction_progress(user):
    """Return (predicted_with_odds, total_with_odds) for the upcoming tab scope.

    Single source of truth used by SubmitPredictionView (OOB progress update).
    Counts SCHEDULED/POSTPONED matches with full odds in the user's active leagues.
    """
    competition_ids = list(
        Competition.objects.filter(
            is_active=True,
            leagues__members=user,
        ).distinct().values_list('pk', flat=True)
    )
    upcoming_with_odds = Match.objects.filter(
        competition_id__in=competition_ids,
        status__in=['SCHEDULED', 'POSTPONED'],
        datetime__gt=timezone.now(),  # exclude matches past kickoff (locked)
        cote_home__isnull=False,
        cote_draw__isnull=False,
        cote_away__isnull=False,
    )
    total = upcoming_with_odds.count()
    if total == 0:
        return 0, 0
    predicted = Prediction.objects.filter(user=user, match__in=upcoming_with_odds).count()
    return predicted, total


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

        # Race condition: match locked or odds removed after the form was loaded.
        # Return the full card so HTMX replaces the stale open card with the locked state.
        if match.is_locked or not match.has_odds:
            prediction = Prediction.objects.filter(user=request.user, match=match).first()
            html = render_to_string(
                'partials/match_card.html',
                {'match': match, 'prediction': prediction},
                request=request,
            )
            response = HttpResponse(html)
            response['HX-Retarget'] = f'#match-card-{match.pk}'
            response['HX-Reswap'] = 'outerHTML'
            return response

        home_raw = request.POST.get('score_h', '').strip()
        away_raw = request.POST.get('score_a', '').strip()

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

        prediction, created = Prediction.objects.update_or_create(
            user=request.user,
            match=match,
            defaults={
                'predicted_home_score': home,
                'predicted_away_score': away,
            }
        )

        from ovalpronos.analytics import capture
        capture(request, 'prediction_saved', {
            'match_id': match.pk,
            'competition': match.competition.name,
            'is_update': not created,
        })

        card_html = render_to_string(
            'partials/match_card.html',
            {'match': match, 'prediction': prediction, 'saved': True},
            request=request,
        )
        predicted, total = _prediction_progress(request.user)
        if total:
            progress_html = render_to_string(
                'partials/predictions_progress.html',
                {'predicted_with_odds': predicted, 'total_with_odds': total, 'oob': True},
                request=request,
            )
        else:
            progress_html = ''
        return HttpResponse(card_html + progress_html, content_type='text/html')
