from django import template
from django.utils import timezone

from core.utils import next_annual_date

register = template.Library()


@register.filter
def date_ru(value):
    if not value:
        return ""
    return value.strftime("%d/%m/%Y")


@register.filter
def date_ru_short(value):
    if not value:
        return ""
    return value.strftime("%d/%m")


@register.filter
def age_years(birth_date):
    if not birth_date:
        return ""
    today = timezone.localdate()
    years = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        years -= 1
    return years


@register.filter
def next_birthday(birth_date):
    if not birth_date:
        return ""
    return next_annual_date(birth_date.month, birth_date.day, timezone.localdate())


@register.filter
def get_item(mapping, key):
    if mapping is None:
        return None
    return mapping.get(key)
