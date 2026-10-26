"""Sign-up attribution without cookies.

Campaign parameters travel in the URL from the first page a visitor lands on to
the register form (every register/login link rebuilds them with the
`auth_url` template tag), then are stored on the account.
"""
import re
import unicodedata
from urllib.parse import urlencode, urlparse

UTM_KEYS = ('utm_source', 'utm_medium', 'utm_campaign', 'utm_content')
# ref: source derived from an external Referer; landing: first known page of the visit
CARRIED_KEYS = UTM_KEYS + ('ref', 'landing')

VALUE_MAX_LENGTH = 50
PATH_MAX_LENGTH = 200

REFERER_SOURCES = {
    'linkedin.com': 'linkedin',
    'lnkd.in': 'linkedin',
    'whatsapp.com': 'whatsapp',
    'wa.me': 'whatsapp',
    'facebook.com': 'facebook',
    'fb.com': 'facebook',
    'instagram.com': 'instagram',
    'x.com': 'twitter',
    'twitter.com': 'twitter',
    't.co': 'twitter',
}


def normalize_value(value):
    """'  WhatsApp Groupe-1 ' -> 'whatsapp_groupe-1'; anything outside [a-z0-9_-] is dropped"""
    value = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode()
    value = re.sub(r'\s+', '_', value.strip().lower())
    return re.sub(r'[^a-z0-9_-]', '', value)[:VALUE_MAX_LENGTH]


def normalize_path(value):
    path = urlparse(str(value)).path
    # a protocol-relative '//evil.com' would read as a host, not a page
    if not path.startswith('/') or path.startswith('//'):
        return ''
    return re.sub(r'[^a-z0-9/_.-]', '', path.lower())[:PATH_MAX_LENGTH]


def referer_source(referer, own_host):
    """Source name for a known external Referer, '' for an internal, unknown or missing one"""
    host = (urlparse(referer or '').hostname or '').lower()
    if not host or host == own_host.split(':')[0].lower():
        return ''
    labels = host.split('.')
    for i in range(len(labels) - 1):
        source = REFERER_SOURCES.get('.'.join(labels[i:]))
        if source:
            return source
    # google.fr, google.co.uk, www.google.com...
    if 'google' in labels[:-1]:
        return 'google'
    return ''


def clean_params(data):
    """Normalized carried parameters from a GET or POST QueryDict, empty values dropped"""
    params = {}
    for key in CARRIED_KEYS:
        raw = data.get(key)
        if raw:
            value = normalize_path(raw) if key == 'landing' else normalize_value(raw)
            if value:
                params[key] = value
    return params


def carried_params(request):
    """Parameters every register/login link on this page must carry.

    Values already in the URL win: they come from the page the visitor first
    landed on. Otherwise this page is that first page, and its Referer is read.
    """
    params = clean_params(request.GET)
    params.setdefault('landing', normalize_path(request.path))
    if not any(key in params for key in UTM_KEYS + ('ref',)):
        ref = referer_source(request.META.get('HTTP_REFERER'), request.get_host())
        if ref:
            params['ref'] = ref
    return params


def visit_source(request):
    """Source of this page view with the sign-up priority, minus invitations: utm_source > known Referer > direct"""
    params = carried_params(request)
    return params.get('utm_source') or params.get('ref') or 'direct'


def carried_querystring(request, next_url=None):
    params = carried_params(request)
    if next_url:
        params = {'next': next_url, **params}
    return urlencode(params)


def resolve_attribution(params, invitation=None, invite_league=None):
    """Account attribution fields from the cleaned parameters of the register form.

    Source priority, first match wins:
      1. explicit utm_source
      2. pre-filled 2023 re-registration link (`invitation`, campaign = cohort)
      3. league invite link (`league_invite`)
      4. known external Referer seen on the first page (`ref`)
      5. `direct`
    utm_medium / utm_campaign / utm_content and the landing path are kept whatever the source.
    """
    if params.get('utm_source'):
        source = params['utm_source']
    elif invitation is not None:
        source = 'invitation'
    elif invite_league is not None:
        source = 'league_invite'
    else:
        source = params.get('ref') or 'direct'
    campaign = params.get('utm_campaign', '')
    if source == 'invitation' and not campaign:
        campaign = normalize_value(invitation.cohort)
    return {
        'signup_source': source,
        'signup_medium': params.get('utm_medium', ''),
        'signup_campaign': campaign,
        'signup_content': params.get('utm_content', ''),
        'signup_landing_path': params.get('landing', ''),
    }


def referral_code(user):
    """Stable, non-reversible tag for a referrer, carried as utm_content on their share links"""
    from django.utils.crypto import salted_hmac
    return salted_hmac('ovalpronos.referral', str(user.pk)).hexdigest()[:12]


def referral_url(request, user, competition):
    from django.urls import reverse
    path = reverse('matches:competition_landing', kwargs={'code': competition.code.lower()})
    query = urlencode({
        'utm_source': 'referral',
        'utm_medium': 'share',
        'utm_campaign': normalize_value(competition.code),
        'utm_content': referral_code(user),
    })
    return request.build_absolute_uri(f'{path}?{query}')
