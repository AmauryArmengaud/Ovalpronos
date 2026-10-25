"""500s are reported to PostHog error tracking with no personal data."""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import RequestFactory, TestCase

from ovalpronos.analytics import ErrorTrackingMiddleware

User = get_user_model()


class ErrorTrackingMiddlewareTest(TestCase):
    def setUp(self):
        self.client_mock = MagicMock()
        patcher = patch('ovalpronos.analytics._get_client', return_value=self.client_mock)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.mw = ErrorTrackingMiddleware(lambda r: None)
        self.user = User.objects.create_user(username='err', password='x', email='secret@test.local')

    def _request(self, path, user=None):
        request = RequestFactory().get(path + '?token=abc', REMOTE_ADDR='203.0.113.9')
        request.user = user or MagicMock(is_authenticated=False)
        return request

    def test_unhandled_error_is_sent_with_opaque_id_only(self):
        exc = ValueError('boom')
        self.assertIsNone(self.mw.process_exception(self._request('/predictions/', self.user), exc))
        args, kwargs = self.client_mock.capture_exception.call_args
        self.assertIs(args[0], exc)
        self.assertEqual(kwargs['distinct_id'], f'user_{self.user.pk}')
        self.assertEqual(kwargs['properties']['$request_path'], '/predictions/')
        sent = repr(kwargs)
        for leak in ('secret@test.local', '203.0.113.9', 'token=abc'):
            self.assertNotIn(leak, sent)

    def test_password_reset_token_is_not_sent(self):
        self.mw.process_exception(self._request('/accounts/password-reset-confirm/MQ/abc-123/'), ValueError())
        path = self.client_mock.capture_exception.call_args.kwargs['properties']['$request_path']
        self.assertNotIn('abc-123', path)

    def test_expected_http_errors_are_not_reported(self):
        for exc in (Http404(), PermissionDenied()):
            self.mw.process_exception(self._request('/x/'), exc)
        self.client_mock.capture_exception.assert_not_called()

    def test_posthog_failure_never_breaks_the_response(self):
        self.client_mock.capture_exception.side_effect = RuntimeError('network down')
        self.assertIsNone(self.mw.process_exception(self._request('/x/'), ValueError()))
