# products/templatetags/product_extras.py
from django import template
import jdatetime

register = template.Library()

@register.filter
def format_price(value):
    """تبدیل عدد به فرمت سه رقم سه رقم"""
    if value is None or value == '':
        return "0"
    try:
        if isinstance(value, str):
            value = value.replace(',', '')
        num = int(float(value))
        return f"{num:,}"
    except (ValueError, TypeError):
        return str(value)

@register.filter
def discount_percent(product):
    """محاسبه درصد تخفیف"""
    if hasattr(product, 'price') and product.price and product.off_price:
        try:
            price = float(product.price) if not isinstance(product.price, float) else product.price
            off_price = float(product.off_price) if not isinstance(product.off_price, float) else product.off_price
            if price > 0:
                return int((1 - off_price / price) * 100)
        except:
            pass
    return 0

@register.filter
def multiply(value, arg):
    """ضرب دو عدد"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

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
        return jalali_date.strftime('%Y/%m/%d - %H:%M')
    except:
        return str(datetime_obj)