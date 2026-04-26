from django.http import HttpResponseForbidden, JsonResponse
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.template.loader import render_to_string
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
from django.db import transaction
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


def _host_dashboard_context(user):
    host_profile = _get_host_profile(user)
    properties = Property.objects.filter(owner=user).prefetch_related('images').order_by('-created_at')
    bookings = Booking.objects.filter(property__owner=user).select_related('property', 'guest')
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
    pending_requests = bookings.filter(status='pending').order_by('check_in_date', '-created_at')[:5]
    active_guest_contacts = bookings.filter(
        status__in=['pending', 'confirmed', 'checked_in'],
    ).select_related('guest', 'property').order_by('check_in_date')[:6]
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
        {'label': 'Email verification', 'done': user.email_verified},
        {'label': 'Phone verification', 'done': user.phone_verified},
        {'label': 'Government ID on file', 'done': bool(host_profile.government_id)},
        {'label': 'Tax or payout details added', 'done': bool(host_profile.tax_id or host_profile.bank_name)},
    ]

    property_latest = properties.order_by('-updated_at').values_list('updated_at', flat=True).first()
    booking_latest = bookings.order_by('-updated_at').values_list('updated_at', flat=True).first()
    latest_update = max(
        [stamp for stamp in [property_latest, booking_latest] if stamp is not None],
        default=None,
    )

    return {
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
        'pending_requests': pending_requests,
        'active_guest_contacts': active_guest_contacts,
        'upcoming_arrivals': upcoming_arrivals,
        'live_version': f"{properties.count()}:{total_bookings}:{latest_update.isoformat() if latest_update else 'none'}",
    }


def _host_listings_context(user):
    properties = Property.objects.filter(owner=user).prefetch_related('images').order_by('-created_at')
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

    latest_update = properties.order_by('-updated_at').values_list('updated_at', flat=True).first()
    return {
        'properties': properties,
        'listing_rows': listing_rows,
        'live_version': f"{properties.count()}:{latest_update.isoformat() if latest_update else 'none'}",
    }


def _host_bookings_context(user):
    properties = Property.objects.filter(owner=user)
    bookings = Booking.objects.filter(property__in=properties).select_related(
        'property', 'guest'
    ).order_by('-created_at')
    today = timezone.now().date()
    stats = {
        'total_bookings': bookings.count(),
        'pending_bookings': bookings.filter(status='pending').count(),
        'confirmed_bookings': bookings.filter(status='confirmed').count(),
        'cancelled_bookings': bookings.filter(status='cancelled').count(),
        'completed_bookings': bookings.filter(status='completed').count(),
        'revenue': bookings.filter(status__in=['confirmed', 'completed']).aggregate(total=Sum('total_price'))['total'] or 0,
    }
    latest_update = bookings.order_by('-updated_at').values_list('updated_at', flat=True).first()
    return {
        'bookings': bookings,
        'stats': stats,
        'properties': properties,
        'upcoming_arrivals': bookings.filter(status__in=['pending', 'confirmed'], check_in_date__gte=today).order_by('check_in_date')[:6],
        'live_version': f"{properties.count()}:{bookings.count()}:{latest_update.isoformat() if latest_update else 'none'}",
    }

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
    return render(request, 'hosts/dashboard.html', _host_dashboard_context(request.user))

@login_required
def add_listing(request):
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate
    if request.method == 'POST':
        form = PropertyForm(request.POST)
        if form.is_valid():
            property = form.save(commit=False)
            property.owner = request.user
            try:
                with transaction.atomic():
                    property.save()
                    image_formset = PropertyImageFormSet(request.POST, request.FILES, instance=property, prefix='images')
                    if image_formset.is_valid():
                        image_formset.save()
                        messages.success(request, 'Property listed successfully with images!')
                        return redirect('hosts:dashboard')
                    property.delete()
                    messages.error(request, 'Please correct the image upload errors below.')
            except Exception as exc:
                if property.pk:
                    property.delete()
                image_formset = PropertyImageFormSet(request.POST, request.FILES, instance=property, prefix='images')
                messages.error(request, f'Image upload failed: {exc}')
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
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate
    property = get_object_or_404(Property, id=property_id, owner=request.user)
    
    if request.method == 'POST':
        form = PropertyForm(request.POST, instance=property)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()

                    # Handle image uploads
                    image_formset = PropertyImageFormSet(request.POST, request.FILES, instance=property, prefix='images')
                    if image_formset.is_valid():
                        image_formset.save()
                        messages.success(request, 'Property updated successfully!')
                        return redirect('hosts:view_listing', property_id=property.id)
                    messages.error(request, 'Please correct the image upload errors below.')
            except Exception as exc:
                image_formset = PropertyImageFormSet(request.POST, request.FILES, instance=property, prefix='images')
                messages.error(request, f'Image upload failed: {exc}')
        else:
            image_formset = PropertyImageFormSet(request.POST, request.FILES, instance=property, prefix='images')
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
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate
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
        'pending_requests': bookings.filter(status='pending')[:4],
    }
    return render(request, 'hosts/view_listing.html', context)

@login_required
def delete_listing(request, property_id):
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate
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
    return render(request, 'hosts/my_listings.html', _host_listings_context(request.user))

@login_required
def property_bookings(request):
    """View all bookings for host's properties"""
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate
    
    return render(request, 'hosts/owner_bookings.html', _host_bookings_context(request.user))


@login_required
def dashboard_live(request):
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return JsonResponse({'redirect_url': reverse('core:home')}, status=403)
    context = _host_dashboard_context(request.user)
    return JsonResponse({
        'html': render_to_string('hosts/_dashboard_content.html', context, request=request),
        'version': context['live_version'],
    })


@login_required
def my_listings_live(request):
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return JsonResponse({'redirect_url': reverse('core:home')}, status=403)
    context = _host_listings_context(request.user)
    return JsonResponse({
        'html': render_to_string('hosts/_my_listings_content.html', context, request=request),
        'version': context['live_version'],
    })


@login_required
def property_bookings_live(request):
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return JsonResponse({'redirect_url': reverse('core:home')}, status=403)
    context = _host_bookings_context(request.user)
    return JsonResponse({
        'html': render_to_string('hosts/_owner_bookings_content.html', context, request=request),
        'version': context['live_version'],
    })


@login_required
def update_booking_status(request, booking_id, status):
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate
    booking = get_object_or_404(Booking, id=booking_id, property__owner=request.user)
    if request.method == 'POST':
        valid_statuses = ['pending', 'confirmed', 'cancelled', 'checked_in', 'checked_out', 'completed']
        next_url = request.POST.get('next')
        if status in valid_statuses:
            booking.status = status
            booking.save(update_fields=['status', 'updated_at'])
            status_labels = {
                'pending': 'moved back to pending review',
                'confirmed': 'confirmed',
                'cancelled': 'cancelled',
                'checked_in': 'marked as checked in',
                'checked_out': 'marked as checked out',
                'completed': 'marked as completed',
            }
            messages.success(request, f"{booking.guest.get_display_name()}'s booking for {booking.property.name} was {status_labels.get(status, status)}.")
        else:
            messages.error(request, 'Invalid booking status action.')
        if next_url:
            return redirect(next_url)
    return redirect('hosts:property_bookings')


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
