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


def send_deadline_reminders():
    """
    Send a prediction reminder to users who have submitted 0 predictions for
    the upcoming round. "Upcoming" = matches starting in the next 22–26 hours.

    Returns the number of emails sent.
    """
    import datetime
    from django.contrib.auth import get_user_model
    from apps.matches.models import Match

    User = get_user_model()

    now = timezone.now()
    window_start = now + datetime.timedelta(hours=22)
    window_end = now + datetime.timedelta(hours=26)

    upcoming_matches = Match.objects.filter(
        status=Match.STATUS_SCHEDULED,
        datetime__gte=window_start,
        datetime__lte=window_end,
    ).select_related('competition', 'home_team', 'away_team')

    if not upcoming_matches.exists():
        logger.info("send_deadline_reminders: no matches in window, nothing to send.")
        return 0

    # Group by (competition, round)
    rounds = (
        upcoming_matches
        .values('competition', 'competition__name', 'round')
        .distinct()
    )

    sent = 0
    for r in rounds:
        competition_id = r['competition']
        competition_name = r['competition__name']
        round_label = r['round']

        round_matches = upcoming_matches.filter(
            competition_id=competition_id,
            round=round_label,
        )
        match_ids = list(round_matches.values_list('pk', flat=True))

        # Users who have at least one prediction in this round
        from apps.predictions.models import Prediction
        users_with_predictions = (
            Prediction.objects
            .filter(match_id__in=match_ids)
            .values_list('user_id', flat=True)
            .distinct()
        )

        # All active users minus those who already predicted
        recipients = User.objects.filter(
            is_active=True,
            email__gt='',  # non-empty email
        ).exclude(pk__in=users_with_predictions)

        first_kickoff = round_matches.order_by('datetime').first()

        for user in recipients:
            context = {
                'user': user,
                'competition_name': competition_name,
                'round_label': round_label,
                'match_count': round_matches.count(),
                'first_kickoff': first_kickoff.datetime,
                'site_url': getattr(settings, 'SITE_URL', ''),
            }
            subject = f"[Oval'Pronos] Tu n'as pas encore pronostiqué — {competition_name} J{round_label}"
            html_body = render_to_string('accounts/emails/deadline_reminder.html', context)
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
