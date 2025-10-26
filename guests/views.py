from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from .forms import GuestSignUpForm
from django.http import JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from bookings.models import Booking
from django.utils import timezone
from core.mixins import LogoutRequiredMixin
from django.views import View
from properties.models import Property

CustomUser = get_user_model()



class GuestSignUpView(LogoutRequiredMixin, View):
    """Guest registration view - only accessible to logged out users"""
    
    def get(self, request):
        # Double-check middleware didn't let this through
        if request.user.is_authenticated:
            messages.info(request, "You're already logged in!")
            return redirect('guests:guest_dashboard')
            
        form = GuestSignUpForm()
        return render(request, 'guests/guest_signup.html', {'form': form})
    
    def post(self, request):
        # Double-check middleware didn't let this through
        if request.user.is_authenticated:
            messages.info(request, "You're already logged in!")
            return redirect('guests:guest_dashboard')
            
        form = GuestSignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.username}! Your guest account has been created.")
            return redirect('users:role_selection')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
        return render(request, 'guests/guest_signup.html', {'form': form})

class GuestLoginView(LogoutRequiredMixin, View):
    """Guest login view - only accessible to logged out users"""
    
    def get(self, request):
        # Double-check middleware didn't let this through
        if request.user.is_authenticated:
            messages.info(request, "You're already logged in!")
            return redirect('guests:guest_dashboard')
            
        form = AuthenticationForm()
        return render(request, 'guests/guest_login.html', {'form': form})
    
    def post(self, request):
        # Double-check middleware didn't let this through
        if request.user.is_authenticated:
            messages.info(request, "You're already logged in!")
            return redirect('guests:guest_dashboard')
            
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.username}!")
                
                # Redirect based on role
                if not user.role:
                    return redirect('users:role_selection')
                elif user.role in ['guest', 'both']:
                    # Set session for users with both roles
                    if user.role == 'both':
                        request.session['active_role'] = 'guest'
                    return redirect('guests:guest_dashboard')
                else:
                    return redirect('hosts:dashboard')
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
        
        return render(request, 'guests/guest_login.html', {'form': form})

@login_required
def guest_logout_view(request):
    """Guest logout view"""
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('core:home')

@login_required
def guest_dashboard_view(request):
    """Guest dashboard - only accessible to guests"""
    # Additional protection beyond middleware
    if not (request.user.role in ['guest', 'both']):
        messages.error(request, "Access denied. This page is for guests only.")
        return redirect('core:home')
    
    # If user has both roles but is in host mode, redirect
    if (request.user.role == 'both' and 
        request.session.get('active_role') == 'host'):
        messages.info(request, "Please switch to guest mode to access the guest dashboard.")
        return redirect('hosts:dashboard')
    
    return render(request, 'guests/guest_dashboard.html')
@login_required(login_url='guests:guest_login')
def guest_properties_view(request):
    """
    View to list properties and handle search/filtering.
    It responds with JSON for AJAX requests and renders a full template otherwise.
    """
    # Start with all active listings
    filtered_properties = Property.objects.filter(is_active=True).order_by('id')

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
