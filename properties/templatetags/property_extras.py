from django import template
from properties.views import AMENITY_ICONS
from properties.models import Property
import random

register = template.Library()


@register.filter
def amenity_icon(value):
    return AMENITY_ICONS.get(value, "fa-solid fa-circle-check")


@register.filter
def amenity_label(value):
    return dict(Property.AMENITY_CHOICES).get(value, str(value).replace("_", " ").title())


@register.filter
def random_amenities(amenities_list, count=3):
    """
    Returns a list of random amenities from the given list.
    Usage: {{ property.amenities|random_amenities:3 }}
    """
    if not amenities_list:
        return []
    
    count = int(count) if count else 3
    if len(amenities_list) <= count:
        return amenities_list
    
    return random.sample(amenities_list, min(count, len(amenities_list)))


@register.filter
def remaining_amenities_count(amenities_list, displayed_count=3):
    """
    Returns the count of remaining amenities.
    Usage: {{ property.amenities|remaining_amenities_count:3 }}
    """
    displayed_count = int(displayed_count) if displayed_count else 3
    remaining = len(amenities_list) - displayed_count
    return max(0, remaining)


@register.filter
def get_amenity_display(amenities_list):
    """
    Returns a formatted display of amenities with count.
    Usage: {{ property.amenities|get_amenity_display }}
    """
    if not amenities_list:
        return {}
    
    selected = random.sample(amenities_list, min(9, len(amenities_list)))
    remaining = len(amenities_list) - 9
    
    return {
        'selected': selected,
        'remaining_count': max(0, remaining)
    }
