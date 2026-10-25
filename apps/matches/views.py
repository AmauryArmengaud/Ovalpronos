import hmac

from django.shortcuts import redirect
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET
from django.http import Http404, JsonResponse
from django.conf import settings


class HomeView(TemplateView):
    template_name = 'matches/home.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('predictions:index')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from apps.matches.models import Competition
        from apps.predictions.services import get_example_points
        ctx = super().get_context_data(**kwargs)
        from apps.accounts.signup_source import utm_querystring
        ctx['competitions'] = Competition.objects.filter(is_active=True).order_by('name')
        ctx['example'] = get_example_points()
        ctx['utm_qs'] = utm_querystring(self.request.GET)
        return ctx


class CompetitionLandingView(TemplateView):
    """Visitor landing page for one competition, linked from campaigns and social posts"""
    template_name = 'matches/competition_landing.html'

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect('predictions:index')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        from apps.accounts.signup_source import utm_querystring
        from apps.matches.models import Competition, Match
        from apps.predictions.services import get_example_points
        ctx = super().get_context_data(**kwargs)
        competition = Competition.objects.filter(code__iexact=self.kwargs['code'], is_active=True).first()
        if competition is None:
            raise Http404
        ctx['competition'] = competition
        ctx['upcoming'] = (
            competition.matches
            .filter(status=Match.STATUS_SCHEDULED, datetime__gt=timezone.now(), is_hidden=False)
            .select_related('home_team', 'away_team')
            .order_by('datetime')[:6]
        )
        ctx['example'] = get_example_points()
        ctx['utm_qs'] = utm_querystring(self.request.GET)
        return ctx


class RulesView(TemplateView):
    template_name = 'matches/rules.html'

    def get_context_data(self, **kwargs):
        from apps.matches.models import Competition
        from apps.predictions.services import get_example_points
        ctx = super().get_context_data(**kwargs)
        ctx['example'] = get_example_points()
        comps = Competition.objects.filter(is_active=True).order_by('name')
        ctx['active_competitions'] = comps
        gap_values = list(comps.values_list('good_gap_pts', flat=True).distinct())
        ctx['good_gap_values'] = gap_values
        ctx['good_gap_uniform'] = len(gap_values) <= 1
        fixed_comps = list(comps.filter(scoring_system='FIXED'))
        ctx['fixed_competitions'] = fixed_comps
        if fixed_comps:
            ctx['fixed_example'] = get_example_points(scoring_system='FIXED')
        return ctx


def _check_bearer(request):
    auth_header = request.headers.get('Authorization', '').strip()
    expected = f'Bearer {settings.SYNC_SECRET_TOKEN}'
    return bool(settings.SYNC_SECRET_TOKEN and hmac.compare_digest(auth_header, expected))


def _upcoming_window(now):
    """Matches sent to Gemini for odds; update_odds_api only accepts these."""
    import datetime as dt
    from django.db.models import Q
    from .models import Match
    return Q(
        status__in=[Match.STATUS_SCHEDULED, Match.STATUS_POSTPONED],
        datetime__gt=now,
        datetime__lte=now + dt.timedelta(days=7),
        is_hidden=False,
    )


def _live_window(now):
    """Matches sent to Gemini for scores; update_scores_api only accepts these."""
    import datetime as dt
    from django.db.models import Q
    from .models import Match
    terminal = [Match.STATUS_FINISHED, Match.STATUS_CANCELLED, Match.STATUS_POSTPONED]
    kicked_off = Q(datetime__lte=now, datetime__gte=now - dt.timedelta(hours=3)) & ~Q(status__in=terminal)
    # kickoff + 5h ≈ 3h after the final whistle: Gemini may still correct a wrong final score
    correctable = Q(status=Match.STATUS_FINISHED, datetime__lte=now, datetime__gte=now - dt.timedelta(hours=5))
    return Q(status=Match.STATUS_IN_PLAY) | kicked_off | correctable


def _odds_are_consistent(cotes):
    # implied probabilities of a real 1N2 market sum to ~1.02-1.25 (bookmaker margin)
    implied = sum(10 / c for c in cotes)
    return 0.95 <= implied <= 1.40


@csrf_exempt
@require_POST
def sync_scores_api(request):
    if not _check_bearer(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    from .services import sync_all_competitions
    results = sync_all_competitions()
    return JsonResponse({'competitions': results})


@csrf_exempt
@require_GET
def has_live_matches_api(request):
    if not _check_bearer(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    from .models import Match

    live = Match.objects.filter(_live_window(timezone.now())).exists()

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

    from .models import Match

    matches = (
        Match.objects
        .filter(_upcoming_window(timezone.now()))
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

    entries = body.get('odds', []) if isinstance(body, dict) else None
    if not isinstance(entries, list):
        return JsonResponse({'error': 'odds must be a list'}, status=400)

    updated = []
    skipped = []
    # web content seen by Gemini is untrusted: only accept the matches it was asked about
    allowed_ids = set(Match.objects.filter(_upcoming_window(timezone.now())).values_list('pk', flat=True))

    for entry in entries:
        if not isinstance(entry, dict):
            skipped.append({'match_id': None, 'reason': 'invalid_data'})
            continue
        match_id = entry.get('match_id')
        cote_home = entry.get('cote_home')
        cote_draw = entry.get('cote_draw')
        cote_away = entry.get('cote_away')

        if not isinstance(match_id, int) or match_id not in allowed_ids:
            skipped.append({'match_id': match_id, 'reason': 'not_allowed'})
            continue

        cotes = [cote_home, cote_draw, cote_away]
        if not all(isinstance(c, int) and 10 <= c <= 1000 for c in cotes):
            skipped.append({'match_id': match_id, 'reason': 'invalid_odds'})
            continue

        if not _odds_are_consistent(cotes):
            skipped.append({'match_id': match_id, 'reason': 'inconsistent_odds'})
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
    cutoff = now + dt.timedelta(days=7)

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
@require_GET
def live_matches_api(request):
    if not _check_bearer(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    from .models import Match

    matches = (
        Match.objects
        .filter(_live_window(timezone.now()))
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
            'current_home_score': m.home_score,
            'current_away_score': m.away_score,
        }
        for m in matches
    ]
    return JsonResponse(data, safe=False)


@csrf_exempt
@require_POST
def update_scores_api(request):
    if not _check_bearer(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    import json
    from .models import Match
    from .services import _calculate_points_for_match

    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    entries = body.get('scores', []) if isinstance(body, dict) else None
    if not isinstance(entries, list):
        return JsonResponse({'error': 'scores must be a list'}, status=400)

    STATUS_MAP = {'in_play': Match.STATUS_IN_PLAY, 'finished': Match.STATUS_FINISHED}

    updated = []
    skipped = []
    # web content seen by Gemini is untrusted: only accept the matches it was asked about
    allowed = {m.pk: m for m in Match.objects.filter(_live_window(timezone.now()))}

    for entry in entries:
        if not isinstance(entry, dict):
            skipped.append({'match_id': None, 'reason': 'invalid_data'})
            continue
        match_id = entry.get('match_id')
        home_score = entry.get('home_score')
        away_score = entry.get('away_score')
        raw_status = entry.get('status')
        status = STATUS_MAP.get(raw_status) if isinstance(raw_status, str) else None

        if status is None or not all(isinstance(s, int) and 0 <= s <= 200 for s in (home_score, away_score)):
            skipped.append({'match_id': match_id, 'reason': 'invalid_data'})
            continue

        match = allowed.get(match_id) if isinstance(match_id, int) else None
        if match is None:
            skipped.append({'match_id': match_id, 'reason': 'not_allowed'})
            continue

        if match.status == Match.STATUS_FINISHED:
            if status != Match.STATUS_FINISHED:
                skipped.append({'match_id': match_id, 'reason': 'already_finished'})
                continue
            if (match.home_score, match.away_score) == (home_score, away_score):
                skipped.append({'match_id': match_id, 'reason': 'unchanged'})
                continue

        match.status = status
        match.home_score = home_score
        match.away_score = away_score
        match.save(update_fields=['status', 'home_score', 'away_score'])

        if status == Match.STATUS_FINISHED:
            _calculate_points_for_match(match)

        updated.append(match_id)

    return JsonResponse({'updated': updated, 'skipped': skipped})


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
