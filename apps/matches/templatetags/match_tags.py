from django import template
from django.utils.translation import gettext_lazy as _

register = template.Library()

# Known non-numeric round labels from api-sports.io.
# Add entries here when the API introduces new round names — makemessages will
# extract the _() calls automatically so the PO file stays in sync.
ROUND_LABELS = {
    'Final':          _('Final'),
    'Semi-finals':    _('Semi-finals'),
    'Quarter-finals': _('Quarter-finals'),
    'Semi Finals':    _('Semi Finals'),
    'Quarter Finals': _('Quarter Finals'),
}


# World Rugby 3-letter codes for national teams. The API sync leaves their
# short_name empty, so the landing derives the code from the team name.
NATION_CODES = {
    'argentina': 'ARG', 'argentine': 'ARG',
    'australia': 'AUS', 'australie': 'AUS',
    'england': 'ENG', 'angleterre': 'ENG',
    'fiji': 'FIJ', 'fidji': 'FIJ',
    'france': 'FRA',
    'georgia': 'GEO', 'georgie': 'GEO',
    'ireland': 'IRL', 'irlande': 'IRL',
    'italy': 'ITA', 'italie': 'ITA',
    'japan': 'JPN', 'japon': 'JPN',
    'new-zealand': 'NZL', 'nouvelle-zelande': 'NZL',
    'portugal': 'POR',
    'samoa': 'SAM',
    'scotland': 'SCO', 'ecosse': 'SCO',
    'south-africa': 'RSA', 'afrique-du-sud': 'RSA',
    'spain': 'ESP', 'espagne': 'ESP',
    'tonga': 'TGA',
    'uruguay': 'URU',
    'usa': 'USA', 'united-states': 'USA',
    'wales': 'WAL', 'pays-de-galles': 'WAL',
}


@register.filter
def team_code(team):
    """Short code for tight layouts: short_name, else nation code, else 3 first letters."""
    from django.utils.text import slugify
    if team.short_name:
        return team.short_name
    key = slugify(team.name)
    return NATION_CODES.get(key) or key.replace('-', '')[:3].upper()


@register.filter
def format_cote(value):
    """Display a cote integer as-is: 63 → '63'."""
    if value is None:
        return "–"
    return str(value)


@register.filter
def is_numeric(value):
    """True if value is a non-empty string of digits (round number from API)."""
    if not value:
        return False
    return str(value).isdigit()


@register.filter
def round_label(value):
    """Translate a known non-numeric round string; falls back to the raw value."""
    if not value:
        return value
    return ROUND_LABELS.get(value, value)


@register.filter
def team_logo_url(team):
    """Uploaded logo, else the team's boar PNG from static, else '' so the caller shows initials"""
    from django.contrib.staticfiles import finders
    from django.templatetags.static import static
    if team.logo:
        return team.logo.url
    path = f'img/teams/{team.slug}.png'
    return static(path) if team.slug and finders.find(path) else ''
