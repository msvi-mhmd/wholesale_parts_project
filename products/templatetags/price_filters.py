# products/templatetags/price_filters.py
from django import template

register = template.Library()

@register.filter
def format_price(value):
    if not value:
        return '0'
    try:
        return f"{int(value):,}"
    except:
        return str(value)

@register.filter
def multiply(value, arg):
    """ضرب دو عدد"""
    try:
        return value * arg
    except:
        return 0