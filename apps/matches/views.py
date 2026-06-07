import hmac

from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.conf import settings


class HomeView(TemplateView):
    template_name = 'matches/home.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('predictions:index')
        return super().dispatch(request, *args, **kwargs)


class RulesView(TemplateView):
    template_name = 'matches/rules.html'


def _check_bearer(request):
    auth_header = request.headers.get('Authorization', '').strip()
    expected = f'Bearer {settings.SYNC_SECRET_TOKEN}'
    return bool(settings.SYNC_SECRET_TOKEN and hmac.compare_digest(auth_header, expected))


@csrf_exempt
@require_POST
def sync_scores_api(request):
    if not _check_bearer(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    from .services import sync_all_competitions
    created, updated = sync_all_competitions()
    return JsonResponse({'created': created, 'updated': updated})


@csrf_exempt
@require_POST
def notify_deadline_reminders_api(request):
    if not _check_bearer(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    from apps.predictions.tasks import send_deadline_reminders
    sent = send_deadline_reminders()
    return JsonResponse({'sent': sent})


@csrf_exempt
@require_POST
def notify_results_summary_api(request):
    if not _check_bearer(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    import json
    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        body = {}

    competition_id = body.get('competition_id') or None
    round_label = body.get('round') or None
    if competition_id:
        try:
            competition_id = int(competition_id)
        except (ValueError, TypeError):
            competition_id = None

    from apps.predictions.tasks import send_results_summary
    sent = send_results_summary(competition_id=competition_id, round_label=round_label)
    return JsonResponse({'sent': sent})
