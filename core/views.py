
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
from properties.models import Property
from bookings.models import Booking
from hosts.models import Host
from django.db.models import Avg, Count
from datetime import timedelta
from django.utils import timezone

# This is the view function for the hosts page.
# It handles the HTTP request and renders the hosts.html template.
def hosts_view(request):
    """Enhanced hosts page with real data"""
    superhosts_count = Host.objects.filter(is_superhost=True).count()
    total_hosts = Host.objects.count()
    avg_host_rating = Host.objects.aggregate(avg_rating=Avg('average_rating'))['avg_rating'] or 0
    
    context = {
        'superhosts_count': superhosts_count,
        'total_hosts': total_hosts,
        'avg_host_rating': round(avg_host_rating, 1),
    }
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
    property_type_query = request.GET.get('property-type')
    guests_query = request.GET.get('guests')

    # Apply filters if they exist
    if location_query:
        # Filter Propertys where the city contains the search query (case-insensitive)
        filtered_properties = filtered_properties.filter(city__icontains=location_query)

    if property_type_query and property_type_query != 'All Types':
        # Filter Propertys by the selected property type
        filtered_properties = filtered_properties.filter(property_type=property_type_query)

    if guests_query and guests_query != 'All Guests':
        # Convert guest query to an integer for filtering
        if guests_query == '4+ Guests':
            # Filter for Propertys with 4 or more beds
            filtered_properties = filtered_properties.filter(beds__gte=4)
        else:
            # Filter for Propertys with an exact number of beds
            num_guests = int(guests_query.split(' ')[0])
            filtered_properties = filtered_properties.filter(beds=num_guests)

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
        # Prepare data for JSON response
        properties_json = [{
            'id': p.id,
            'title': p.name,
            'location': p.city,
            'type': p.property_type,
            'price_per_night': p.price,
            'beds': p.beds,
            'baths': p.baths,
            'sqft': p.sqft,
            # Placeholder for image_url, you would add this to your model
            'image_url': f"https://placehold.co/600x400/E5E7EB/4B5563?text=Property+{p.id}"
        } for p in page_obj.object_list]
        
        data = {
            'properties': properties_json,
            'page': page_obj.number,
            'total_pages': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'location': location_query,
            'property_type': property_type_query,
            'guests': guests_query,
        }
        return JsonResponse(data)
    
    # For a normal page load, render the full template
    context = {
        'properties': page_obj,
        'page': page_obj.number,
        'total_pages': range(1, paginator.num_pages + 1),
        'location': location_query,
        'property_type': property_type_query,
        'guests': guests_query,
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
    ).order_by('-avg_rating')[:6]
    
    # Most booked properties
    most_booked_properties = Property.objects.filter(
        is_active=True
    ).annotate(
        booking_count=Count('bookings')
    ).order_by('-booking_count')[:6]
    
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
    ).distinct().order_by('-bookings__created_at')[:6]
    
    # Properties with special offers (you can add a discount field later)
    special_offer_properties = Property.objects.filter(
        is_active=True
    ).order_by('?')[:4]  # Random selection for now
    
    # Statistics for the stats section
    stats = {
        'active_properties': Property.objects.filter(is_active=True).count(),
        'happy_guests': Booking.objects.filter(status='completed').count(),
        'superhosts_count': Host.objects.filter(is_superhost=True).count(),
        'countries': Property.objects.values('country').distinct().count(),
    }
    
    # Testimonials (you can create a Testimonial model later)
    testimonials = [
        {
            'name': 'Sarah Johnson',
            'location': 'New York, USA',
            'text': 'This platform made managing my vacation rental so much easier!',
            'rating': 5,
            'image_url': 'https://images.unsplash.com/photo-1494790108755-2616b612b786?w=150'
        },
        {
            'name': 'Mike Chen',
            'location': 'Toronto, Canada', 
            'text': 'As a host, the tools provided are incredible. Highly recommended!',
            'rating': 5,
            'image_url': 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=150'
        },
        {
            'name': 'Emma Davis',
            'location': 'London, UK',
            'text': 'Found the perfect apartment for my family vacation. Amazing experience!',
            'rating': 5,
            'image_url': 'https://images.unsplash.com/photo-1438761681033-6461ffad8d80?w=150'
        }
    ]
    
    context = {
        'top_rated_properties': top_rated_properties,
        'most_booked_properties': most_booked_properties,
        'superhosts': superhosts,
        'recently_booked_properties': recently_booked_properties,
        'special_offer_properties': special_offer_properties,
        'stats': stats,
        'testimonials': testimonials,
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
