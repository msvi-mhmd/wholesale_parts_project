# products/templatetags/date_filters.py
from django import template
import jdatetime

register = template.Library()

@register.filter
def to_jalali(date):
    """تبدیل تاریخ میلادی به شمسی"""
    if not date:
        return ''
    try:
        jalali_date = jdatetime.date.fromgregorian(date=date)
        return jalali_date.strftime('%Y/%m/%d')
    except:
        return str(date)

@register.filter
def to_jalali_datetime(datetime_obj):
    """تبدیل datetime میلادی به شمسی با زمان"""
    if not datetime_obj:
        return ''
    try:
        jalali_date = jdatetime.datetime.fromgregorian(datetime=datetime_obj)
        return jalali_date.strftime('%Y/%m/%d %H:%M')
    except:
        return str(datetime_obj)

@register.filter
def to_jalali_short(date):
    """تبدیل تاریخ میلادی به شمسی با فرمت کوتاه"""
    if not date:
        return ''
    try:
        jalali_date = jdatetime.date.fromgregorian(date=date)
        return jalali_date.strftime('%d %B %Y')
    except:
        return str(date)