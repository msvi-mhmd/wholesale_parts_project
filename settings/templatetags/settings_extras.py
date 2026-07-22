from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """دریافت مقدار از دیکشنری با کلید"""
    if dictionary is None:
        return ''
    return dictionary.get(key, '')