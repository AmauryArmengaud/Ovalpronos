"""
Sync service for rugby-live-data (RapidAPI)
===========================================
API documentation: https://rapidapi.com/rugby-live-data-rugby-live-data-default/api/rugby-live-data

Endpoint used:
    GET https://rugby-live-data.p.rapidapi.com/fixtures/{comp_id}/{season}
    Headers:
        x-rapidapi-host: rugby-live-data.p.rapidapi.com
        x-rapidapi-key: <RapidAPI key>

Usage from Django management:
    python manage.py sync_matches
    python manage.py sync_matches --comp TOP14
"""

import requests
import logging
from datetime import datetime, timezone as dt_timezone
from django.conf import settings
from django.utils.text import slugify
from django.db import transaction

logger = logging.getLogger(__name__)

API_BASE_URL = 'https://rugby-live-data.p.rapidapi.com'

HEADERS = {
    'x-rapidapi-host': 'rugby-live-data.p.rapidapi.com',
    'x-rapidapi-key': settings.RAPIDAPI_KEY,
    'Content-Type': 'application/json',
}

STATUS_MAP = {
    'Not Started': 'SCHEDULED',
    'First Half':  'IN_PLAY',
    'Half Time':   'IN_PLAY',
    'Second Half': 'IN_PLAY',
    'Full Time':   'FINISHED',
    'Result':      'FINISHED',
    'Postponed':   'POSTPONED',
    'Cancelled':   'CANCELLED',
}

# Manual mapping: external_id → slug (PNG file name) + short_name (3 chars)
# Slug must match static/img/teams/<slug>.png
TEAM_OVERRIDES = {
    6767:  {'slug': 'clermont',   'short_name': 'ASM'},  # ASM Clermont Auvergne
    14567: {'slug': 'bayonne',    'short_name': 'BAY'},  # Aviron Bayonnais
    6167:  {'slug': 'castres',    'short_name': 'CO'},   # Castres Olympique
    152:   {'slug': 'lyon',       'short_name': 'LOU'},  # Lyon Olympique Universitaire
    14867: {'slug': 'montpellier','short_name': 'MHR'},  # Montpellier Hérault Rugby
    134:   {'slug': 'toulon',     'short_name': 'RCT'},  # RC Toulon
    140:   {'slug': 'racing92',   'short_name': 'R92'},  # Racing 92
    10367: {'slug': 'pau',        'short_name': 'PAU'},  # Section Paloise
    4817:  {'slug': 'paris',      'short_name': 'SFP'},  # Stade Français Paris
    158:   {'slug': 'larochelle', 'short_name': 'SRO'},  # Stade Rochelais
    7067:  {'slug': 'toulouse',   'short_name': 'ST'},   # Stade Toulousain
    4967:  {'slug': 'perpignan',  'short_name': 'PER'},  # USAP
    131:   {'slug': 'bordeaux',   'short_name': 'UBB', 'name': 'Union Bordeaux-Bègles'},
    14717: {'slug': 'montauban',  'short_name': 'USM'},  # US Montauban
    1322:  {'slug': 'vannes',     'short_name': 'RCV'}, # Racing Club Vannes
    17:    {'slug': 'tbc',        'short_name': 'TBC'},  # To be confirmed
}


def _get_fixtures(comp_id, season):
    """
    Calls the /fixtures/{comp_id}/{season} endpoint.
    Returns the list of fixtures, or None on error.
    """
    url = f"{API_BASE_URL}/fixtures/{comp_id}/{season}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get('results', [])
    except requests.RequestException as e:
        logger.error(f"Erreur API rugby-live-data (fixtures/{comp_id}/{season}): {e}")
        return None


def _resolve_competition(code):
    """
    Active Competition for this code, or None.

    A code is shared by every season of a competition (one row per season),
    so the lookup is restricted to active rows. If several seasons are active
    at once, the most recent one wins and a warning is logged.
    """
    from apps.matches.models import Competition

    candidates = list(Competition.objects.filter(code=code, is_active=True).order_by('-season', '-pk'))
    if not candidates:
        logger.error(f"Aucune compétition active pour le code : {code}")
        return None
    if len(candidates) > 1:
        logger.warning(
            f"{len(candidates)} compétitions actives pour le code {code} "
            f"({', '.join(c.season for c in candidates)}) : sync de {candidates[0].season}"
        )
    return candidates[0]


def sync_competition_matches(competition):
    """
    Syncs the matches of one competition.
    Creates or updates the teams, then the matches.

    Args:
        competition: a Competition instance (preferred), or a code (e.g. 'TOP14'),
            resolved to the active season of that code
    """
    from apps.matches.models import Team, Match

    if isinstance(competition, str):
        competition = _resolve_competition(competition)
        if competition is None:
            return {'created': 0, 'updated': 0, 'changes': [], 'points_calculated': 0}
    competition_code = competition.code

    games = _get_fixtures(competition.external_id, competition.season)
    if games is None:
        return {'created': 0, 'updated': 0, 'changes': [], 'points_calculated': 0, 'api_error': True}

    created_count = 0
    updated_count = 0
    changes = []
    points_calculated = 0

    # Prefetch existing match states for comparison
    existing = {
        m.external_id: (m.status, m.home_score, m.away_score)
        for m in Match.objects.filter(
            external_id__in=[g['id'] for g in games]
        ).only('external_id', 'status', 'home_score', 'away_score')
    }

    with transaction.atomic():
        for game in games:
            try:
                # Teams
                home_overrides = TEAM_OVERRIDES.get(game['home_id'], {})
                away_overrides = TEAM_OVERRIDES.get(game['away_id'], {})

                home_team, _ = Team.objects.update_or_create(
                    external_id=game['home_id'],
                    defaults={
                        'name': home_overrides.get('name', game['home']),
                        'slug': home_overrides.get('slug', slugify(game['home'])),
                        'short_name': home_overrides.get('short_name', ''),
                    },
                )
                away_team, _ = Team.objects.update_or_create(
                    external_id=game['away_id'],
                    defaults={
                        'name': away_overrides.get('name', game['away']),
                        'slug': away_overrides.get('slug', slugify(game['away'])),
                        'short_name': away_overrides.get('short_name', ''),
                    },
                )

                # Status
                api_status = game.get('status', 'Not Started')
                status = STATUS_MAP.get(api_status.title(), 'SCHEDULED')

                # Date (ISO 8601 UTC)
                match_datetime = datetime.fromisoformat(game['date']).astimezone(dt_timezone.utc)
                match_datetime = match_datetime.replace(tzinfo=dt_timezone.utc)

                old = existing.get(game['id'])
                old_status = old[0] if old else None

                defaults = {
                    'competition': competition,
                    'home_team': home_team,
                    'away_team': away_team,
                    'round': str(game.get('game_week', '')),
                    'datetime': match_datetime,
                    'venue': game.get('venue', '') or '',
                }
                # Scores and IN_PLAY/FINISHED come from sync_live_scores.py: the API
                # result is unreliable, so it is only used for brand-new matches
                # (no predictions yet) and for calendar statuses
                if old is None:
                    defaults.update(status=status, home_score=game.get('home_score'), away_score=game.get('away_score'))
                elif (old_status not in (Match.STATUS_IN_PLAY, Match.STATUS_FINISHED)
                      and status in (Match.STATUS_SCHEDULED, Match.STATUS_POSTPONED, Match.STATUS_CANCELLED)):
                    defaults['status'] = status

                match, created = Match.objects.update_or_create(
                    external_id=game['id'],
                    defaults=defaults,
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1
                    if match.status != old_status:
                        changes.append(f"{game['home']} vs {game['away']}: {old_status}→{match.status}")

                if not created and match.status == Match.STATUS_CANCELLED:
                    _calculate_points_for_match(match)
                    points_calculated += 1

            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Données malformées pour game {game.get('id', '?')}: {e}")
                continue

    logger.info(
        f"[{competition_code}] Sync terminée : {created_count} créés, {updated_count} mis à jour, "
        f"{len(changes)} changements, {points_calculated} matchs scorés"
    )
    return {
        'created': created_count,
        'updated': updated_count,
        'changes': changes,
        'points_calculated': points_calculated,
        'api_error': False,
    }


def refresh_user_scores_for_match(match):
    """
    Refresh the global and per-competition UserScore cache for all users
    who have a scored prediction on this match.
    Called at the end of _calculate_points_for_match().
    """
    from apps.rankings.models import UserScore
    from apps.predictions.models import Prediction
    from django.db.models import Sum, Count, Q
    from django.contrib.auth import get_user_model

    User = get_user_model()

    affected_user_ids = list(
        Prediction.objects
        .filter(match=match, points_earned__isnull=False)
        .values_list('user_id', flat=True)
        .distinct()
    )
    if not affected_user_ids:
        return

    for user in User.objects.filter(pk__in=affected_user_ids):
        base_qs = Prediction.objects.filter(user=user, points_earned__isnull=False)

        # Global scope (competition=None, league=None)
        agg = base_qs.aggregate(
            total=Sum('points_earned'),
            total_count=Count('pk'),
            exact=Count('pk', filter=Q(result_type='EXACT')),
            gap=Count('pk', filter=Q(result_type='GAP')),
            win=Count('pk', filter=Q(result_type='WIN')),
        )
        UserScore.objects.update_or_create(
            user=user,
            competition=None,
            league=None,
            defaults={
                'points': agg['total'] or 0,
                'prediction_count': agg['total_count'],
                'exact_count': agg['exact'],
                'gap_count': agg['gap'],
                'win_count': agg['win'],
            }
        )

        # Per-competition scope
        agg_comp = base_qs.filter(match__competition=match.competition).aggregate(
            total=Sum('points_earned'),
            total_count=Count('pk'),
            exact=Count('pk', filter=Q(result_type='EXACT')),
            gap=Count('pk', filter=Q(result_type='GAP')),
            win=Count('pk', filter=Q(result_type='WIN')),
        )
        UserScore.objects.update_or_create(
            user=user,
            competition=match.competition,
            league=None,
            defaults={
                'points': agg_comp['total'] or 0,
                'prediction_count': agg_comp['total_count'],
                'exact_count': agg_comp['exact'],
                'gap_count': agg_comp['gap'],
                'win_count': agg_comp['win'],
            }
        )

    logger.info(f"UserScore refreshed for {len(affected_user_ids)} user(s) — {match}")


def _calculate_points_for_match(match):
    """
    Triggers the points calculation for every prediction of a finished match.
    """
    from apps.predictions.models import Prediction
    from apps.predictions.services import calculate_points

    if match.status == 'CANCELLED':
        Prediction.objects.filter(match=match).update(
            points_earned=0,
            result_type='CANCELLED'
        )
        logger.info(f"Match annulé — {Prediction.objects.filter(match=match).count()} pronostic(s) remboursés")
        refresh_user_scores_for_match(match)
        return

    if not match.has_odds:
        logger.info(f"Pas de cotes pour {match} — calcul ignoré")
        return

    # NB: ALL predictions of the match are recalculated, even those already
    # scored (points_earned not null). A match can be scored a first time
    # with a still provisional score (e.g. a live sync on a match wrongly
    # detected as FINISHED), then have its score corrected by the next sync.
    # Without this systematic recalculation, points stay frozen on the old
    # score and are never corrected, including through the admin action
    # "Recalculer les points".
    predictions = Prediction.objects.filter(match=match)

    count = 0
    for prediction in predictions:
        result = calculate_points(prediction, match)
        if result is not None:
            new_points, new_result_type = result
            if (prediction.points_earned, prediction.result_type) != (new_points, new_result_type):
                prediction.points_earned, prediction.result_type = new_points, new_result_type
                prediction.save(update_fields=['points_earned', 'result_type'])
                count += 1

    if count > 0:
        logger.info(f"Points calculés pour {count} pronostic(s) — {match}")
        refresh_user_scores_for_match(match)


def sync_all_competitions():
    from apps.matches.models import Competition
    results = []
    for comp in Competition.objects.filter(is_active=True):
        r = sync_competition_matches(comp)
        r['competition'] = comp.code
        results.append(r)
    return results


def campaign_report(competition, since=None):
    """Sign-up funnel of a competition landing, per source.

    A sign-up belongs to the landing when its first known page is that landing;
    sign-ups of the period that entered elsewhere are reported apart, without views.
    `since` defaults to the first recorded landing view (campaign start).
    Returns {'since', 'landing': {'rows', 'total'}, 'other': {'rows', 'total'}};
    each row: source, views (None outside the landing), signups, conversion, activated, leagues.
    """
    from collections import defaultdict
    from django.contrib.auth import get_user_model
    from django.db.models import Exists, OuterRef, Sum
    from django.urls import reverse
    from django.utils import timezone
    from apps.leagues.models import League
    from apps.predictions.models import Prediction

    if since is None:
        first_view = competition.landing_views.order_by('day').first()
        since = first_view.day if first_view else timezone.localdate()
    start = timezone.make_aware(datetime.combine(since, datetime.min.time()))
    landing_path = reverse('matches:competition_landing', kwargs={'code': competition.code.lower()})

    views = dict(
        competition.landing_views.filter(day__gte=since)
        .values('source').annotate(total=Sum('count')).values_list('source', 'total')
    )
    signups = get_user_model().objects.filter(date_joined__gte=start).annotate(
        activated=Exists(Prediction.objects.filter(user=OuterRef('pk'))),
    ).values('pk', 'signup_source', 'signup_landing_path', 'activated')
    league_creators = set(
        League.objects.filter(competitions=competition, created_at__gte=start).values_list('creator_id', flat=True)
    )

    funnels = {'landing': defaultdict(lambda: defaultdict(int)), 'other': defaultdict(lambda: defaultdict(int))}
    for user in signups:
        funnel = funnels['landing' if user['signup_landing_path'] == landing_path else 'other']
        stats = funnel[user['signup_source'] or 'direct']
        stats['signups'] += 1
        stats['activated'] += user['activated']
        stats['leagues'] += user['pk'] in league_creators
    for source in views:
        funnels['landing'].setdefault(source, defaultdict(int))

    def section(stats_by_source, with_views):
        rows = [
            _funnel_row(source, views.get(source, 0) if with_views else None, stats)
            for source, stats in stats_by_source.items()
        ]
        rows.sort(key=lambda row: (-row['signups'], row['source']))
        totals = defaultdict(int)
        for row in rows:
            for key in ('signups', 'activated', 'leagues'):
                totals[key] += row[key]
        total_views = sum(views.values()) if with_views else None
        return {'rows': rows, 'total': _funnel_row('', total_views, totals)}

    return {'since': since, 'landing': section(funnels['landing'], True), 'other': section(funnels['other'], False)}


def _funnel_row(source, views, stats):
    return {
        'source': source,
        'views': views,
        'signups': stats['signups'],
        'conversion': stats['signups'] / views if views else None,
        'activated': stats['activated'],
        'leagues': stats['leagues'],
    }
