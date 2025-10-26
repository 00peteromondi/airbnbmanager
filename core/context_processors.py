from properties.models import Property
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import timedelta

def global_data(request):
    """Global context data available to all templates"""
    
    # Featured properties (most booked, highest rated)
    featured_properties = Property.objects.filter(
        is_active=True
    ).annotate(
        avg_rating=Avg('reviews__rating'),
        booking_count=Count('bookings')
    ).filter(
        Q(avg_rating__gte=4.5) | Q(booking_count__gte=5)
    ).order_by('-avg_rating', '-booking_count')[:8]
    
    # Recently added properties
    recent_properties = Property.objects.filter(
        is_active=True
    ).order_by('-created_at')[:6]
    
    # Popular destinations (cities with most properties)
    popular_destinations = Property.objects.filter(
        is_active=True
    ).values('city', 'country').annotate(
        property_count=Count('id')
    ).order_by('-property_count')[:6]
    
    # Statistics for homepage
    total_properties = Property.objects.filter(is_active=True).count()
    total_bookings = Property.objects.aggregate(
        total_bookings=Count('bookings')
    )['total_bookings'] or 0
    
    # Properties by type for filtering
    property_types = Property.PROPERTY_TYPES
    
    return {
        'featured_properties': featured_properties,
        'recent_properties': recent_properties,
        'popular_destinations': popular_destinations,
        'total_properties': total_properties,
        'total_bookings': total_bookings,
        'property_types': property_types,
    }

def active_role(request):
    """
    Add active_role to template context for users with both roles
    """
    context = {}
    if request.user.is_authenticated and request.user.role == 'both':
        context['active_role'] = request.session.get('active_role', 'guest')
    return context