from django import template
from properties.views import AMENITY_ICONS
from properties.models import Property

register = template.Library()


@register.filter
def amenity_icon(value):
    return AMENITY_ICONS.get(value, "fa-solid fa-circle-check")


@register.filter
def amenity_label(value):
    return dict(Property.AMENITY_CHOICES).get(value, str(value).replace("_", " ").title())
