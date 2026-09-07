"""
Service de synchronisation avec rugby-live-data (RapidAPI)
===========================================================
Documentation API : https://rapidapi.com/rugby-live-data-rugby-live-data-default/api/rugby-live-data

Endpoint utilisé :
    GET https://rugby-live-data.p.rapidapi.com/fixtures/{comp_id}/{season}
    Headers:
        x-rapidapi-host: rugby-live-data.p.rapidapi.com
        x-rapidapi-key: <clé RapidAPI>

Usage depuis la gestion Django :
    python manage.py sync_matches
    python manage.py sync_matches --comp TOP14
"""

import requests
import logging
from datetime import datetime, timezone as dt_timezone
from django.conf import settings
from django.utils import timezone
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

# Correspondances manuelles : external_id → slug (nom du fichier PNG) + short_name (3 car.)
# Slug doit correspondre à static/img/teams/<slug>.png
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
    131:   {'slug': 'bordeaux',   'short_name': 'UBB'},  # Union Bordeaux-Bègles
    14717: {'slug': 'montauban',  'short_name': 'USM'},  # US Montauban
    1322:  {'slug': 'vannes',     'short_name': 'RCV'}, # Racing Club Vannes
    17:    {'slug': 'tbc',        'short_name': 'TBC'},  # À définir
}


def _get_match(match_id):
    """
    Appelle l'endpoint /match/{match_id} pour les données en temps réel.
    Retourne le dict 'match' ou None en cas d'erreur.
    """
    url = f"{API_BASE_URL}/match/{match_id}"
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        data = response.json()
        return data.get('results', {}).get('match')
    except requests.RequestException as e:
        logger.error(f"Erreur API rugby-live-data (match/{match_id}): {e}")
        return None


def _get_fixtures(comp_id, season):
    """
    Appelle l'endpoint /fixtures/{comp_id}/{season}.
    Retourne la liste des fixtures ou None en cas d'erreur.
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


def sync_competition_matches(competition_code):
    """
    Synchronise les matchs d'une compétition donnée.
    Crée ou met à jour les équipes, puis les matchs.

    Args:
        competition_code: clé dans RUGBY_COMPETITIONS (ex: 'TOP14')
    """
    from apps.matches.models import Competition, Team, Match

    comp_config = settings.RUGBY_COMPETITIONS.get(competition_code)
    if not comp_config:
        logger.error(f"Compétition inconnue : {competition_code}")
        return 0, 0

    season = comp_config.get('season', settings.RUGBY_SEASON)

    competition, _ = Competition.objects.get_or_create(
        external_id=comp_config['id'],
        season=str(season),
        defaults={
            'name': comp_config['name'],
            'code': competition_code,
            'country': comp_config['country'],
        }
    )

    games = _get_fixtures(comp_config['id'], season)
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
                # Équipes
                home_overrides = TEAM_OVERRIDES.get(game['home_id'], {})
                away_overrides = TEAM_OVERRIDES.get(game['away_id'], {})

                home_team, _ = Team.objects.update_or_create(
                    external_id=game['home_id'],
                    defaults={
                        'name': game['home'],
                        'slug': home_overrides.get('slug', slugify(game['home'])),
                        'short_name': home_overrides.get('short_name', ''),
                    },
                )
                away_team, _ = Team.objects.update_or_create(
                    external_id=game['away_id'],
                    defaults={
                        'name': game['away'],
                        'slug': away_overrides.get('slug', slugify(game['away'])),
                        'short_name': away_overrides.get('short_name', ''),
                    },
                )

                # Statut
                api_status = game.get('status', 'Not Started')
                status = STATUS_MAP.get(api_status, 'SCHEDULED')

                # Date (ISO 8601 UTC)
                match_datetime = datetime.fromisoformat(game['date']).astimezone(dt_timezone.utc)
                match_datetime = match_datetime.replace(tzinfo=dt_timezone.utc)

                # Score
                score_home = game.get('home_score')
                score_away = game.get('away_score')

                old = existing.get(game['id'])
                old_status = old[0] if old else None
                old_score_home = old[1] if old else None
                old_score_away = old[2] if old else None

                # Ne pas rétrograder un match déjà FINISHED vers SCHEDULED
                if old_status == Match.STATUS_FINISHED and status == Match.STATUS_SCHEDULED:
                    status = old_status
                    if score_home is None:
                        score_home = old_score_home
                    if score_away is None:
                        score_away = old_score_away

                match, created = Match.objects.update_or_create(
                    external_id=game['id'],
                    defaults={
                        'competition': competition,
                        'home_team': home_team,
                        'away_team': away_team,
                        'round': str(game.get('game_week', '')),
                        'datetime': match_datetime,
                        'venue': game.get('venue', '') or '',
                        'status': status,
                        'home_score': score_home,
                        'away_score': score_away,
                        },
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1
                    if old_status and old_status != status:
                        score_str = f" ({score_home}-{score_away})" if score_home is not None else ""
                        changes.append(
                            f"{game['home']} vs {game['away']}{score_str}: {old_status}→{status}"
                        )
                    elif score_home is not None and (score_home, score_away) != (old_score_home, old_score_away):
                        changes.append(
                            f"{game['home']} vs {game['away']} [{status}]: {old_score_home}-{old_score_away} → {score_home}-{score_away}"
                        )

                if status == Match.STATUS_FINISHED and score_home is not None:
                    _calculate_points_for_match(match)
                    points_calculated += 1
                elif status == Match.STATUS_CANCELLED:
                    _calculate_points_for_match(match)
                    points_calculated += 1

            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Données malformées pour game {game.get('id', '?')}: {e}")
                continue

    # Sync live : pour les matchs dont la date est passée mais pas encore FINISHED,
    # l'endpoint /fixtures ne reflète pas les scores en temps réel.
    # On appelle /match/{id} individuellement pour chacun.
    now = timezone.now()
    live_matches = Match.objects.filter(
        competition=competition,
        datetime__lte=now,
    ).exclude(
        status__in=[Match.STATUS_FINISHED, Match.STATUS_CANCELLED]
    ).select_related('home_team', 'away_team')

    for match in live_matches:
        if not match.external_id:
            continue
        live_data = _get_match(match.external_id)
        if not live_data:
            continue

        api_status = live_data.get('status', 'Not Started')
        live_status = STATUS_MAP.get(api_status, 'SCHEDULED')
        live_score_home = live_data.get('home_score')
        live_score_away = live_data.get('away_score')

        old_status = match.status
        old_score_home = match.home_score
        old_score_away = match.away_score

        status_changed = old_status != live_status
        score_changed = live_score_home is not None and (live_score_home, live_score_away) != (old_score_home, old_score_away)

        if not status_changed and not score_changed:
            continue

        match.status = live_status
        if live_score_home is not None:
            match.home_score = live_score_home
            match.away_score = live_score_away
        match.save(update_fields=['status', 'home_score', 'away_score'])

        label = f"{match.home_team.name} vs {match.away_team.name}"
        if status_changed:
            score_str = f" ({live_score_home}-{live_score_away})" if live_score_home is not None else ""
            changes.append(f"{label}{score_str}: {old_status}→{live_status} [live]")
        else:
            changes.append(f"{label} [{live_status}]: {old_score_home}-{old_score_away} → {live_score_home}-{live_score_away} [live]")

        if live_status == Match.STATUS_FINISHED and live_score_home is not None:
            _calculate_points_for_match(match)
            points_calculated += 1
        elif live_status == Match.STATUS_CANCELLED:
            _calculate_points_for_match(match)
            points_calculated += 1

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
    Déclenche le calcul des points pour tous les pronostics d'un match terminé.
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

    # NB : on recalcule TOUJOURS tous les pronostics du match, même ceux déjà
    # scorés (points_earned non-null). Un match peut être scoré une première
    # fois avec un score encore provisoire (ex. sync live sur un match mal
    # détecté comme FINISHED), puis voir son score corrigé plus tard par la
    # sync suivante. Sans ce recalcul systématique, les points restent figés
    # sur l'ancien score et ne sont jamais corrigés, y compris via l'action
    # admin "Recalculer les points".
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
    results = []
    for code in settings.RUGBY_COMPETITIONS:
        r = sync_competition_matches(code)
        r['competition'] = code
        results.append(r)
    return results
