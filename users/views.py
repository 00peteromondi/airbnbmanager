from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import CustomUserCreationForm, ProfileDetailsForm, ProfilePreferencesForm
from django.http import JsonResponse
from bookings.models import Booking
from properties.models import Property
from hosts.models import Host
from django.db.models import Sum, Avg

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('core:home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {'form': form})

def profile(request):
    if not request.user.is_authenticated:
        return redirect('guests:guest_login')

    profile_obj = request.user.profile
    if request.method == 'POST':
        form_scope = request.POST.get('form_scope')
        if form_scope == 'preferences':
            details_form = ProfileDetailsForm(instance=request.user)
            preferences_form = ProfilePreferencesForm(request.POST, instance=profile_obj)
            if preferences_form.is_valid():
                preferences_form.save()
                from django.contrib import messages
                messages.success(request, "Your BayStays preferences have been updated.")
                return redirect('users:profile')
        else:
            details_form = ProfileDetailsForm(request.POST, request.FILES, instance=request.user)
            preferences_form = ProfilePreferencesForm(instance=profile_obj)
            if details_form.is_valid():
                details_form.save()
                from django.contrib import messages
                messages.success(request, "Your BayStays profile has been updated.")
                return redirect('users:profile')
    else:
        details_form = ProfileDetailsForm(instance=request.user)
        preferences_form = ProfilePreferencesForm(instance=profile_obj)

    guest_bookings = Booking.objects.filter(guest=request.user).exclude(status='cancelled')
    host_properties = Property.objects.filter(owner=request.user)
    host_bookings = Booking.objects.filter(property__owner=request.user)
    host_profile = Host.objects.filter(user=request.user).first()

    context = {
        'details_form': details_form,
        'preferences_form': preferences_form,
        'guest_stats': {
            'total_bookings': guest_bookings.count(),
            'upcoming_trips': guest_bookings.filter(status__in=['pending', 'confirmed']).count(),
            'completed_trips': guest_bookings.filter(status__in=['completed', 'checked_out']).count(),
            'spend': guest_bookings.filter(status__in=['confirmed', 'completed']).aggregate(total=Sum('total_price'))['total'] or 0,
        },
        'host_stats': {
            'total_properties': host_properties.count(),
            'live_properties': host_properties.filter(is_active=True).count(),
            'total_bookings': host_bookings.count(),
            'revenue': host_bookings.filter(status__in=['confirmed', 'completed']).aggregate(total=Sum('total_price'))['total'] or 0,
            'avg_rating': host_properties.aggregate(avg=Avg('average_rating'))['avg'] or 0,
        },
        'host_profile': host_profile,
        'recent_guest_bookings': guest_bookings.select_related('property').order_by('-created_at')[:4],
        'recent_host_bookings': host_bookings.select_related('property', 'guest').order_by('-created_at')[:4],
    }
    return render(request, 'users/profile.html', context)

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import FormView
from .forms import RoleSelectionForm
from .models import CustomUser

@login_required
def role_selection(request):
    """
    View for new users to select their role (Host, Guest, or Both)
    """
    if request.user.role:  # User already has a role
        return redirect(get_redirect_url(request.user))
    
    if request.method == 'POST':
        form = RoleSelectionForm(request.POST, instance=request.user)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Welcome! You're now registered as a {user.get_role_display()}.")
            return redirect(get_redirect_url(user))
    else:
        form = RoleSelectionForm(instance=request.user)
    
    return render(request, 'users/role_selection.html', {'form': form})

def get_redirect_url(user):
    """Determine redirect URL based on user role"""
    if user.role == 'host':
        return 'hosts:dashboard'
    elif user.role == 'both':
        return 'core:home'  # Let them choose from dashboard
    else:  # guest or default
        return 'guests:guest_dashboard'

@login_required
def switch_role(request, role):
    """
    Allow users to switch between host and guest roles if they have 'both' role
    """
    if request.user.role != 'both':
        messages.error(request, "You don't have permission to switch roles.")
        return redirect('core:home')
    
    valid_roles = ['host', 'guest']
    if role not in valid_roles:
        messages.error(request, "Invalid role selection.")
        return redirect('core:home')
    
    # Store the active role in session
    request.session['active_role'] = role
    request.session.modified = True  # Ensure session is saved
    
    messages.success(request, f"🎉 Switched to {role.capitalize()} Mode! You can now access {role}-specific features.")
    
    # Redirect to appropriate dashboard with clear indication
    if role == 'host':
        return redirect('hosts:dashboard')
    else:
        return redirect('guests:guest_dashboard')

@login_required
def get_active_role(request):
    """API endpoint to get current active role (for AJAX calls)"""
    active_role = request.session.get('active_role', 'guest')
    return JsonResponse({'active_role': active_role})
