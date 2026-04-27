
from django.shortcuts import render
from django.db.models import Q # Used for complex queries

# In a real application, you would import your Property model here
# from .models import Property

from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
import decimal
from datetime import datetime
from properties.models import Property, Review
from bookings.models import Booking
from hosts.models import Host
from django.db.models import Avg, Count, Max
from datetime import timedelta
from django.utils import timezone
from django.template.loader import render_to_string
from decimal import Decimal, InvalidOperation

# This is the view function for the hosts page.
# It handles the HTTP request and renders the hosts.html template.
def hosts_view(request):
    """Enhanced hosts page with real data"""
    superhosts_count = Host.objects.filter(is_superhost=True).count()
    total_hosts = Host.objects.count()
    avg_host_rating = Review.objects.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0
    host_review_highlights = list(
        Review.objects.select_related('property', 'property__owner', 'user')
        .exclude(comment__exact='')
        .exclude(property__owner__first_name__exact='')
        .order_by('-created_at')[:4]
    )
    host_ready_count = Host.objects.filter(
        fully_verified=True,
        user__properties__is_active=True,
    ).distinct().count()
    
    context = {
        'superhosts_count': superhosts_count,
        'total_hosts': total_hosts,
        'avg_host_rating': round(avg_host_rating, 1),
        'host_review_highlights': host_review_highlights,
        'host_ready_count': host_ready_count,
    }

    if request.user.is_authenticated and request.user.role in ['host', 'both']:
        host_property_count = Property.objects.filter(owner=request.user).count()
        active_property_count = Property.objects.filter(owner=request.user, is_active=True).count()
        host_profile = Host.objects.filter(user=request.user).first()
        context.update({
            'is_host_user': True,
            'host_property_count': host_property_count,
            'host_active_property_count': active_property_count,
            'host_profile': host_profile,
        })

    return render(request, 'core/hosts.html', context)

def start_hosting_view(request):
    """
    Placeholder for the 'start hosting' page view.
    """
    return render(request, 'core/start_hosting.html', {})

def become_a_host_now_view(request):
    """
    Placeholder for the 'become a host now' page view.
    """
    return render(request, 'core/become_a_host.html', {})

from django.shortcuts import render
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from properties.models import Property  # Import the Property model from your host app

def properties_list(request):
    """
    View to list properties and handle search/filtering.
    It responds with JSON for AJAX requests and renders a full template otherwise.
    """
    # Start with all active Propertys
    filtered_properties = Property.objects.filter(is_active=True).order_by('id')

    # Get filter parameters from the request
    location_query = request.GET.get('location')
    location_lat = request.GET.get('location_lat')
    location_lng = request.GET.get('location_lng')
    property_type_query = request.GET.get('property-type')
    guests_query = request.GET.get('guests')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    check_in = request.GET.get('check_in')
    check_out = request.GET.get('check_out')
    sort_by = request.GET.get('sort', 'recommended')

    # Apply filters if they exist
    if location_query:
        geo_filtered = None
        if location_lat and location_lng:
            try:
                lat = Decimal(location_lat)
                lng = Decimal(location_lng)
                delta = Decimal('0.45')
                geo_filtered = filtered_properties.filter(
                    latitude__isnull=False,
                    longitude__isnull=False,
                    latitude__gte=lat - delta,
                    latitude__lte=lat + delta,
                    longitude__gte=lng - delta,
                    longitude__lte=lng + delta,
                )
            except (InvalidOperation, TypeError):
                geo_filtered = None

        if geo_filtered is not None and geo_filtered.exists():
            filtered_properties = geo_filtered
        else:
            filtered_properties = filtered_properties.filter(
                Q(city__icontains=location_query) |
                Q(state__icontains=location_query) |
                Q(country__icontains=location_query) |
                Q(address__icontains=location_query) |
                Q(name__icontains=location_query)
            )

    if property_type_query and property_type_query != 'All Types':
        filtered_properties = filtered_properties.filter(property_type=property_type_query)

    if guests_query and guests_query != 'All Guests':
        try:
            if guests_query == '4+ Guests':
                filtered_properties = filtered_properties.filter(max_guests__gte=4)
            else:
                filtered_properties = filtered_properties.filter(max_guests__gte=int(str(guests_query).split(' ')[0]))
        except (ValueError, TypeError):
            pass

    if min_price:
        try:
            filtered_properties = filtered_properties.filter(price_per_night__gte=Decimal(min_price))
        except (InvalidOperation, TypeError):
            pass

    if max_price:
        try:
            filtered_properties = filtered_properties.filter(price_per_night__lte=Decimal(max_price))
        except (InvalidOperation, TypeError):
            pass

    if check_in and check_out:
        try:
            check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
            check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
            booked_properties = Booking.objects.filter(
                check_in_date__lt=check_out_date,
                check_out_date__gt=check_in_date,
                status__in=['confirmed', 'pending', 'checked_in']
            ).values_list('property_id', flat=True)
            filtered_properties = filtered_properties.exclude(id__in=booked_properties)
        except ValueError:
            pass

    filtered_properties = filtered_properties.annotate(
        review_count=Count('reviews')
    )

    if sort_by == 'price_asc':
        filtered_properties = filtered_properties.order_by('price_per_night', '-average_rating')
    elif sort_by == 'price_desc':
        filtered_properties = filtered_properties.order_by('-price_per_night', '-average_rating')
    elif sort_by == 'top_rated':
        filtered_properties = filtered_properties.order_by('-average_rating', '-review_count', '-id')
    elif sort_by == 'most_guests':
        filtered_properties = filtered_properties.order_by('-max_guests', '-average_rating')
    else:
        filtered_properties = filtered_properties.order_by('-average_rating', 'price_per_night', '-id')

    destination = (
        filtered_properties.exclude(city__exact='')
        .values('city')
        .annotate(total=Count('id'))
        .order_by('-total', 'city')
        .first()
    )
    summary = filtered_properties.aggregate(
        avg_price=Avg('price_per_night'),
        avg_rating=Avg('average_rating'),
        total_results=Count('id'),
        latest_update=Max('updated_at'),
    )
    live_version = f"{summary['total_results'] or 0}:{summary['latest_update'].isoformat() if summary['latest_update'] else 'none'}"
    user_booked_property_ids = []
    if request.user.is_authenticated and request.user.role in ['guest', 'both']:
        user_booked_property_ids = list(
            Booking.objects.filter(guest=request.user)
            .exclude(status='cancelled')
            .values_list('property_id', flat=True)
            .distinct()
        )

    # Set up pagination
    paginator = Paginator(filtered_properties, 6) # Show 6 properties per page
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Check if the request is an AJAX request
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        results_html = render_to_string(
            'core/_property_results.html',
            {
                'properties': page_obj.object_list,
                'user': request.user,
                'user_booked_property_ids': user_booked_property_ids,
            },
            request=request,
        )
        data = {
            'html': results_html,
            'version': live_version,
            'page': page_obj.number,
            'total_pages': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'location': location_query,
            'property_type': property_type_query,
            'guests': guests_query,
            'results_count': summary['total_results'] or 0,
            'avg_price': summary['avg_price'] or 0,
            'avg_rating': summary['avg_rating'] or 0,
            'top_destination': destination['city'] if destination else '',
        }
        return JsonResponse(data)
    
    # For a normal page load, render the full template
    context = {
        'properties': page_obj,
        'page': page_obj.number,
        'total_pages': range(1, paginator.num_pages + 1),
        'location': location_query,
        'location_lat': location_lat,
        'location_lng': location_lng,
        'property_type': property_type_query,
        'guests': guests_query,
        'min_price': min_price,
        'max_price': max_price,
        'check_in': check_in,
        'check_out': check_out,
        'sort': sort_by,
        'results_count': summary['total_results'] or 0,
        'avg_price': summary['avg_price'] or 0,
        'avg_rating': summary['avg_rating'] or 0,
        'top_destination': destination['city'] if destination else '',
        'user_booked_property_ids': user_booked_property_ids,
        'live_version': live_version,
    }
    return render(request, 'core/properties.html', context)



def home(request):
    """Data-driven home page with dynamic content"""
    
    # Top-rated properties (minimum 3 reviews, rating >= 4.5)
    top_rated_properties = Property.objects.filter(
        is_active=True
    ).annotate(
        avg_rating=Avg('reviews__rating'),
        review_count=Count('reviews')
    ).filter(
        avg_rating__gte=4.5,
        review_count__gte=3
    ).order_by('-avg_rating', '-review_count')[:6]
    
    # Most booked properties
    most_booked_properties = Property.objects.filter(
        is_active=True
    ).annotate(
        booking_count=Count('bookings'),
        avg_rating=Avg('reviews__rating')
    ).order_by('-booking_count', '-avg_rating')[:6]
    
    # Superhosts with their properties
    superhosts = Host.objects.filter(
        is_superhost=True,
        user__is_active=True
    ).select_related('user')[:4]
    
    # Recently booked properties (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recently_booked_properties = Property.objects.filter(
        bookings__created_at__gte=thirty_days_ago,
        is_active=True
    ).distinct().annotate(avg_rating=Avg('reviews__rating')).order_by('-bookings__created_at')[:6]
    
    # Properties with special offers (you can add a discount field later)
    special_offer_properties = Property.objects.filter(
        is_active=True
    ).annotate(avg_rating=Avg('reviews__rating')).order_by('?')[:4]  # Random selection for now

    # Popular destinations (by number of active properties)
    popular_destinations = Property.objects.filter(
        is_active=True
    ).exclude(city__exact='').values('city', 'country').annotate(total=Count('id')).order_by('-total')[:6]
    
    # Statistics for the stats section
    stats = {
        'active_properties': Property.objects.filter(is_active=True).count(),
        'happy_guests': Booking.objects.filter(status='completed').count(),
        'superhosts_count': Host.objects.filter(is_superhost=True).count(),
        'countries': Property.objects.values('country').distinct().count(),
    }
    
    testimonials = list(
        Review.objects.select_related('user', 'property')
        .exclude(comment__exact='')
        .order_by('-created_at')[:3]
    )

    user_booked_property_ids = []
    active_guest_bookings = []
    if request.user.is_authenticated and request.user.role in ['guest', 'both']:
        active_guest_bookings = list(
            Booking.objects.filter(guest=request.user)
            .exclude(status='cancelled')
            .select_related('property')
            .order_by('-created_at')[:3]
        )
        user_booked_property_ids = [booking.property_id for booking in active_guest_bookings]

    context = {
        'top_rated_properties': top_rated_properties,
        'most_booked_properties': most_booked_properties,
        'superhosts': superhosts,
        'recently_booked_properties': recently_booked_properties,
        'special_offer_properties': special_offer_properties,
        'popular_destinations': popular_destinations,
        'stats': stats,
        'testimonials': testimonials,
        'active_guest_bookings': active_guest_bookings,
        'user_booked_property_ids': user_booked_property_ids,
    }
    
    return render(request, 'core/home.html', context)

# core/views.py - Enhanced search
def property_search(request):
    properties = Property.objects.filter(is_active=True)
    
    # Get search parameters
    location = request.GET.get('location', '')
    check_in = request.GET.get('check_in', '')
    check_out = request.GET.get('check_out', '')
    guests = request.GET.get('guests', '')
    property_type = request.GET.get('property_type', '')
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    amenities = request.GET.getlist('amenities')
    
    # Apply filters
    if location:
        properties = properties.filter(
            Q(city__icontains=location) |
            Q(state__icontains=location) |
            Q(country__icontains=location)
        )
    
    if property_type:
        properties = properties.filter(property_type=property_type)
    
    if guests:
        properties = properties.filter(max_guests__gte=int(guests))
    
    if min_price:
        properties = properties.filter(price_per_night__gte=decimal.Decimal(min_price))
    
    if max_price:
        properties = properties.filter(price_per_night__lte=decimal.Decimal(max_price))
    
    if amenities:
        properties = properties.filter(amenities__contains=amenities)
    
    # Date availability filtering
    if check_in and check_out:
        try:
            check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
            check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()
            
            # Get properties with no conflicting bookings
            booked_properties = Booking.objects.filter(
                check_in_date__lt=check_out_date,
                check_out_date__gt=check_in_date,
                status__in=['confirmed', 'checked_in']
            ).values_list('property_id', flat=True)
            
            properties = properties.exclude(id__in=booked_properties)
        except ValueError:
            pass
    
    # Pagination
    paginator = Paginator(properties, 12)
    page = request.GET.get('page')
    
    try:
        properties_page = paginator.page(page)
    except PageNotAnInteger:
        properties_page = paginator.page(1)
    except EmptyPage:
        properties_page = paginator.page(paginator.num_pages)
    
    context = {
        'properties': properties_page,
        'search_params': request.GET,
        'property_types': dict(Property.PROPERTY_TYPES),
        'amenity_choices': Property.AMENITY_CHOICES,
    }
    
    return render(request, 'core/property_search.html', context)
