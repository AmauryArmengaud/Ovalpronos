from django import template
from django.utils.translation import get_language

register = template.Library()


@register.filter
def ordinal_local(value):
    """Locale-aware ordinal: '1er'/'2e' (fr) or '1st'/'2nd' (en)."""
    n = int(value)
    if (get_language() or '').startswith('fr'):
        return f"{n}er" if n == 1 else f"{n}e"
    if 11 <= (n % 100) <= 13:
        suffix = 'th'
    else:
        suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')
    return f"{n}{suffix}"
