import posthog as _posthog
from django.conf import settings

_POSTHOG_HOST = 'https://eu.i.posthog.com'


def _configured():
    return settings.POSTHOG_ENABLED and settings.POSTHOG_API_KEY


def capture(user_pk: int, event: str, properties: dict = None):
    if not _configured():
        return
    _posthog.project_api_key = settings.POSTHOG_API_KEY
    _posthog.host = _POSTHOG_HOST
    _posthog.capture(f'user_{user_pk}', event, properties or {})
