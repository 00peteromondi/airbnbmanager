from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction
from django.db.models import Avg, Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.generic import View

from bookings.forms import WithdrawalRequestForm
from bookings.models import Booking, BookingPayment, HostWithdrawal
from bookings.services import simulate_withdrawal_payout
from core.mixins import HostRequiredMixin, LoginRequiredMixin, LogoutRequiredMixin, UserPassesTestMixin
from core.realtime import announce_live_update
from hosts.models import Host
from properties.forms import PropertyForm, PropertyImageFormSet
from properties.models import Property

from .forms import HostRegistrationForm


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


def _host_live_groups(user, property_id=None):
    groups = [
        'public-explore',
        f'host-dashboard-{user.id}',
        f'host-listings-{user.id}',
        f'host-bookings-{user.id}',
    ]
    if property_id:
        groups.append(f'property-{property_id}')
    return groups


def _announce_host_update(user, property_id=None, extra_groups=None, message='updated'):
    groups = _host_live_groups(user, property_id=property_id)
    if extra_groups:
        groups.extend(extra_groups)
    announce_live_update(groups, message=message)


def _coalesce_decimal(value):
    return value or Decimal('0.00')


def _booking_status_moment(booking, phase):
    if phase == 'check_in':
        target_date = booking.check_in_date
        target_time = booking.property.check_in_time
    else:
        target_date = booking.check_out_date
        target_time = booking.property.check_out_time
    target = datetime.combine(target_date, target_time)
    return timezone.make_aware(target, timezone.get_current_timezone())


def _booking_action_state(booking, now=None):
    now = now or timezone.localtime()
    check_in_at = _booking_status_moment(booking, 'check_in')
    check_out_at = _booking_status_moment(booking, 'check_out')

    controls = {
        'can_confirm': booking.status == 'pending',
        'can_cancel': booking.status in ['pending', 'confirmed'] and now < check_in_at,
        'can_check_in': booking.status == 'confirmed' and now >= check_in_at,
        'can_check_out': booking.status == 'checked_in' and now >= check_out_at,
        'can_complete': booking.status == 'checked_out',
        'next_message': '',
        'check_in_at': check_in_at,
        'check_out_at': check_out_at,
    }

    if booking.status == 'confirmed' and not controls['can_check_in']:
        controls['next_message'] = f"Check-in opens on {timezone.localtime(check_in_at).strftime('%b %d at %I:%M %p')}."
    elif booking.status == 'checked_in' and not controls['can_check_out']:
        controls['next_message'] = f"Check-out opens on {timezone.localtime(check_out_at).strftime('%b %d at %I:%M %p')}."
    elif booking.status == 'pending':
        controls['next_message'] = 'Approve or decline this request before the arrival window.'
    elif booking.status == 'checked_out':
        controls['next_message'] = 'Mark the stay complete to lock in post-stay reporting.'
    elif booking.status == 'completed':
        controls['next_message'] = 'This stay is fully closed out.'
    elif booking.status == 'cancelled':
        controls['next_message'] = 'This reservation is cancelled and no longer actionable.'

    return controls


def _available_withdrawal_amount(user):
    total_received = _coalesce_decimal(
        BookingPayment.objects.filter(host=user, status='paid').aggregate(total=Sum('amount'))['total']
    )
    committed = _coalesce_decimal(
        HostWithdrawal.objects.filter(host=user, status__in=['requested', 'processing', 'paid']).aggregate(total=Sum('amount'))['total']
    )
    return max(total_received - committed, Decimal('0.00'))


def _refresh_host_rollups(host_profile, properties, bookings):
    host_profile.total_properties = properties.count()
    host_profile.total_bookings = bookings.count()
    host_profile.total_earnings = _coalesce_decimal(
        bookings.filter(status__in=Booking.REVENUE_ACTIVE_STATUSES).aggregate(total=Sum('total_price'))['total']
    )
    host_profile.average_rating = properties.aggregate(avg=Avg('average_rating'))['avg'] or 0
    host_profile.save(update_fields=[
        'total_properties',
        'total_bookings',
        'total_earnings',
        'average_rating',
        'id_verified',
        'email_verified',
        'phone_verified',
        'fully_verified',
        'is_superhost',
        'superhost_since',
    ])
    return host_profile


def _base_host_finance_context(user):
    host_payments = BookingPayment.objects.filter(host=user).select_related('booking', 'guest', 'booking__property')
    withdrawals = HostWithdrawal.objects.filter(host=user)
    total_received = _coalesce_decimal(host_payments.filter(status='paid').aggregate(total=Sum('amount'))['total'])
    paid_out_total = _coalesce_decimal(withdrawals.filter(status='paid').aggregate(total=Sum('amount'))['total'])
    pending_payout_total = _coalesce_decimal(withdrawals.filter(status__in=['requested', 'processing']).aggregate(total=Sum('amount'))['total'])
    available_balance = _available_withdrawal_amount(user)
    return {
        'recent_payments': host_payments[:6],
        'recent_withdrawals': withdrawals[:5],
        'finance_snapshot': {
            'total_received': total_received,
            'paid_out_total': paid_out_total,
            'pending_payout_total': pending_payout_total,
            'available_balance': available_balance,
            'paid_payment_count': host_payments.filter(status='paid').count(),
        },
        'withdrawal_form': WithdrawalRequestForm(initial={
            'mpesa_phone_number': getattr(getattr(user, 'host_profile', None), 'mpesa_phone_number', '') or user.phone_number or '',
        }),
    }


def _host_dashboard_context(user):
    host_profile = _get_host_profile(user)
    properties = Property.objects.filter(owner=user).prefetch_related('images').order_by('-created_at')
    bookings = Booking.objects.filter(property__owner=user).select_related('property', 'guest')
    host_profile = _refresh_host_rollups(host_profile, properties, bookings)
    today = timezone.localdate()
    now = timezone.localtime()

    total_bookings = bookings.count()
    pending_bookings = bookings.filter(status='pending').count()
    confirmed_bookings = bookings.filter(status='confirmed').count()
    active_stays = bookings.filter(status='checked_in').count()
    completed_bookings = bookings.filter(status__in=['completed', 'checked_out']).count()
    revenue = _coalesce_decimal(
        bookings.filter(status__in=Booking.REVENUE_ACTIVE_STATUSES).aggregate(total_revenue=Sum('total_price'))['total_revenue']
    )

    next_week = today + timedelta(days=7)
    upcoming_arrivals = bookings.filter(
        status__in=['confirmed', 'pending'],
        check_in_date__gte=today,
        check_in_date__lte=next_week,
    ).order_by('check_in_date')[:6]
    check_ins_today = bookings.filter(status='confirmed', check_in_date=today).order_by('property__name')[:6]
    check_outs_today = bookings.filter(status='checked_in', check_out_date=today).order_by('property__name')[:6]
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
    for property_obj in properties:
        property_bookings = bookings.filter(property=property_obj)
        image_count = property_obj.images.count()
        summary = {
            'property': property_obj,
            'image_count': image_count,
            'booking_count': property_bookings.count(),
            'pending_count': property_bookings.filter(status='pending').count(),
            'confirmed_count': property_bookings.filter(status='confirmed').count(),
            'active_count': property_bookings.filter(status='checked_in').count(),
            'completed_count': property_bookings.filter(status__in=['completed', 'checked_out']).count(),
            'revenue': _coalesce_decimal(property_bookings.filter(status__in=Booking.REVENUE_ACTIVE_STATUSES).aggregate(total=Sum('total_price'))['total']),
            'next_arrival': property_bookings.filter(
                status__in=['pending', 'confirmed'],
                check_in_date__gte=today,
            ).order_by('check_in_date').first(),
        }
        property_summaries.append(summary)
        if image_count == 0:
            attention_items.append(f"{property_obj.name} needs gallery photos.")
        if not property_obj.latitude or not property_obj.longitude:
            attention_items.append(f"{property_obj.name} is missing an exact map pin.")
        if len(property_obj.amenities or []) < 4:
            attention_items.append(f"{property_obj.name} could use more amenities to improve conversion.")
        if not property_obj.is_active:
            attention_items.append(f"{property_obj.name} is paused and not bookable right now.")

    if not host_profile.tax_id:
        attention_items.append('Add your host tax information so payouts and reporting stay compliant.')
    if host_profile.payout_method == 'mpesa' and not host_profile.mpesa_phone_number:
        attention_items.append('Add your M-Pesa payout number to enable host withdrawals.')
    if user.government_id_status != 'verified':
        attention_items.append('Upload a government ID and complete verification to unlock full host trust signals.')

    top_properties = sorted(property_summaries, key=lambda item: (item['booking_count'], item['revenue']), reverse=True)[:4]
    readiness_checks = [
        {'label': 'Email verification', 'done': user.email_verified},
        {'label': 'Phone verification', 'done': user.phone_verified},
        {'label': 'Government ID approved', 'done': user.government_id_status == 'verified'},
        {'label': 'Tax and payout details added', 'done': bool(host_profile.tax_id and (host_profile.mpesa_phone_number or host_profile.bank_name))},
    ]

    property_latest = properties.order_by('-updated_at').values_list('updated_at', flat=True).first()
    booking_latest = bookings.order_by('-updated_at').values_list('updated_at', flat=True).first()
    latest_update = max(
        [stamp for stamp in [property_latest, booking_latest] if stamp is not None],
        default=None,
    )

    context = {
        'properties': properties,
        'property_summaries': property_summaries[:4],
        'top_properties': top_properties,
        'host_profile': host_profile,
        'readiness_checks': readiness_checks,
        'attention_items': attention_items[:7],
        'total_properties': properties.count(),
        'active_properties': active_properties,
        'paused_properties': paused_properties,
        'total_bookings': total_bookings,
        'pending_bookings': pending_bookings,
        'confirmed_bookings': confirmed_bookings,
        'active_stays': active_stays,
        'completed_bookings': completed_bookings,
        'revenue': revenue,
        'avg_listing_rating': avg_listing_rating,
        'recent_bookings': recent_bookings,
        'pending_requests': pending_requests,
        'active_guest_contacts': active_guest_contacts,
        'upcoming_arrivals': upcoming_arrivals,
        'check_ins_today': check_ins_today,
        'check_outs_today': check_outs_today,
        'now': now,
        'live_version': f"{properties.count()}:{total_bookings}:{latest_update.isoformat() if latest_update else 'none'}",
    }
    context.update(_base_host_finance_context(user))
    return context


def _host_listings_context(user):
    properties = Property.objects.filter(owner=user).prefetch_related('images').order_by('-created_at')
    listing_rows = []
    for property_obj in properties:
        property_bookings = Booking.objects.filter(property=property_obj)
        listing_rows.append({
            'property': property_obj,
            'bookings_count': property_bookings.count(),
            'pending_count': property_bookings.filter(status='pending').count(),
            'confirmed_count': property_bookings.filter(status='confirmed').count(),
            'active_count': property_bookings.filter(status='checked_in').count(),
            'revenue': _coalesce_decimal(property_bookings.filter(status__in=Booking.REVENUE_ACTIVE_STATUSES).aggregate(total=Sum('total_price'))['total']),
            'image_count': property_obj.images.count(),
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
    today = timezone.localdate()
    now = timezone.localtime()
    for booking in bookings:
        booking.host_controls = _booking_action_state(booking, now=now)
    stats = {
        'total_bookings': bookings.count(),
        'pending_bookings': bookings.filter(status='pending').count(),
        'confirmed_bookings': bookings.filter(status='confirmed').count(),
        'active_bookings': bookings.filter(status='checked_in').count(),
        'cancelled_bookings': bookings.filter(status='cancelled').count(),
        'completed_bookings': bookings.filter(status__in=['completed', 'checked_out']).count(),
        'revenue': _coalesce_decimal(bookings.filter(status__in=Booking.REVENUE_ACTIVE_STATUSES).aggregate(total=Sum('total_price'))['total']),
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
            property_obj = form.save(commit=False)
            property_obj.owner = request.user
            try:
                with transaction.atomic():
                    property_obj.save()
                    image_formset = PropertyImageFormSet(request.POST, request.FILES, instance=property_obj, prefix='images')
                    if image_formset.is_valid():
                        image_formset.save()
                        _announce_host_update(request.user, property_id=property_obj.id)
                        messages.success(request, 'Property listed successfully with images!')
                        return redirect('hosts:dashboard')
                    property_obj.delete()
                    messages.error(request, 'Please correct the image upload errors below.')
            except Exception as exc:
                if property_obj.pk:
                    property_obj.delete()
                image_formset = PropertyImageFormSet(request.POST, request.FILES, instance=property_obj, prefix='images')
                messages.error(request, f'Image upload failed: {exc}')
        else:
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
    property_obj = get_object_or_404(Property, id=property_id, owner=request.user)

    if request.method == 'POST':
        form = PropertyForm(request.POST, instance=property_obj)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                    image_formset = PropertyImageFormSet(request.POST, request.FILES, instance=property_obj, prefix='images')
                    if image_formset.is_valid():
                        image_formset.save()
                        _announce_host_update(request.user, property_id=property_obj.id)
                        messages.success(request, 'Property updated successfully!')
                        return redirect('hosts:view_listing', property_id=property_obj.id)
                    messages.error(request, 'Please correct the image upload errors below.')
            except Exception as exc:
                image_formset = PropertyImageFormSet(request.POST, request.FILES, instance=property_obj, prefix='images')
                messages.error(request, f'Image upload failed: {exc}')
        else:
            image_formset = PropertyImageFormSet(request.POST, request.FILES, instance=property_obj, prefix='images')
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PropertyForm(instance=property_obj)
        image_formset = PropertyImageFormSet(instance=property_obj, prefix='images')

    context = {
        'form': form,
        'property': property_obj,
        'image_formset': image_formset,
    }
    return render(request, 'hosts/edit_listing.html', context)


@login_required
def view_listing(request, property_id):
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate
    property_obj = get_object_or_404(Property, id=property_id, owner=request.user)
    bookings = Booking.objects.filter(property=property_obj).select_related('guest').order_by('-created_at')
    today = timezone.localdate()
    now = timezone.localtime()
    for booking in bookings:
        booking.host_controls = _booking_action_state(booking, now=now)
    listing_stats = {
        'total_bookings': bookings.count(),
        'pending_bookings': bookings.filter(status='pending').count(),
        'confirmed_bookings': bookings.filter(status='confirmed').count(),
        'active_bookings': bookings.filter(status='checked_in').count(),
        'completed_bookings': bookings.filter(status__in=['completed', 'checked_out']).count(),
        'revenue': _coalesce_decimal(bookings.filter(status__in=Booking.REVENUE_ACTIVE_STATUSES).aggregate(total=Sum('total_price'))['total']),
        'next_arrival': bookings.filter(status__in=['pending', 'confirmed'], check_in_date__gte=today).order_by('check_in_date').first(),
    }
    context = {
        'property': property_obj,
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
    property_obj = get_object_or_404(Property, id=property_id, owner=request.user)

    if request.method == 'POST':
        property_identifier = property_obj.id
        property_obj.delete()
        _announce_host_update(request.user, property_id=property_identifier)
        messages.success(request, 'Property deleted successfully!')
        return redirect('hosts:dashboard')

    context = {
        'property': property_obj,
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
        next_url = request.POST.get('next')
        now = timezone.localtime()
        controls = _booking_action_state(booking, now=now)
        allowed_transitions = {
            'pending': ['confirmed', 'cancelled'],
            'confirmed': ['checked_in', 'cancelled'],
            'checked_in': ['checked_out'],
            'checked_out': ['completed'],
        }

        if status not in allowed_transitions.get(booking.status, []):
            messages.error(request, 'That booking action is not available from the current reservation state.')
        elif status == 'checked_in' and not controls['can_check_in']:
            messages.error(request, controls['next_message'] or 'Check-in is not available yet for this reservation.')
        elif status == 'checked_out' and not controls['can_check_out']:
            messages.error(request, controls['next_message'] or 'Check-out is not available yet for this reservation.')
        else:
            booking.status = status
            update_fields = ['status', 'updated_at']
            if status == 'confirmed':
                booking.confirmed_at = booking.confirmed_at or now
                update_fields.append('confirmed_at')
            elif status == 'checked_in':
                booking.checked_in_at = now
                update_fields.append('checked_in_at')
            elif status == 'checked_out':
                booking.checked_out_at = now
                update_fields.append('checked_out_at')
            elif status == 'completed':
                booking.completed_at = now
                update_fields.append('completed_at')
            elif status == 'cancelled':
                booking.cancelled_at = now
                update_fields.append('cancelled_at')
            booking.save(update_fields=update_fields)
            _announce_host_update(
                request.user,
                property_id=booking.property_id,
                extra_groups=[f'guest-bookings-{booking.guest_id}'],
                message='booking-updated',
            )
            status_labels = {
                'confirmed': 'confirmed',
                'cancelled': 'cancelled',
                'checked_in': 'marked as checked in',
                'checked_out': 'marked as checked out',
                'completed': 'marked as completed',
            }
            messages.success(request, f"{booking.guest.get_display_name()}'s booking for {booking.property.name} was {status_labels.get(status, status)}.")
        if next_url:
            return redirect(next_url)
    return redirect('hosts:property_bookings')


@login_required
def toggle_listing_status(request, property_id):
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate
    property_obj = get_object_or_404(Property, id=property_id, owner=request.user)
    if request.method == 'POST':
        property_obj.is_active = not property_obj.is_active
        property_obj.save(update_fields=['is_active'])
        _announce_host_update(request.user, property_id=property_obj.id, message='listing-updated')
        messages.success(request, f"{property_obj.name} is now {'live' if property_obj.is_active else 'paused'}.")
    next_url = request.POST.get('next')
    if next_url:
        return redirect(next_url)
    return redirect('hosts:view_listing', property_id=property_obj.id)


@login_required
def request_withdrawal(request):
    host_gate = _ensure_host_mode(request)
    if host_gate:
        return host_gate
    host_profile = _get_host_profile(request.user)
    next_url = request.POST.get('next') or reverse('hosts:dashboard')

    if request.method != 'POST':
        return redirect(next_url)

    form = WithdrawalRequestForm(request.POST)
    available_balance = _available_withdrawal_amount(request.user)
    if not form.is_valid():
        messages.error(request, 'Please review the withdrawal details and try again.')
        return redirect(next_url)

    withdrawal = form.save(commit=False)
    withdrawal.host = request.user
    if withdrawal.amount > available_balance:
        messages.error(request, 'That withdrawal exceeds the balance currently available for payout.')
        return redirect(next_url)

    if host_profile.payout_method == 'mpesa' and not host_profile.mpesa_phone_number and not withdrawal.mpesa_phone_number:
        messages.error(request, 'Add an M-Pesa payout number before requesting a withdrawal.')
        return redirect(next_url)

    withdrawal.mpesa_phone_number = withdrawal.mpesa_phone_number or host_profile.mpesa_phone_number or request.user.phone_number or ''
    withdrawal.reference = f'BAYWD-{timezone.now().strftime("%Y%m%d%H%M%S")}'
    withdrawal.status = 'processing'
    withdrawal.processed_at = timezone.localtime()
    withdrawal.save()

    result = simulate_withdrawal_payout()
    if result.get('status') == 'paid':
        withdrawal.status = 'paid'
        withdrawal.reference = result.get('reference', withdrawal.reference)
        withdrawal.notes = (withdrawal.notes or '').strip()
        withdrawal.processed_at = result.get('processed_at', timezone.localtime())
        withdrawal.save(update_fields=['status', 'reference', 'notes', 'processed_at', 'updated_at'])
        messages.success(request, f'Withdrawal of KES {withdrawal.amount:,.0f} has been queued to M-Pesa.')
    else:
        withdrawal.status = 'failed'
        withdrawal.notes = result.get('message', 'Payout simulation failed.')
        withdrawal.save(update_fields=['status', 'notes', 'updated_at'])
        messages.error(request, 'We could not queue that withdrawal right now. Please try again shortly.')

    _announce_host_update(request.user, extra_groups=[f'guest-bookings-{request.user.id}'], message='finance-updated')
    return redirect(next_url)
