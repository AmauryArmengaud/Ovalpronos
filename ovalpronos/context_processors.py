from django.conf import settings


def analytics(request):
    return {
        'POSTHOG_API_KEY': settings.POSTHOG_API_KEY if settings.POSTHOG_ENABLED else '',
    }
