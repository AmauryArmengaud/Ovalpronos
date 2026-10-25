"""
Walks the whole URL resolver: every route must be either in PUBLIC_VIEWS or
reject anonymous requests (login redirect, 401, 403). Adding an unprotected
view makes this test fail until it is protected or explicitly allowlisted.
"""
import re

from django.test import TestCase, override_settings
from django.urls import URLPattern, URLResolver, get_resolver, resolve

PUBLIC_VIEWS = {
    'matches:home', 'matches:rules', 'matches:competition_landing',
    'matches:legal_notice', 'matches:legal_privacy', 'matches:legal_terms',
    'accounts:register', 'accounts:login', 'accounts:logout',
    'accounts:password_reset', 'accounts:password_reset_done',
    'accounts:password_reset_confirm', 'accounts:password_reset_complete',
    'leagues:public_invite',
    'set_language',
}


def _iter_routes(patterns, prefix='', namespace=None):
    for p in patterns:
        if isinstance(p, URLResolver):
            if str(p.pattern) == 'admin/':
                continue  # every admin view is wrapped by admin_site.admin_view
            ns = p.namespace or namespace
            yield from _iter_routes(p.url_patterns, prefix + str(p.pattern), ns)
        elif isinstance(p, URLPattern):
            name = f'{namespace}:{p.name}' if namespace and p.name else p.name
            yield prefix + str(p.pattern), name, p.callback


def _sample_url(route):
    url = re.sub(r'<int:\w+>', '1', route)
    url = re.sub(r'<(?:str:|slug:)?\w+>', 'X', url)
    return '/' + url


@override_settings(SYNC_SECRET_TOKEN='permission-test-token')
class UrlPermissionTest(TestCase):
    def test_every_route_is_public_by_choice_or_protected(self):
        unprotected = []
        for route, name, callback in _iter_routes(get_resolver().url_patterns):
            if route.startswith('^media/') or name in PUBLIC_VIEWS:
                continue
            url = _sample_url(route)
            if resolve(url).func is not callback:
                continue  # shadowed by an earlier route, unreachable
            for method in ('get', 'post'):
                resp = getattr(self.client, method)(url)
                if resp.status_code in (401, 403, 405):
                    continue
                if resp.status_code == 302 and '/login/' in resp['Location']:
                    continue
                unprotected.append(f'{method.upper()} {url} ({name}) -> {resp.status_code}')
        self.assertEqual(unprotected, [], 'Routes reachable anonymously:\n' + '\n'.join(unprotected))

    def test_api_rejects_wrong_bearer_token(self):
        for url in ('/api/upcoming-matches/', '/api/live-matches/', '/api/has-live-matches/'):
            resp = self.client.get(url, HTTP_AUTHORIZATION='Bearer wrong')
            self.assertEqual(resp.status_code, 401, url)
            self.assertEqual(resp.json(), {'error': 'Unauthorized'})
