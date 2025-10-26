from django.http import HttpResponseForbidden
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from core.mixins import LogoutRequiredMixin, HostRequiredMixin, LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import View, CreateView, UpdateView
from .forms import HostRegistrationForm
from properties.forms import PropertyForm, PropertyImageFormSet
from properties.models import Property, PropertyImage
from bookings.models import Booking
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count
from django.utils import timezone

class HostRegistrationView(LogoutRequiredMixin, View):
    def get(self, request):
        if request.user.is_authenticated:
            messages.info(request, "You're already logged in!")
            return redirect('hosts:dashboard')
        form = HostRegistrationForm()
        return render(request, 'hosts/register.html', {'form': form})
    
    def post(self, request):
        if request.user.is_authenticated:
            messages.info(request, "You're already logged in!")
            return redirect('hosts:dashboard')
        form = HostRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful! Welcome to Aurban.")
            return redirect('users:role_selection')
        messages.error(request, "Registration failed. Invalid information.")
        return render(request, 'hosts/register.html', {'form': form})

@login_required
def logout_host(request):
    logout(request)
    messages.info(request, "Logged out successfully.")
    return redirect('core:home')

@login_required
def dashboard(request):
    if not (request.user.role in ['host', 'both']):
        messages.error(request, "Access denied. This page is for hosts only.")
        return redirect('core:home')
    
    if (request.user.role == 'both' and 
        request.session.get('active_role') == 'guest'):
        messages.info(request, "Please switch to host mode to access the host dashboard.")
        return redirect('guests:guest_dashboard')
    
    properties = Property.objects.filter(owner=request.user).order_by('-created_at')
    
    # Get booking statistics
    bookings = Booking.objects.filter(property__owner=request.user)
    total_bookings = bookings.count()
    pending_bookings = bookings.filter(status='pending').count()
    confirmed_bookings = bookings.filter(status='confirmed').count()
    revenue = bookings.filter(status__in=['confirmed', 'completed']).aggregate(
        total_revenue=Sum('total_price')
    )['total_revenue'] or 0
    
    context = {
        'properties': properties,
        'total_properties': properties.count(),
        'total_bookings': total_bookings,
        'pending_bookings': pending_bookings,
        'confirmed_bookings': confirmed_bookings,
        'revenue': revenue,
    }
    return render(request, 'hosts/dashboard.html', context)

@login_required
def add_listing(request):
    if request.method == 'POST':
        form = PropertyForm(request.POST)
        if form.is_valid():
            property = form.save(commit=False)
            property.owner = request.user
            property.save()

            # Handle image uploads (use prefix 'images' so JS matches the management_form ids)
            image_formset = PropertyImageFormSet(request.POST, request.FILES, instance=property, prefix='images')
            if image_formset.is_valid():
                image_formset.save()
                messages.success(request, 'Property listed successfully with images!')
                return redirect('hosts:dashboard')
            else:
                # If image formset is invalid, delete the property and show error
                property.delete()
                messages.error(request, 'Error uploading images. Please try again.')
        else:
            # Ensure image_formset exists so the template can render it with form errors
            # We don't have a saved Property instance in this branch, so provide an empty formset
            image_formset = PropertyImageFormSet(request.POST or None, request.FILES or None, prefix='images')
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PropertyForm()
        image_formset = PropertyImageFormSet(prefix='images')
    
    context = {
        'form': form,
        'image_formset': image_formset,
    }
    return render(request, 'hosts/add_listing.html', context)

@login_required
def edit_listing(request, property_id):
    property = get_object_or_404(Property, id=property_id, owner=request.user)
    
    if request.method == 'POST':
        form = PropertyForm(request.POST, instance=property)
        if form.is_valid():
            form.save()

            # Handle image uploads
            image_formset = PropertyImageFormSet(request.POST, request.FILES, instance=property, prefix='images')
            if image_formset.is_valid():
                image_formset.save()
                messages.success(request, 'Property updated successfully!')
                return redirect('hosts:view_listing', property_id=property.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PropertyForm(instance=property)
        image_formset = PropertyImageFormSet(instance=property, prefix='images')
    
    context = {
        'form': form,
        'property': property,
        'image_formset': image_formset,
    }
    return render(request, 'hosts/edit_listing.html', context)

@login_required
def view_listing(request, property_id):
    property = get_object_or_404(Property, id=property_id, owner=request.user)
    context = {
        'property': property,
    }
    return render(request, 'hosts/view_listing.html', context)

@login_required
def delete_listing(request, property_id):
    property = get_object_or_404(Property, id=property_id, owner=request.user)
    
    if request.method == 'POST':
        property.delete()
        messages.success(request, 'Property deleted successfully!')
        return redirect('hosts:dashboard')
    
    context = {
        'property': property,
    }
    return render(request, 'hosts/delete_listing.html', context)

@login_required
def my_listings(request):
    properties = Property.objects.filter(owner=request.user)
    context = {'properties': properties}
    return render(request, 'hosts/my_listings.html', context)

@login_required
def property_bookings(request):
    """View all bookings for host's properties"""
    if not (request.user.role in ['host', 'both']):
        messages.error(request, "Access denied. This page is for hosts only.")
        return redirect('core:home')
    
    properties = Property.objects.filter(owner=request.user)
    bookings = Booking.objects.filter(property__in=properties).select_related(
        'property', 'guest'
    ).order_by('-created_at')
    
    # Booking statistics
    stats = {
        'total_bookings': bookings.count(),
        'pending_bookings': bookings.filter(status='pending').count(),
        'confirmed_bookings': bookings.filter(status='confirmed').count(),
        'cancelled_bookings': bookings.filter(status='cancelled').count(),
        'completed_bookings': bookings.filter(status='completed').count(),
    }
    
    context = {
        'bookings': bookings,
        'stats': stats,
        'properties': properties,
    }
    return render(request, 'hosts/property_bookings.html', context)