from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import CustomUserCreationForm
from django.http import JsonResponse

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {'form': form})

def profile(request):
    return render(request, 'users/profile.html')

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