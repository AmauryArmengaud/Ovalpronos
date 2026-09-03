"""
Email notification tasks for Oval'Pronos.
Called via management commands (send_deadline_reminders, send_results_summary).
"""

import logging
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


_MONTHS_FR = ['jan.', 'fév.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
_DAYS_FR = ['Lun.', 'Mar.', 'Mer.', 'Jeu.', 'Ven.', 'Sam.', 'Dim.']


def _format_kickoff(dt):
    """Format a datetime as 'Sam. 14 sept. à 17h00' in French."""
    import datetime
    local_dt = dt.astimezone(timezone.get_current_timezone())
    day = _DAYS_FR[local_dt.weekday()]
    month = _MONTHS_FR[local_dt.month - 1]
    return f"{day} {local_dt.day} {month} à {local_dt.strftime('%Hh%M')}"


def send_deadline_reminders():
    """
    Send a weekly prediction reminder via Brevo template #1.

    Triggered when the earliest upcoming match (with odds, not locked) starts
    in the next 22–26 hours. Each user receives at most one reminder per 6 days.
    The email lists all upcoming matches the user hasn't predicted yet.

    Returns the number of emails sent.
    """
    import datetime
    from django.contrib.auth import get_user_model
    from anymail.message import AnymailMessage
    from apps.matches.models import Match
    from apps.predictions.models import Prediction

    User = get_user_model()
    now = timezone.now()
    window_start = now + datetime.timedelta(hours=22)
    window_end = now + datetime.timedelta(hours=26)

    # Check if the first upcoming match (with odds) falls in the 22–26h window
    first_upcoming = (
        Match.objects
        .filter(
            status=Match.STATUS_SCHEDULED,
            datetime__gt=now,
            cote_home__isnull=False,
            cote_draw__isnull=False,
            cote_away__isnull=False,
        )
        .order_by('datetime')
        .first()
    )
    if not first_upcoming or not (window_start <= first_upcoming.datetime <= window_end):
        logger.info("send_deadline_reminders: first upcoming match not in window, nothing to send.")
        return 0

    # All upcoming matches with odds (not yet locked)
    all_upcoming = (
        Match.objects
        .filter(status=Match.STATUS_SCHEDULED, datetime__gt=now)
        .select_related('competition', 'home_team', 'away_team')
        .order_by('datetime')
    )
    all_upcoming_ids = list(all_upcoming.values_list('pk', flat=True))

    site_url = settings.SITE_URL.rstrip('/')
    predictions_url = f"{site_url}/predictions/"
    cooldown = datetime.timedelta(days=6)

    sent = 0
    for user in User.objects.filter(is_active=True, email__gt=''):
        # Once-per-week guard
        if user.last_reminder_sent and (now - user.last_reminder_sent) < cooldown:
            continue

        # Matches this user hasn't predicted yet
        predicted_ids = set(
            Prediction.objects
            .filter(user=user, match_id__in=all_upcoming_ids)
            .values_list('match_id', flat=True)
        )
        user_matches = [m for m in all_upcoming if m.pk not in predicted_ids]

        if not user_matches:
            continue

        match_params = [
            {
                'home': m.home_team.name,
                'away': m.away_team.name,
                'home_logo': f"{site_url}/static/img/teams/{m.home_team.slug}.png",
                'away_logo': f"{site_url}/static/img/teams/{m.away_team.slug}.png",
                'kickoff': _format_kickoff(m.datetime),
                'competition': m.competition.name,
            }
            for m in user_matches
        ]

        msg = AnymailMessage(
            to=[user.email],
            from_email=settings.DEFAULT_FROM_EMAIL,
            template_id=1,
            merge_global_data={
                'user_name': user.get_display_name(),
                'predictions_url': predictions_url,
                'matches': match_params,
            },
        )
        try:
            msg.send()
            user.last_reminder_sent = now
            user.save(update_fields=['last_reminder_sent'])
            sent += 1
        except Exception as e:
            logger.error(f"Failed to send deadline reminder to {user.email}: {e}")

    logger.info(f"send_deadline_reminders: {sent} email(s) sent.")
    return sent


def send_results_summary(competition_id=None, round_label=None):
    """
    Send a results summary to every user who had predictions on the given round.
    If competition_id and round_label are not provided, auto-detects rounds where
    all matches are FINISHED and at least one match was updated in the last 3 hours.

    Returns the number of emails sent.
    """
    import datetime
    from django.contrib.auth import get_user_model
    from apps.matches.models import Match, Competition
    from apps.predictions.models import Prediction

    User = get_user_model()

    if competition_id and round_label:
        # Explicit round
        round_matches = Match.objects.filter(
            competition_id=competition_id,
            round=round_label,
            status=Match.STATUS_FINISHED,
        ).select_related('competition', 'home_team', 'away_team')
        if not round_matches.exists():
            logger.info(f"send_results_summary: no finished matches for comp={competition_id} round={round_label}.")
            return 0
        scopes = [{'competition_id': competition_id, 'round': round_label}]
    else:
        # Auto-detect recently completed rounds
        cutoff = timezone.now() - datetime.timedelta(hours=3)
        recently_updated_finished = Match.objects.filter(
            status=Match.STATUS_FINISHED,
            updated_at__gte=cutoff,
        ).values('competition_id', 'round').distinct()

        scopes = []
        for scope in recently_updated_finished:
            cid, rnd = scope['competition_id'], scope['round']
            # Check all matches in this round are FINISHED
            total = Match.objects.filter(competition_id=cid, round=rnd).count()
            finished = Match.objects.filter(competition_id=cid, round=rnd, status=Match.STATUS_FINISHED).count()
            if total == finished:
                scopes.append({'competition_id': cid, 'round': rnd})

        if not scopes:
            logger.info("send_results_summary: no completed rounds detected.")
            return 0

    sent = 0
    for scope in scopes:
        cid = scope['competition_id']
        rnd = scope['round']

        round_matches = Match.objects.filter(
            competition_id=cid,
            round=rnd,
        ).select_related('competition', 'home_team', 'away_team')

        competition_name = round_matches.first().competition.name
        match_ids = list(round_matches.values_list('pk', flat=True))

        users_with_predictions = (
            User.objects.filter(
                predictions__match_id__in=match_ids,
                is_active=True,
                email__gt='',
            ).distinct()
        )

        for user in users_with_predictions:
            user_predictions = (
                Prediction.objects
                .filter(user=user, match_id__in=match_ids)
                .select_related('match__home_team', 'match__away_team')
                .order_by('match__datetime')
            )
            round_points = sum(p.points_earned or 0 for p in user_predictions)

            context = {
                'user': user,
                'competition_name': competition_name,
                'round_label': rnd,
                'predictions': user_predictions,
                'round_points': round_points,
                'site_url': getattr(settings, 'SITE_URL', ''),
            }
            subject = f"[Oval'Pronos] Résultats {competition_name} J{rnd} — {round_points} pts"
            html_body = render_to_string('accounts/emails/results_summary.html', context)
            msg = EmailMultiAlternatives(
                subject=subject,
                body=html_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            msg.attach_alternative(html_body, 'text/html')
            try:
                msg.send()
                sent += 1
            except Exception as e:
                logger.error(f"Failed to send results summary to {user.email}: {e}")

    logger.info(f"send_results_summary: {sent} email(s) sent.")
    return sent
