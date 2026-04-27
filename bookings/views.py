import json
from datetime import datetime, time
from decimal import Decimal
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import CreateView, ListView, UpdateView
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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


def _build_guest_plan(booking, user, today):
    checklist = [
        {'label': 'Payment settled', 'done': booking.payment_status == 'paid'},
        {'label': 'Email and phone verified', 'done': user.email_verified and user.phone_verified},
        {'label': 'Government ID ready', 'done': user.government_id_status == 'verified'},
        {'label': 'Profile phone available', 'done': bool(user.phone_number)},
        {'label': 'Arrival still ahead', 'done': booking.check_in_date >= today},
    ]
    return {
        'booking': booking,
        'checklist': checklist,
        'ready_count': sum(1 for item in checklist if item['done']),
        'checklist_total': len(checklist),
        'countdown_days': max((booking.check_in_date - today).days, 0),
    }


def _build_pdf_response(filename, title, subtitle, sections):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    palette = {
        'primary': colors.HexColor('#cf2338'),
        'primary_dark': colors.HexColor('#7f1022'),
        'orange': colors.HexColor('#f97316'),
        'soft': colors.HexColor('#fff4ef'),
        'line': colors.HexColor('#e2e8f0'),
        'text': colors.HexColor('#1f2937'),
        'muted': colors.HexColor('#64748b'),
        'green': colors.HexColor('#15803d'),
        'amber': colors.HexColor('#b45309'),
    }
    palette_hex = {
        'green': '#15803d',
        'amber': '#b45309',
    }
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='BayTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=23,
        leading=28,
        textColor=colors.white,
        alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name='BaySubtitle',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=14,
        textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        name='BaySection',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=palette['primary_dark'],
    ))
    styles.add(ParagraphStyle(
        name='BayBody',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10.2,
        leading=14.5,
        textColor=palette['text'],
    ))
    styles.add(ParagraphStyle(
        name='BayMeta',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9.4,
        leading=13,
        textColor=palette['muted'],
    ))
    styles.add(ParagraphStyle(
        name='BayChecklist',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10,
        leading=13.5,
        textColor=palette['text'],
    ))

    story = []
    header = Table([[Paragraph(f'BayStays<br/><font size="10">{title}</font>', styles['BayTitle']), Paragraph(subtitle, styles['BaySubtitle'])]], colWidths=[108 * mm, 58 * mm])
    header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), palette['primary']),
        ('BOX', (0, 0), (-1, -1), 0, palette['primary']),
        ('LEFTPADDING', (0, 0), (-1, -1), 16),
        ('RIGHTPADDING', (0, 0), (-1, -1), 16),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 16),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(header)
    story.append(Spacer(1, 10))

    for section in sections:
        story.append(Paragraph(section['heading'], styles['BaySection']))
        story.append(Spacer(1, 4))
        if section.get('intro'):
            story.append(Paragraph(section['intro'], styles['BayBody']))
            story.append(Spacer(1, 6))
        if section.get('rows'):
            data = []
            for label, value in section['rows']:
                data.append([
                    Paragraph(f'<b>{label}</b>', styles['BayMeta']),
                    Paragraph(str(value), styles['BayBody']),
                ])
            table = Table(data, colWidths=[48 * mm, 118 * mm])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), palette['soft']),
                ('BOX', (0, 0), (-1, -1), 0.6, palette['line']),
                ('INNERGRID', (0, 0), (-1, -1), 0.6, palette['line']),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(table)
            story.append(Spacer(1, 8))
        if section.get('checklist'):
            checklist_rows = []
            for item in section['checklist']:
                state = 'Ready' if item['done'] else 'Needs action'
                tone = palette_hex['green'] if item['done'] else palette_hex['amber']
                checklist_rows.append([
                    Paragraph(f'<font color="{tone}">{"&#10003;" if item["done"] else "&#9675;"}</font>', styles['BayChecklist']),
                    Paragraph(item['label'], styles['BayChecklist']),
                    Paragraph(f'<font color="{tone}">{state}</font>', styles['BayChecklist']),
                ])
            checklist_table = Table(checklist_rows, colWidths=[10 * mm, 110 * mm, 46 * mm])
            checklist_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('BOX', (0, 0), (-1, -1), 0.6, palette['line']),
                ('INNERGRID', (0, 0), (-1, -1), 0.6, palette['line']),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            story.append(checklist_table)
            story.append(Spacer(1, 8))
        if section.get('note'):
            note = Table([[Paragraph(section['note'], styles['BayBody'])]], colWidths=[166 * mm])
            note.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fef3c7')),
                ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#f59e0b')),
                ('LEFTPADDING', (0, 0), (-1, -1), 10),
                ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(note)
            story.append(Spacer(1, 10))

    doc.build(story)
    response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename=\"{filename}\"'
    return response


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


def _guest_payments_center_context(user):
    booking_context = _guest_bookings_context(user)
    bookings = booking_context['bookings']
    payment_history = BookingPayment.objects.filter(guest=user).select_related('booking', 'booking__property', 'host')
    today = timezone.localdate()
    active_bookings = bookings.exclude(status='cancelled')
    upcoming_bookings = active_bookings.filter(check_out_date__gte=today).order_by('check_in_date')
    unpaid_bookings = active_bookings.filter(payment_status__in=['pending', 'initiated', 'failed']).order_by('check_in_date')
    next_trip = upcoming_bookings.first()
    days_to_next_trip = None
    if next_trip:
        days_to_next_trip = max((next_trip.check_in_date - today).days, 0)
    unpaid_trip_plans = [_build_guest_plan(booking, user, today) for booking in unpaid_bookings[:6]]
    travel_timeline_plans = [_build_guest_plan(booking, user, today) for booking in upcoming_bookings[:6]]
    next_trip_plan = _build_guest_plan(next_trip, user, today) if next_trip else None

    return {
        **booking_context,
        'payment_center_summary': {
            'upcoming_spend': _coalesce_decimal(upcoming_bookings.aggregate(total=Sum('total_price'))['total']),
            'settled_total': _coalesce_decimal(payment_history.filter(status='paid').aggregate(total=Sum('amount'))['total']),
            'outstanding_total': _coalesce_decimal(unpaid_bookings.aggregate(total=Sum('total_price'))['total']),
            'failed_total': _coalesce_decimal(payment_history.filter(status='failed').aggregate(total=Sum('amount'))['total']),
        },
        'unpaid_bookings': unpaid_bookings[:6],
        'unpaid_trip_plans': unpaid_trip_plans,
        'payment_history_full': payment_history[:12],
        'next_trip': next_trip,
        'next_trip_plan': next_trip_plan,
        'days_to_next_trip': days_to_next_trip,
        'travel_timeline': upcoming_bookings[:6],
        'travel_timeline_plans': travel_timeline_plans,
        'travel_utilities': [
            {
                'icon': 'fa-mobile-screen-button',
                'title': 'Keep M-Pesa ready',
                'detail': 'Outstanding stays can be settled from this page with your saved or preferred phone number.',
            },
            {
                'icon': 'fa-id-card',
                'title': 'Verify before you travel',
                'detail': 'Verified email, phone, and ID keep support and host coordination smoother around arrival.',
            },
            {
                'icon': 'fa-route',
                'title': 'Plan the next arrival',
                'detail': 'Use your next confirmed stay and payment state together so nothing is left until check-in day.',
            },
        ],
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

        if property_obj.owner_id == self.request.user.id:
            form.add_error(None, 'Hosts cannot book their own listing from BayStays. Use availability controls or manual guest coordination instead.')
            return self.form_invalid(form, unavailable_ranges=unavailable_ranges)

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
def guest_payments_center(request):
    context = _guest_payments_center_context(request.user)
    return render(request, 'bookings/payments_center.html', context)


@login_required
def download_trip_summary(request, booking_id):
    booking = get_object_or_404(Booking.objects.select_related('property'), id=booking_id, guest=request.user)
    today = timezone.localdate()
    plan = _build_guest_plan(booking, request.user, today)
    nights = (booking.check_out_date - booking.check_in_date).days
    return _build_pdf_response(
        filename=f'baystays-trip-{booking.id}.pdf',
        title='Trip Summary',
        subtitle='Lakeside hosting travel brief',
        sections=[
            {
                'heading': 'Stay snapshot',
                'intro': 'A polished summary of the stay, payment state, and arrival details tied to this BayStays booking.',
                'rows': [
                    ('Property', booking.property.name),
                    ('Location', f'{booking.property.city}, {booking.property.country}'),
                    ('Check-in', booking.check_in_date),
                    ('Check-out', booking.check_out_date),
                    ('Nights', nights),
                    ('Guests', booking.num_guests),
                    ('Booking status', booking.get_status_display()),
                    ('Payment status', booking.get_payment_status_display()),
                    ('Total price', f'KES {booking.total_price}'),
                ],
            },
            {
                'heading': 'Pre-arrival checklist',
                'checklist': plan['checklist'],
                'note': f"Special requests: {booking.special_requests or 'None recorded.'}",
            },
        ],
    )


@login_required
def download_booking_reminder(request, booking_id):
    booking = get_object_or_404(Booking.objects.select_related('property'), id=booking_id, guest=request.user)
    check_in_time = getattr(booking.property, 'check_in_time', None) or time(15, 0)
    check_out_time = getattr(booking.property, 'check_out_time', None) or time(11, 0)
    start = datetime.combine(booking.check_in_date, check_in_time)
    end = datetime.combine(booking.check_out_date, check_out_time)
    description = (
        f"BayStays stay at {booking.property.name}\\n"
        f"Location: {booking.property.city}, {booking.property.country}\\n"
        f"Payment status: {booking.get_payment_status_display()}\\n"
        f"Booking status: {booking.get_status_display()}"
    )
    ics = "\r\n".join([
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//BayStays//Trip Reminder//EN",
        "BEGIN:VEVENT",
        f"UID:baystays-booking-{booking.id}@baystays",
        f"DTSTAMP:{timezone.now().strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}",
        f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}",
        f"SUMMARY:BayStays stay - {booking.property.name}",
        f"DESCRIPTION:{description}",
        f"LOCATION:{booking.property.city}, {booking.property.country}",
        "END:VEVENT",
        "END:VCALENDAR",
    ])
    response = HttpResponse(ics, content_type='text/calendar; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename=\"baystays-booking-{booking.id}.ics\"'
    return response


@login_required
def download_payment_receipt(request, payment_id):
    payment = get_object_or_404(
        BookingPayment.objects.select_related('booking', 'booking__property', 'guest', 'host'),
        id=payment_id,
        guest=request.user,
    )
    booking = payment.booking
    fee_state = 'Settled' if payment.status == 'paid' else 'Awaiting settlement'
    return _build_pdf_response(
        filename=f'baystays-receipt-{payment.id}.pdf',
        title='Payment Receipt',
        subtitle='BayStays M-Pesa payment confirmation',
        sections=[
            {
                'heading': 'Receipt summary',
                'intro': 'A downloadable record of the guest-side payment captured against this BayStays booking.',
                'rows': [
                    ('Receipt ID', f'BST-{payment.id:05d}'),
                    ('Property', booking.property.name),
                    ('Location', f'{booking.property.city}, {booking.property.country}'),
                    ('Guest', payment.guest.get_display_name()),
                    ('Host', payment.host.get_display_name()),
                    ('Payment provider', payment.get_provider_display()),
                    ('Amount', f'KES {payment.amount}'),
                    ('Phone number', payment.phone_number or 'Not supplied'),
                    ('Transaction reference', payment.transaction_reference or payment.checkout_request_id or 'Pending'),
                    ('Payment state', payment.get_status_display()),
                    ('Booking state', booking.get_status_display()),
                    ('Paid at', payment.paid_at or payment.created_at),
                ],
            },
            {
                'heading': 'Booking coverage',
                'rows': [
                    ('Check-in', booking.check_in_date),
                    ('Check-out', booking.check_out_date),
                    ('Guests', booking.num_guests),
                    ('Total booking price', f'KES {booking.total_price}'),
                    ('Receipt note', fee_state),
                ],
                'note': f"Failure note: {payment.failure_reason or 'No failure was recorded for this transaction.'}",
            },
        ],
    )


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
