import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, ListView, UpdateView

from core.realtime import announce_live_update
from hosts.models import Host
from properties.models import Property

from .forms import BookingForm
from .models import Booking, BookingPayment
from .services import initiate_mpesa_payment


def _unavailable_ranges_for_property(property_obj):
    return list(
        Booking.objects.filter(
            property=property_obj,
            status__in=['confirmed', 'pending', 'checked_in']
        )
        .order_by('check_in_date')
        .values('check_in_date', 'check_out_date', 'status')[:12]
    )


def _booking_overlap_queryset(property_obj, check_in_date, check_out_date, exclude_id=None):
    queryset = Booking.objects.filter(
        property=property_obj,
        check_in_date__lt=check_out_date,
        check_out_date__gt=check_in_date,
        status__in=['confirmed', 'pending', 'checked_in'],
    )
    if exclude_id:
        queryset = queryset.exclude(id=exclude_id)
    return queryset


def _coalesce_decimal(value):
    return value or Decimal('0.00')


def _guest_live_groups(guest_id, property_id=None, owner_id=None):
    groups = [f'guest-bookings-{guest_id}']
    if property_id:
        groups.append(f'property-{property_id}')
    if owner_id:
        groups.extend([
            f'host-dashboard-{owner_id}',
            f'host-listings-{owner_id}',
            f'host-bookings-{owner_id}',
        ])
    return groups


def _announce_booking_update(booking, message='booking-updated'):
    announce_live_update(
        _guest_live_groups(booking.guest_id, property_id=booking.property_id, owner_id=booking.property.owner_id) + ['public-explore'],
        message=message,
    )


def _run_mpesa_charge(booking, phone_number):
    payment = BookingPayment.objects.create(
        booking=booking,
        guest=booking.guest,
        host=booking.property.owner,
        amount=booking.total_price,
        phone_number=phone_number,
        status='initiated',
    )
    result = initiate_mpesa_payment(
        booking=booking,
        phone_number=phone_number,
        amount=booking.total_price,
    )
    payment.status = result.get('status', 'failed')
    payment.checkout_request_id = result.get('checkout_request_id', '')
    payment.merchant_request_id = result.get('merchant_request_id', '')
    payment.transaction_reference = result.get('transaction_reference', '')
    payment.failure_reason = result.get('message', '')
    update_fields = [
        'status',
        'checkout_request_id',
        'merchant_request_id',
        'transaction_reference',
        'failure_reason',
        'updated_at',
    ]
    if payment.status == 'paid':
        payment.paid_at = timezone.localtime()
        update_fields.append('paid_at')
        booking.payment_status = 'paid'
        booking.payment_intent_id = payment.transaction_reference or payment.checkout_request_id
        booking.save(update_fields=['payment_status', 'payment_intent_id', 'updated_at'])
    elif payment.status == 'initiated':
        booking.payment_status = 'initiated'
        booking.payment_intent_id = payment.checkout_request_id or payment.transaction_reference
        booking.save(update_fields=['payment_status', 'payment_intent_id', 'updated_at'])
    else:
        booking.payment_status = 'failed'
        booking.save(update_fields=['payment_status', 'updated_at'])
    payment.save(update_fields=update_fields)
    return payment, result


def _guest_bookings_context(user):
    bookings = Booking.objects.filter(guest=user).select_related('property').prefetch_related('payments').order_by('-created_at')
    today = timezone.localdate()
    active_bookings = bookings.exclude(status='cancelled')
    payment_history = BookingPayment.objects.filter(guest=user).select_related('booking', 'booking__property', 'host')
    latest_update = max(
        [stamp for stamp in [
            bookings.order_by('-updated_at').values_list('updated_at', flat=True).first(),
            payment_history.order_by('-updated_at').values_list('updated_at', flat=True).first(),
        ] if stamp is not None],
        default=None,
    )
    return {
        'bookings': bookings,
        'today': today,
        'booking_summary': {
            'total': bookings.count(),
            'upcoming': active_bookings.filter(check_out_date__gte=today).count(),
            'manageable': bookings.filter(
                status__in=['pending', 'confirmed'],
                check_in_date__gt=today,
            ).count(),
        },
        'payment_summary': {
            'paid_total': _coalesce_decimal(payment_history.filter(status='paid').aggregate(total=Sum('amount'))['total']),
            'paid_count': payment_history.filter(status='paid').count(),
            'pending_count': payment_history.filter(status__in=['pending', 'initiated']).count(),
            'failed_count': payment_history.filter(status='failed').count(),
        },
        'recent_payments': payment_history[:6],
        'can_manage_any_booking': bookings.filter(
            status__in=['pending', 'confirmed'],
            check_in_date__gt=today,
        ).exists(),
        'live_version': f"{bookings.count()}:{payment_history.count()}:{latest_update.isoformat() if latest_update else 'none'}",
    }


class BookingCreateView(LoginRequiredMixin, CreateView):
    model = Booking
    form_class = BookingForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['property'] = get_object_or_404(Property, pk=self.kwargs['property_id'])
        return context

    def form_valid(self, form):
        property_obj = get_object_or_404(Property, pk=self.kwargs['property_id'])
        unavailable_ranges = _unavailable_ranges_for_property(property_obj)

        overlapping_bookings = _booking_overlap_queryset(
            property_obj,
            form.instance.check_in_date,
            form.instance.check_out_date,
        )

        if overlapping_bookings.exists():
            form.add_error(None, 'These dates are not available')
            return self.form_invalid(form, unavailable_ranges=unavailable_ranges)

        if Booking.objects.filter(
            guest=self.request.user,
            property=property_obj,
            check_in_date__lt=form.instance.check_out_date,
            check_out_date__gt=form.instance.check_in_date,
            status__in=['pending', 'confirmed', 'checked_in']
        ).exists():
            form.add_error(None, 'You already have an active booking for this stay within that period.')
            return self.form_invalid(form, unavailable_ranges=unavailable_ranges)

        if form.instance.check_in_date <= timezone.localdate():
            form.add_error('check_in_date', 'Check-in must be at least 1 day in advance')
            return self.form_invalid(form, unavailable_ranges=unavailable_ranges)

        if form.instance.num_guests > property_obj.max_guests:
            form.add_error('num_guests', f'This property accommodates maximum {property_obj.max_guests} guests')
            return self.form_invalid(form, unavailable_ranges=unavailable_ranges)

        num_nights = (form.instance.check_out_date - form.instance.check_in_date).days
        form.instance.total_price = num_nights * property_obj.price_per_night
        form.instance.guest = self.request.user
        form.instance.property = property_obj
        form.instance.payment_status = 'pending'

        host_profile = Host.objects.filter(user=property_obj.owner).first()
        if host_profile and (host_profile.instant_book or host_profile.auto_approval):
            form.instance.status = 'confirmed'
            form.instance.confirmed_at = timezone.localtime()

        mpesa_phone_number = (form.cleaned_data.get('mpesa_phone_number') or self.request.user.phone_number or '').strip()
        charge_now = form.cleaned_data.get('charge_now')
        if charge_now and not mpesa_phone_number:
            form.add_error('mpesa_phone_number', 'Add an M-Pesa number to charge this booking now.')
            return self.form_invalid(form, unavailable_ranges=unavailable_ranges)

        with transaction.atomic():
            response = super().form_valid(form)
            payment = None
            payment_result = None
            if charge_now:
                payment, payment_result = _run_mpesa_charge(self.object, mpesa_phone_number)

        _announce_booking_update(self.object, message='booking-created')
        messages.success(self.request, 'Booking request submitted successfully!')
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'ok': True,
                'message': 'Booking request submitted successfully.',
                'redirect_url': reverse('bookings:booking_list'),
                'total_price': str(self.object.total_price),
                'status': self.object.status,
                'payment_status': self.object.payment_status,
                'payment_message': payment_result.get('message') if payment_result else '',
                'booking_id': self.object.id,
                'paid_now': bool(payment and payment.status == 'paid'),
            })
        return response

    def form_invalid(self, form, unavailable_ranges=None):
        response = super().form_invalid(form)
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'ok': False,
                'errors': form.errors,
                'non_field_errors': form.non_field_errors(),
                'unavailable_ranges': [
                    {
                        'check_in': row['check_in_date'].isoformat(),
                        'check_out': row['check_out_date'].isoformat(),
                        'status': row['status'],
                    }
                    for row in (unavailable_ranges or [])
                ],
            }, status=400)
        return response

    def get_success_url(self):
        return reverse('bookings:booking_list')


class OwnerBookingListView(LoginRequiredMixin, ListView):
    model = Booking
    template_name = 'hosts/owner_bookings.html'
    context_object_name = 'bookings'
    paginate_by = 10

    def get_queryset(self):
        return Booking.objects.filter(property__owner=self.request.user).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bookings = self.get_queryset()
        context['stats'] = {
            'total_bookings': bookings.count(),
            'pending_bookings': bookings.filter(status='pending').count(),
            'confirmed_bookings': bookings.filter(status='confirmed').count(),
            'cancelled_bookings': bookings.filter(status='cancelled').count(),
        }
        return context


@login_required
def update_booking_status(request, booking_id, status):
    if request.method == 'POST':
        booking = get_object_or_404(Booking, id=booking_id, property__owner=request.user)
        valid_statuses = ['pending', 'confirmed', 'cancelled', 'checked_in', 'checked_out', 'completed']
        next_url = request.POST.get('next')

        if status in valid_statuses:
            booking.status = status
            booking.save(update_fields=['status', 'updated_at'])
            _announce_booking_update(booking, message='booking-updated')
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
            messages.error(request, 'Invalid status')

        if next_url:
            return redirect(next_url)

    return redirect('hosts:property_bookings')


@login_required
def update_booking_notes(request, booking_id):
    if request.method == 'POST':
        booking = get_object_or_404(Booking, id=booking_id, property__owner=request.user)
        if hasattr(booking, 'admin_notes'):
            booking.admin_notes = request.POST.get('admin_notes', '')
            booking.save()
            _announce_booking_update(booking, message='booking-updated')
            messages.success(request, 'Notes updated successfully!')
        else:
            messages.info(request, 'Booking notes are not enabled on this project yet.')

    return redirect('hosts:property_bookings')


class BookingUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Booking
    fields = ['status']

    def test_func(self):
        return self.request.user == self.get_object().property.owner

    def form_valid(self, form):
        booking = self.get_object()
        if booking.status != form.cleaned_data['status']:
            messages.info(self.request, f"Booking status changed to {form.cleaned_data['status']}")
        return super().form_valid(form)


class UserBookingListView(LoginRequiredMixin, ListView):
    model = Booking
    template_name = 'bookings/booking_list.html'
    context_object_name = 'bookings'

    def get_queryset(self):
        return Booking.objects.filter(guest=self.request.user).select_related('property').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(_guest_bookings_context(self.request.user))
        return context


@login_required
def booking_list_live(request):
    context = _guest_bookings_context(request.user)
    return JsonResponse({
        'html': render_to_string('bookings/_booking_list_content.html', context, request=request),
        'version': context['live_version'],
    })


@login_required
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, guest=request.user)
    if request.method != 'POST':
        return redirect('bookings:booking_list')

    if booking.status not in ['pending', 'confirmed']:
        messages.error(request, 'Only active reservation requests can be cancelled.')
        return redirect('bookings:booking_list')
    if booking.check_in_date <= timezone.localdate():
        messages.error(request, 'This booking can no longer be cancelled from your account because the stay has already started.')
        return redirect('bookings:booking_list')

    booking.status = 'cancelled'
    booking.cancelled_at = timezone.localtime()
    booking.save(update_fields=['status', 'cancelled_at', 'updated_at'])
    _announce_booking_update(booking, message='booking-cancelled')
    messages.success(request, f'{booking.property.name} has been cancelled.')
    return redirect('bookings:booking_list')


@login_required
def reschedule_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, guest=request.user)
    if booking.status not in ['pending', 'confirmed']:
        messages.error(request, 'Only active bookings can be rescheduled.')
        return redirect('bookings:booking_list')
    if booking.check_in_date <= timezone.localdate():
        messages.error(request, 'This stay has already started, so it cannot be rescheduled from your account.')
        return redirect('bookings:booking_list')

    if request.method == 'POST':
        form = BookingForm(request.POST, instance=booking)
        if form.is_valid():
            rescheduled = form.save(commit=False)
            unavailable_ranges = _unavailable_ranges_for_property(booking.property)
            overlaps = _booking_overlap_queryset(
                booking.property,
                rescheduled.check_in_date,
                rescheduled.check_out_date,
                exclude_id=booking.id,
            )
            if overlaps.exists():
                form.add_error(None, 'Those new dates overlap with another active booking.')
            elif rescheduled.check_in_date <= timezone.localdate():
                form.add_error('check_in_date', 'Check-in must be at least 1 day in advance')
            elif rescheduled.num_guests > booking.property.max_guests:
                form.add_error('num_guests', f'This property accommodates maximum {booking.property.max_guests} guests')
            else:
                nights = (rescheduled.check_out_date - rescheduled.check_in_date).days
                rescheduled.total_price = nights * booking.property.price_per_night
                rescheduled.save()
                _announce_booking_update(rescheduled, message='booking-rescheduled')
                messages.success(request, f'{booking.property.name} was rescheduled successfully.')
                return redirect('bookings:booking_list')
        else:
            unavailable_ranges = _unavailable_ranges_for_property(booking.property)
    else:
        form = BookingForm(instance=booking)
        unavailable_ranges = _unavailable_ranges_for_property(booking.property)

    return render(request, 'bookings/booking_edit.html', {
        'form': form,
        'booking': booking,
        'property': booking.property,
        'unavailable_ranges': unavailable_ranges,
    })


@login_required
def pay_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, guest=request.user)
    next_url = request.POST.get('next') or reverse('bookings:booking_list')
    if request.method != 'POST':
        return redirect(next_url)

    if booking.payment_status == 'paid':
        messages.info(request, 'This reservation has already been paid for.')
        return redirect(next_url)

    phone_number = (request.POST.get('mpesa_phone_number') or request.user.phone_number or '').strip()
    if not phone_number:
        messages.error(request, 'Add an M-Pesa number to complete this payment.')
        return redirect(next_url)

    payment, result = _run_mpesa_charge(booking, phone_number)
    _announce_booking_update(booking, message='payment-updated')
    if payment.status == 'paid':
        messages.success(request, f'Payment for {booking.property.name} was received successfully.')
    elif payment.status == 'initiated':
        messages.success(request, result.get('message') or 'M-Pesa payment initiated. Complete the prompt on your phone.')
    else:
        messages.error(request, result.get('message') or 'We could not process that M-Pesa payment right now.')
    return redirect(next_url)


@csrf_exempt
def mpesa_callback(request):
    if request.method != 'POST':
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid method.'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'ResultCode': 1, 'ResultDesc': 'Invalid JSON.'}, status=400)

    callback = payload.get('Body', {}).get('stkCallback', {})
    checkout_request_id = callback.get('CheckoutRequestID')
    if not checkout_request_id:
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'No checkout request id supplied.'})

    payment = BookingPayment.objects.filter(checkout_request_id=checkout_request_id).select_related('booking', 'booking__property').first()
    if not payment:
        return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Payment record not found.'})

    items = callback.get('CallbackMetadata', {}).get('Item', []) or []
    metadata = {}
    for item in items:
        name = item.get('Name')
        if name:
            metadata[name] = item.get('Value')

    if callback.get('ResultCode') == 0:
        payment.status = 'paid'
        payment.transaction_reference = str(metadata.get('MpesaReceiptNumber') or payment.transaction_reference or '')
        payment.phone_number = str(metadata.get('PhoneNumber') or payment.phone_number or '')
        payment.paid_at = timezone.localtime()
        payment.failure_reason = ''
        payment.save(update_fields=['status', 'transaction_reference', 'phone_number', 'paid_at', 'failure_reason', 'updated_at'])
        payment.booking.payment_status = 'paid'
        if payment.transaction_reference:
            payment.booking.payment_intent_id = payment.transaction_reference
            payment.booking.save(update_fields=['payment_status', 'payment_intent_id', 'updated_at'])
        else:
            payment.booking.save(update_fields=['payment_status', 'updated_at'])
        _announce_booking_update(payment.booking, message='payment-updated')
    else:
        payment.status = 'failed'
        payment.failure_reason = callback.get('ResultDesc', 'M-Pesa payment failed.')
        payment.save(update_fields=['status', 'failure_reason', 'updated_at'])
        payment.booking.payment_status = 'failed'
        payment.booking.save(update_fields=['payment_status', 'updated_at'])
        _announce_booking_update(payment.booking, message='payment-updated')

    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Accepted'})
