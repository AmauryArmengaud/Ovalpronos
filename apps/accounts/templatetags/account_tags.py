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


@register.simple_tag(takes_context=True)
def auth_url(context, view_name, next=''):
    """Register/login URL carrying the visit's campaign parameters, so attribution survives any entry point"""
    from django.urls import reverse
    from apps.accounts.signup_source import carried_querystring
    return f"{reverse(view_name)}?{carried_querystring(context['request'], next)}"
