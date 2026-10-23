from django.conf import settings

_client = None


def _get_client():
    global _client
    if _client is None and settings.POSTHOG_ENABLED and settings.POSTHOG_API_KEY:
        from posthog import Posthog
        _client = Posthog(settings.POSTHOG_API_KEY, host='https://eu.i.posthog.com')
    return _client


# Set by the consent banner (templates/partials/consent_banner.html) when the visitor accepts
CONSENT_COOKIE = 'op_analytics'


def capture(request, event: str, properties: dict = None):
    """Server-side analytics event, sent only if the visitor accepted statistics."""
    if request.COOKIES.get(CONSENT_COOKIE) != 'granted' or not request.user.is_authenticated:
        return
    try:
        client = _get_client()
        if client:
            client.capture(f'user_{request.user.pk}', event, properties or {})
    except Exception:
        pass
