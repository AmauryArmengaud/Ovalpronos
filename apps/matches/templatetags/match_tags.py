from django import template

register = template.Library()


@register.filter
def format_cote(value):
    """Display a cote integer as-is: 63 → '63'."""
    if value is None:
        return "–"
    return str(value)
