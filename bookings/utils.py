# bookings/utils.py
from datetime import datetime, timedelta
from django.db.models import Q
from properties.models import Property
from bookings.models import Booking

def check_property_availability(property, check_in, check_out):
    """
    Check if a property is available for the given dates
    """
    conflicting_bookings = Booking.objects.filter(
        property=property,
        check_in_date__lt=check_out,
        check_out_date__gt=check_in,
        status__in=['confirmed', 'checked_in', 'pending']
    )
    return not conflicting_bookings.exists()

def get_available_properties(check_in, check_out, guests=1, location=None):
    """
    Get all available properties for given criteria
    """
    properties = Property.objects.filter(
        is_active=True,
        max_guests__gte=guests
    )
    
    if location:
        properties = properties.filter(
            Q(city__icontains=location) | 
            Q(state__icontains=location) |
            Q(country__icontains=location)
        )
    
    available_properties = []
    for property in properties:
        if check_property_availability(property, check_in, check_out):
            available_properties.append(property)
    
    return available_properties