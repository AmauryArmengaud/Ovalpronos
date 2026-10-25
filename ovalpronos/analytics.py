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


class ErrorTrackingMiddleware:
    """Reports unhandled view exceptions (500s) to PostHog error tracking.

    Hand-rolled instead of posthog's Django middleware, which sends the user's
    email and IP by default. Only the opaque user id and a path without query
    string or reset token leave the server.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        from django.core.exceptions import BadRequest, PermissionDenied, SuspiciousOperation
        from django.http import Http404

        if isinstance(exception, (Http404, PermissionDenied, BadRequest, SuspiciousOperation)):
            return None  # rendered as 4xx by Django, not bugs
        try:
            client = _get_client()
            if client:
                user = getattr(request, 'user', None)
                path = request.path
                if path.startswith('/accounts/password-reset-confirm/'):
                    path = '/accounts/password-reset-confirm/'
                client.capture_exception(
                    exception,
                    distinct_id=f'user_{user.pk}' if user is not None and user.is_authenticated else None,
                    properties={'$request_path': path, '$request_method': request.method},
                    disable_geoip=True,
                )
        except Exception:
            pass
        return None
