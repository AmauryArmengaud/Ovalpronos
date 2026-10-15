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
