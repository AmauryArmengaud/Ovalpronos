from django import template

register = template.Library()


@register.filter
def format_cote(value):
    """Format a raw cote integer (×10) as a decimal string: 125 → '1.25'."""
    if value is None:
        return "–"
    return f"{value / 10:.2f}"
