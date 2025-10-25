from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from .forms import GuestSignUpForm
from hosts.models import Listing
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

CustomUser = get_user_model()

# This view handles the guest registration.
def guest_signup_view(request):
    if request.method == 'POST':
        form = GuestSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Your account has been created.")
            return redirect('guests:guest_dashboard')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = GuestSignUpForm()
    
    return render(request, 'guests/guest_signup.html', {'form': form})

# This view handles the guest login process.
def guest_login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                return redirect('guests:guest_dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    
    form = AuthenticationForm()
    return render(request, 'guests/guest_login.html', {'form': form})

# This view logs out the user and redirects to the homepage.
def guest_logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('core:home')

# This is a protected view for the guest's dashboard.
@login_required(login_url='guests:guest_login')
def guest_dashboard_view(request):
    return render(request, 'guests/guest_dashboard.html')

@login_required(login_url='guests:guest_login')
def guest_properties_view(request):
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
    return render(request, 'guests/properties.html', context)
