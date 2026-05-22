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
    6167:  {'slug': 'castres',    'short_name': 'CO'},  # Castres Olympique
    152:   {'slug': 'lyon',       'short_name': 'LOU'},  # Lyon Olympique Universitaire
    14867: {'slug': 'montpellier','short_name': 'MHR'},  # Montpellier Hérault Rugby
    134:   {'slug': 'toulon',     'short_name': 'RCT'},  # RC Toulon
    140:   {'slug': 'racing92',   'short_name': 'R92'},  # Racing 92
    10367: {'slug': 'pau',        'short_name': 'PAU'},  # Section Paloise
    4817:  {'slug': 'paris',      'short_name': 'SFP'},  # Stade Français Paris
    158:   {'slug': 'larochelle', 'short_name': 'SRO'},  # Stade Rochelais
    7067:  {'slug': 'toulouse',   'short_name': 'ST'},  # Stade Toulousain
    4967:  {'slug': 'perpignan',  'short_name': 'PER'},  # USAP
    131:   {'slug': 'bordeaux',   'short_name': 'UBB'},  # Union Bordeaux-Bègles
    14717: {'slug': 'montauban',  'short_name': 'USM'},  # US Montauban
    17:    {'slug': 'tbc',        'short_name': 'TBC'},  # À définir
}


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
        return 0, 0

    created_count = 0
    updated_count = 0

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
                    }
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

                if status == Match.STATUS_FINISHED and score_home is not None:
                    _calculate_points_for_match(match)
                elif status == Match.STATUS_CANCELLED:
                    _calculate_points_for_match(match)

            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Données malformées pour game {game.get('id', '?')}: {e}")
                continue

    logger.info(
        f"[{competition_code}] Sync terminée : {created_count} créés, {updated_count} mis à jour"
    )
    return created_count, updated_count


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
        return

    if not match.has_odds:
        logger.info(f"Pas de cotes pour {match} — calcul ignoré")
        return

    predictions = Prediction.objects.filter(
        match=match,
        points_earned__isnull=True
    )

    count = 0
    for prediction in predictions:
        result = calculate_points(prediction, match)
        if result is not None:
            prediction.points_earned, prediction.result_type = result
            prediction.save(update_fields=['points_earned', 'result_type'])
            count += 1

    if count > 0:
        logger.info(f"Points calculés pour {count} pronostic(s) — {match}")


def sync_all_competitions():
    from apps.matches.models import Competition
    total_created = 0
    total_updated = 0
    for competition in Competition.objects.filter(is_active=True):
        created, updated = sync_competition_matches(competition.code)
        total_created += created
        total_updated += updated
    return total_created, total_updated
