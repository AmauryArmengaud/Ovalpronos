from django import template
from django.utils import timezone
from datetime import timedelta

register = template.Library()


@register.inclusion_tag('admin/partials/dashboard_stats.html')
def dashboard_stats():
    from apps.matches.models import Match
    from apps.predictions.models import Prediction
    from django.contrib.auth import get_user_model

    User = get_user_model()
    now = timezone.now()

    return {
        'users_active': User.objects.filter(is_active=True).count(),
        'matches_no_odds': Match.objects.filter(status='SCHEDULED', cote_home__isnull=True).count(),
        'unscored_predictions': Prediction.objects.filter(
            points_earned__isnull=True, match__status='FINISHED'
        ).count(),
        'upcoming_matches': Match.objects.filter(
            status='SCHEDULED',
            datetime__gte=now,
            datetime__lte=now + timedelta(days=7),
        ).count(),
    }
