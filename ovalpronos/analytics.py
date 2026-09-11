from django.conf import settings

_client = None


def _get_client():
    global _client
    if _client is None and settings.POSTHOG_ENABLED and settings.POSTHOG_API_KEY:
        from posthog import Posthog
        _client = Posthog(settings.POSTHOG_API_KEY, host='https://eu.i.posthog.com')
    return _client


def capture(user_pk: int, event: str, properties: dict = None):
    try:
        client = _get_client()
        if client:
            client.capture(f'user_{user_pk}', event, properties or {})
    except Exception:
        pass
