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
from django.db.models import Sum, Count, Avg, Q
from django.utils import timezone
from datetime import timedelta
from hosts.models import Host


def _ensure_host_mode(request):
    if not (request.user.role in ['host', 'both']):
        messages.error(request, "Access denied. This page is for hosts only.")
        return redirect('core:home')
    if request.user.role == 'both' and request.session.get('active_role') == 'guest':
        messages.info(request, "Please switch to host mode to access the host dashboard.")
        return redirect('guests:guest_dashboard')
    return None


def _get_host_profile(user):
    host_profile, _ = Host.objects.get_or_create(user=user)
    return host_profile

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
            messages.success(request, "Registration successful! Welcome to BayStays.")
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
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate

    host_profile = _get_host_profile(request.user)
    properties = Property.objects.filter(owner=request.user).prefetch_related('images').order_by('-created_at')

    bookings = Booking.objects.filter(property__owner=request.user).select_related('property', 'guest')
    total_bookings = bookings.count()
    pending_bookings = bookings.filter(status='pending').count()
    confirmed_bookings = bookings.filter(status='confirmed').count()
    completed_bookings = bookings.filter(status__in=['completed', 'checked_out']).count()
    revenue = bookings.filter(status__in=['confirmed', 'completed']).aggregate(
        total_revenue=Sum('total_price')
    )['total_revenue'] or 0

    today = timezone.now().date()
    next_week = today + timedelta(days=7)
    upcoming_arrivals = bookings.filter(
        status__in=['confirmed', 'pending'],
        check_in_date__gte=today,
        check_in_date__lte=next_week,
    ).order_by('check_in_date')[:6]
    recent_bookings = bookings.order_by('-created_at')[:6]
    active_properties = properties.filter(is_active=True).count()
    paused_properties = properties.filter(is_active=False).count()
    avg_listing_rating = properties.aggregate(avg=Avg('average_rating'))['avg'] or 0

    property_summaries = []
    attention_items = []
    for property in properties:
        property_bookings = bookings.filter(property=property)
        image_count = property.images.count()
        summary = {
            'property': property,
            'image_count': image_count,
            'booking_count': property_bookings.count(),
            'pending_count': property_bookings.filter(status='pending').count(),
            'confirmed_count': property_bookings.filter(status='confirmed').count(),
            'completed_count': property_bookings.filter(status__in=['completed', 'checked_out']).count(),
            'revenue': property_bookings.filter(status__in=['confirmed', 'completed']).aggregate(total=Sum('total_price'))['total'] or 0,
            'next_arrival': property_bookings.filter(
                status__in=['pending', 'confirmed'],
                check_in_date__gte=today,
            ).order_by('check_in_date').first(),
        }
        property_summaries.append(summary)
        if image_count == 0:
            attention_items.append(f"{property.name} needs gallery photos.")
        if not property.latitude or not property.longitude:
            attention_items.append(f"{property.name} is missing an exact map pin.")
        if len(property.amenities or []) < 4:
            attention_items.append(f"{property.name} could use more amenities to improve conversion.")
        if not property.is_active:
            attention_items.append(f"{property.name} is paused and not bookable right now.")

    top_properties = sorted(property_summaries, key=lambda item: (item['booking_count'], item['revenue']), reverse=True)[:4]
    readiness_checks = [
        {'label': 'Email verification', 'done': request.user.email_verified},
        {'label': 'Phone verification', 'done': request.user.phone_verified},
        {'label': 'Government ID on file', 'done': bool(host_profile.government_id)},
        {'label': 'Tax or payout details added', 'done': bool(host_profile.tax_id or host_profile.bank_name)},
    ]

    context = {
        'properties': properties,
        'property_summaries': property_summaries[:4],
        'top_properties': top_properties,
        'host_profile': host_profile,
        'readiness_checks': readiness_checks,
        'attention_items': attention_items[:6],
        'total_properties': properties.count(),
        'active_properties': active_properties,
        'paused_properties': paused_properties,
        'total_bookings': total_bookings,
        'pending_bookings': pending_bookings,
        'confirmed_bookings': confirmed_bookings,
        'completed_bookings': completed_bookings,
        'revenue': revenue,
        'avg_listing_rating': avg_listing_rating,
        'recent_bookings': recent_bookings,
        'upcoming_arrivals': upcoming_arrivals,
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
    bookings = Booking.objects.filter(property=property).select_related('guest').order_by('-created_at')
    today = timezone.now().date()
    listing_stats = {
        'total_bookings': bookings.count(),
        'pending_bookings': bookings.filter(status='pending').count(),
        'confirmed_bookings': bookings.filter(status='confirmed').count(),
        'completed_bookings': bookings.filter(status__in=['completed', 'checked_out']).count(),
        'revenue': bookings.filter(status__in=['confirmed', 'completed']).aggregate(total=Sum('total_price'))['total'] or 0,
        'next_arrival': bookings.filter(status__in=['pending', 'confirmed'], check_in_date__gte=today).order_by('check_in_date').first(),
    }
    context = {
        'property': property,
        'bookings': bookings[:8],
        'listing_stats': listing_stats,
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
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate
    properties = Property.objects.filter(owner=request.user).prefetch_related('images').order_by('-created_at')
    listing_rows = []
    for property in properties:
        property_bookings = Booking.objects.filter(property=property)
        listing_rows.append({
            'property': property,
            'bookings_count': property_bookings.count(),
            'pending_count': property_bookings.filter(status='pending').count(),
            'confirmed_count': property_bookings.filter(status='confirmed').count(),
            'revenue': property_bookings.filter(status__in=['confirmed', 'completed']).aggregate(total=Sum('total_price'))['total'] or 0,
            'image_count': property.images.count(),
        })
    context = {
        'properties': properties,
        'listing_rows': listing_rows,
    }
    return render(request, 'hosts/my_listings.html', context)

@login_required
def property_bookings(request):
    """View all bookings for host's properties"""
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate
    
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
        'revenue': bookings.filter(status__in=['confirmed', 'completed']).aggregate(total=Sum('total_price'))['total'] or 0,
    }

    today = timezone.now().date()
    context = {
        'bookings': bookings,
        'stats': stats,
        'properties': properties,
        'upcoming_arrivals': bookings.filter(status__in=['pending', 'confirmed'], check_in_date__gte=today).order_by('check_in_date')[:6],
    }
    return render(request, 'hosts/owner_bookings.html', context)


@login_required
def toggle_listing_status(request, property_id):
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate
    property = get_object_or_404(Property, id=property_id, owner=request.user)
    if request.method == 'POST':
        property.is_active = not property.is_active
        property.save(update_fields=['is_active'])
        messages.success(request, f"{property.name} is now {'live' if property.is_active else 'paused'}.")
    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('hosts:view_listing', property_id=property.id)
