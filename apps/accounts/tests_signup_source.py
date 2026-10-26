from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from .models import CustomUser, Invitation
from .signup_source import carried_params, clean_params, normalize_path, normalize_value, referer_source, resolve_attribution
from .tests_invitations import REGISTER_URL, VALID_FORM


class NormalizationTest(SimpleTestCase):

    def test_values_are_lowercased_trimmed_and_restricted(self):
        self.assertEqual(normalize_value('  WhatsApp '), 'whatsapp')
        self.assertEqual(normalize_value('Groupe Été 1'), 'groupe_ete_1')
        self.assertEqual(normalize_value('<script>alert(1)</script>'), 'scriptalert1script')
        self.assertEqual(len(normalize_value('x' * 500)), 50)

    def test_path_keeps_only_a_local_path(self):
        self.assertEqual(normalize_path('/competitions/NATIONS/?utm_source=x'), '/competitions/nations/')
        self.assertEqual(normalize_path('https://evil.com/'), '/')
        self.assertEqual(normalize_path('//evil.com/x'), '/x')
        self.assertEqual(normalize_path('////evil.com'), '')
        self.assertEqual(normalize_path('javascript:alert(1)'), '')

    def test_referer_mapping(self):
        host = 'ovalpronos.com'
        self.assertEqual(referer_source('https://www.linkedin.com/feed/', host), 'linkedin')
        self.assertEqual(referer_source('https://lnkd.in/abc', host), 'linkedin')
        self.assertEqual(referer_source('https://www.google.fr/', host), 'google')
        self.assertEqual(referer_source('https://ovalpronos.com/rules/', host), '')
        self.assertEqual(referer_source('https://some-blog.example/', host), '')
        self.assertEqual(referer_source('', host), '')


class PriorityTest(SimpleTestCase):

    invitation = Invitation(cohort='CDM_2023')
    league = object()

    def source(self, params, **kwargs):
        return resolve_attribution(clean_params(params), **kwargs)['signup_source']

    def test_explicit_utm_wins_over_everything(self):
        self.assertEqual(
            self.source({'utm_source': 'WhatsApp', 'ref': 'linkedin'}, invitation=self.invitation, invite_league=self.league),
            'whatsapp',
        )

    def test_invitation_then_league_invite_then_referer_then_direct(self):
        self.assertEqual(self.source({'ref': 'linkedin'}, invitation=self.invitation, invite_league=self.league), 'invitation')
        self.assertEqual(self.source({'ref': 'linkedin'}, invite_league=self.league), 'league_invite')
        self.assertEqual(self.source({'ref': 'linkedin'}), 'linkedin')
        self.assertEqual(self.source({}), 'direct')

    def test_invitation_campaign_defaults_to_cohort(self):
        self.assertEqual(resolve_attribution({}, invitation=self.invitation)['signup_campaign'], 'cdm_2023')

    def test_details_are_kept_whatever_the_source(self):
        fields = resolve_attribution(
            clean_params({'utm_medium': 'Social', 'utm_content': 'msg-B', 'landing': '/competitions/nations/'}),
            invite_league=self.league,
        )
        self.assertEqual(fields['signup_medium'], 'social')
        self.assertEqual(fields['signup_content'], 'msg-b')
        self.assertEqual(fields['signup_landing_path'], '/competitions/nations/')


class CarriedParamsTest(SimpleTestCase):

    def test_first_page_becomes_landing_and_reads_external_referer(self):
        request = RequestFactory().get('/competitions/nations/', HTTP_REFERER='https://www.linkedin.com/')
        self.assertEqual(carried_params(request), {'landing': '/competitions/nations/', 'ref': 'linkedin'})

    def test_values_in_url_win_and_referer_is_ignored_when_utm_present(self):
        request = RequestFactory().get(
            '/accounts/register/', {'utm_source': 'whatsapp', 'landing': '/competitions/nations/'},
            HTTP_REFERER='https://www.linkedin.com/',
        )
        self.assertEqual(carried_params(request), {'utm_source': 'whatsapp', 'landing': '/competitions/nations/'})


class AuthLinksCarryUtmTest(TestCase):

    def test_navbar_and_bottom_nav_carry_utm_on_home(self):
        response = self.client.get(reverse('matches:home'), {'utm_source': 'linkedin', 'utm_content': 'post_a'})
        register = 'href="/accounts/register/?next=%2F&amp;utm_source=linkedin&amp;utm_content=post_a&amp;landing=%2F"'
        login = 'href="/accounts/login/?next=%2F&amp;utm_source=linkedin&amp;utm_content=post_a&amp;landing=%2F"'
        self.assertContains(response, register, count=2)  # navbar + mobile bottom nav
        self.assertContains(response, login, count=2)
        self.assertNotContains(response, 'href="/accounts/register/"')

    def test_login_page_link_to_register_keeps_utm(self):
        response = self.client.get(reverse('accounts:login'), {'next': '/competitions/nations/', 'utm_source': 'whatsapp'})
        self.assertContains(response, '/accounts/register/?next=%2Fcompetitions%2Fnations%2F&amp;utm_source=whatsapp')


class RegisterStoresAttributionTest(TestCase):

    @patch('apps.accounts.views._verify_turnstile', return_value=True)
    def test_full_attribution_travels_through_the_form(self, _mock):
        query = {
            'utm_source': ' WhatsApp', 'utm_medium': 'Social', 'utm_campaign': 'Lancement CDN',
            'utm_content': 'msg_b', 'landing': '/competitions/nations/',
        }
        response = self.client.get(REGISTER_URL, query)
        self.assertContains(response, 'name="utm_source" value="whatsapp"')
        self.assertContains(response, 'name="landing" value="/competitions/nations/"')
        hidden = {k: v for k, v in response.context['attribution'].items()}
        self.client.post(REGISTER_URL, {**VALID_FORM, **hidden})
        user = CustomUser.objects.get(username='Pepito')
        self.assertEqual(
            (user.signup_source, user.signup_medium, user.signup_campaign, user.signup_content, user.signup_landing_path),
            ('whatsapp', 'social', 'lancement_cdn', 'msg_b', '/competitions/nations/'),
        )

    @patch('apps.accounts.views._verify_turnstile', return_value=True)
    def test_external_referer_on_register_page_is_kept(self, _mock):
        response = self.client.get(REGISTER_URL, HTTP_REFERER='https://www.linkedin.com/feed/')
        self.client.post(REGISTER_URL, {**VALID_FORM, **response.context['attribution']})
        user = CustomUser.objects.get(username='Pepito')
        self.assertEqual((user.signup_source, user.signup_landing_path), ('linkedin', '/accounts/register/'))

    @patch('apps.accounts.views._verify_turnstile', return_value=True)
    def test_2023_invitation_without_utm(self, _mock):
        invitation = Invitation.objects.create(email='pepito@test.local', cohort='CDM_2023')
        self.client.post(REGISTER_URL, {**VALID_FORM, 'invite': invitation.token})
        user = CustomUser.objects.get(username='Pepito')
        self.assertEqual((user.signup_source, user.signup_campaign), ('invitation', 'cdm_2023'))


class LightRegisterFormTest(TestCase):

    @patch('apps.accounts.views._verify_turnstile', return_value=True)
    def test_cold_visitor_signs_up_with_four_fields(self, _mock):
        response = self.client.get(REGISTER_URL)
        self.assertNotContains(response, 'name="first_name"')
        self.assertNotContains(response, 'name="display_name"')
        data = {k: VALID_FORM[k] for k in ('username', 'email', 'password1', 'password2', 'cf-turnstile-response')}
        self.client.post(REGISTER_URL, data)
        self.assertTrue(CustomUser.objects.filter(username='Pepito').exists())

    def test_invitation_still_shows_prefilled_names(self):
        invitation = Invitation.objects.create(email='p@test.local', pseudo='Fabien', first_name='Fabien', cohort='CDM_2023')
        response = self.client.get(REGISTER_URL, {'invite': invitation.token})
        self.assertContains(response, 'name="first_name"')
        self.assertContains(response, 'value="Fabien"')


class ReferralCodeTests(TestCase):
    def test_stable_per_user_and_survives_normalization(self):
        from .signup_source import referral_code
        u1 = CustomUser.objects.create_user(username='ref1', email='ref1@test.local', password='x')
        u2 = CustomUser.objects.create_user(username='ref2', email='ref2@test.local', password='x')
        code = referral_code(u1)
        self.assertEqual(code, referral_code(u1))
        self.assertNotEqual(code, referral_code(u2))
        self.assertEqual(normalize_value(code), code)
