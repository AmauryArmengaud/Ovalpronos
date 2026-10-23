"""Analytics consent: nothing reaches PostHog until the visitor accepts."""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from ovalpronos.analytics import CONSENT_COOKIE, capture

User = get_user_model()


class ServerSideCaptureConsentTest(TestCase):
    def setUp(self):
        self.client_mock = MagicMock()
        patcher = patch('ovalpronos.analytics._get_client', return_value=self.client_mock)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = User.objects.create_user(username='c', password='x', email='c@test.local')

    def _request(self, cookie=None):
        request = RequestFactory().get('/')
        request.user = self.user
        if cookie is not None:
            request.COOKIES[CONSENT_COOKIE] = cookie
        return request

    def test_event_sent_after_consent(self):
        capture(self._request('granted'), 'prediction_saved', {'match_id': 1})
        self.client_mock.capture.assert_called_once_with(
            f'user_{self.user.pk}', 'prediction_saved', {'match_id': 1}
        )

    def test_no_event_without_choice_or_after_refusal(self):
        capture(self._request(), 'prediction_saved')
        capture(self._request('denied'), 'prediction_saved')
        self.client_mock.capture.assert_not_called()


@override_settings(POSTHOG_ENABLED=True, POSTHOG_API_KEY='phc_test')
class ConsentBannerTest(TestCase):
    def test_posthog_is_not_loaded_by_the_page_itself(self):
        html = self.client.get(reverse('matches:rules')).content.decode()
        self.assertIn('id="consent-banner"', html)
        # the library is only injected by the consent script once the visitor accepts
        self.assertNotIn('<script src="https://eu-assets.i.posthog.com', html)

    def test_refuse_is_as_easy_as_accept(self):
        html = self.client.get(reverse('matches:rules')).content.decode()
        self.assertIn('data-consent="granted"', html)
        self.assertIn('data-consent="denied"', html)

    def test_footer_links_to_legal_pages_and_choice(self):
        html = self.client.get(reverse('matches:rules')).content.decode()
        for name in ('legal_notice', 'legal_privacy', 'legal_terms'):
            self.assertIn(reverse(f'matches:{name}'), html)
        self.assertIn('data-consent-open', html)


class LegalPagesTest(TestCase):
    def test_pages_are_public_and_name_the_publisher_and_host(self):
        for name in ('legal_notice', 'legal_privacy', 'legal_terms'):
            resp = self.client.get(reverse(f'matches:{name}'))
            self.assertEqual(resp.status_code, 200, name)
        notice = self.client.get(reverse('matches:legal_notice')).content.decode()
        for fact in ('Amaury LEMAUR-ARMENGAUD', 'contact@ovalpronos.com', 'Hetzner Online GmbH', 'Gunzenhausen'):
            self.assertIn(fact, notice)

    def test_register_page_mentions_terms(self):
        html = self.client.get(reverse('accounts:register')).content.decode()
        self.assertIn(reverse('matches:legal_terms'), html)
        self.assertIn(reverse('matches:legal_privacy'), html)
