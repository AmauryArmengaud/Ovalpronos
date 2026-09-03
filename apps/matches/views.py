import hmac

from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
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
@require_GET
def has_live_matches_api(request):
    if not _check_bearer(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    from .models import Match
    from django.db.models import Q
    import datetime as dt

    now = timezone.now()
    window_start = now - dt.timedelta(hours=2)
    terminal = [Match.STATUS_FINISHED, Match.STATUS_CANCELLED, Match.STATUS_POSTPONED]

    live = Match.objects.filter(
        Q(status=Match.STATUS_IN_PLAY)
        | (Q(datetime__lte=now) & Q(datetime__gte=window_start) & ~Q(status__in=terminal))
    ).exists()

    return JsonResponse({'live': live})


@csrf_exempt
@require_POST
def notify_deadline_reminders_api(request):
    if not _check_bearer(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    from apps.predictions.tasks import send_deadline_reminders
    sent = send_deadline_reminders()
    return JsonResponse({'sent': sent})


@csrf_exempt
@require_GET
def upcoming_matches_api(request):
    if not _check_bearer(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    import datetime as dt
    from .models import Match

    now = timezone.now()
    cutoff = now + dt.timedelta(days=14)

    matches = (
        Match.objects
        .filter(
            status__in=[Match.STATUS_SCHEDULED, Match.STATUS_POSTPONED],
            datetime__gt=now,
            datetime__lte=cutoff,
            is_hidden=False,
        )
        .select_related('home_team', 'away_team', 'competition')
        .order_by('datetime')
    )

    data = [
        {
            'match_id': m.pk,
            'home_team': m.home_team.name,
            'home_team_short': m.home_team.short_name,
            'away_team': m.away_team.name,
            'away_team_short': m.away_team.short_name,
            'competition': m.competition.name,
            'datetime': m.datetime.isoformat(),
        }
        for m in matches
    ]
    return JsonResponse(data, safe=False)


@csrf_exempt
@require_POST
def update_odds_api(request):
    if not _check_bearer(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    import json
    from .models import Match

    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    entries = body.get('odds', [])
    if not isinstance(entries, list):
        return JsonResponse({'error': 'odds must be a list'}, status=400)

    updated = []
    skipped = []
    now = timezone.now()

    for entry in entries:
        match_id = entry.get('match_id')
        cote_home = entry.get('cote_home')
        cote_draw = entry.get('cote_draw')
        cote_away = entry.get('cote_away')

        try:
            match = Match.objects.get(pk=match_id)
        except Match.DoesNotExist:
            skipped.append({'match_id': match_id, 'reason': 'not_found'})
            continue

        if match.datetime <= now:
            skipped.append({'match_id': match_id, 'reason': 'locked'})
            continue

        cotes = [cote_home, cote_draw, cote_away]
        if not all(isinstance(c, int) and 11 <= c <= 500 for c in cotes):
            skipped.append({'match_id': match_id, 'reason': 'invalid_odds'})
            continue

        Match.objects.filter(pk=match_id).update(
            cote_home=cote_home,
            cote_draw=cote_draw,
            cote_away=cote_away,
        )
        updated.append(match_id)

    return JsonResponse({'updated': updated, 'skipped': skipped})


@csrf_exempt
@require_POST
def notify_missing_odds_api(request):
    if not _check_bearer(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    import datetime as dt
    from django.contrib.auth import get_user_model
    from django.core.mail import EmailMultiAlternatives
    from .models import Match

    now = timezone.now()
    cutoff = now + dt.timedelta(days=14)

    missing = list(
        Match.objects
        .filter(
            status__in=[Match.STATUS_SCHEDULED, Match.STATUS_POSTPONED],
            datetime__gt=now,
            datetime__lte=cutoff,
            is_hidden=False,
            cote_home__isnull=True,
        )
        .select_related('home_team', 'away_team', 'competition')
        .order_by('datetime')
    )

    if not missing:
        return JsonResponse({'missing': 0, 'sent': 0})

    lines = [f"Oval'Pronos — {len(missing)} match(s) sans côtes dans les 14 prochains jours :\n"]
    for m in missing:
        local_dt = m.datetime.astimezone(timezone.get_current_timezone())
        lines.append(f"  - {m.home_team.name} vs {m.away_team.name} ({m.competition.name}, {local_dt.strftime('%d/%m %Hh%M')})")

    body = "\n".join(lines)
    admins = list(get_user_model().objects.filter(is_superuser=True, email__gt='').values_list('email', flat=True))

    sent = 0
    if admins:
        msg = EmailMultiAlternatives(
            subject=f"[Oval'Pronos] {len(missing)} match(s) sans côtes",
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=admins,
        )
        try:
            msg.send()
            sent = 1
        except Exception:
            pass

    return JsonResponse({'missing': len(missing), 'sent': sent})


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
