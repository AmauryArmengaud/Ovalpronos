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


@csrf_exempt
@require_POST
def sync_scores_api(request):
    auth_header = request.headers.get('Authorization', '').strip()
    expected = f'Bearer {settings.SYNC_SECRET_TOKEN}'
    if not settings.SYNC_SECRET_TOKEN or not hmac.compare_digest(auth_header, expected):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    from .services import sync_all_competitions
    created, updated = sync_all_competitions()
    return JsonResponse({'created': created, 'updated': updated})
