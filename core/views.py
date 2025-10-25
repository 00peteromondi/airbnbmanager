
from django.shortcuts import render
from django.db.models import Q # Used for complex queries

# In a real application, you would import your Property model here
# from .models import Property

from django.shortcuts import render
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from django.shortcuts import render

# This is the view function for the hosts page.
# It handles the HTTP request and renders the hosts.html template.
def hosts_view(request):
    """
    Renders the hosts.html template.
    
    Args:
        request: The HTTP request object.
    
    Returns:
        An HttpResponse object containing the rendered hosts.html template.
    """
    # A context dictionary can be passed to the template.
    # We'll keep it empty for now, but you can add data here
    # to be displayed on the page.
    context = {}
    return render(request, 'core/hosts.html', context)

# Placeholder views for the other URLs in the template.
# You will need to replace these with your actual logic.
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
from hosts.models import Listing  # Import the Listing model from your host app

def properties_list(request):
    """
    View to list properties and handle search/filtering.
    It responds with JSON for AJAX requests and renders a full template otherwise.
    """
    # Start with all active listings
    filtered_properties = Listing.objects.filter(status='Active').order_by('id')

    # Get filter parameters from the request
    location_query = request.GET.get('location')
    property_type_query = request.GET.get('property-type')
    guests_query = request.GET.get('guests')

    # Apply filters if they exist
    if location_query:
        # Filter listings where the city contains the search query (case-insensitive)
        filtered_properties = filtered_properties.filter(city__icontains=location_query)

    if property_type_query and property_type_query != 'All Types':
        # Filter listings by the selected property type
        filtered_properties = filtered_properties.filter(property_type=property_type_query)

    if guests_query and guests_query != 'All Guests':
        # Convert guest query to an integer for filtering
        if guests_query == '4+ Guests':
            # Filter for listings with 4 or more beds
            filtered_properties = filtered_properties.filter(beds__gte=4)
        else:
            # Filter for listings with an exact number of beds
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
    return render(request, 'core/home.html')

