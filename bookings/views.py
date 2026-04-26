from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.generic import CreateView, ListView, UpdateView

from properties.models import Property

from .forms import BookingForm
from .models import Booking


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


def _guest_bookings_context(user):
    bookings = Booking.objects.filter(guest=user).select_related('property').order_by('-created_at')
    today = timezone.now().date()
    active_bookings = bookings.exclude(status='cancelled')
    latest_update = bookings.order_by('-updated_at').values_list('updated_at', flat=True).first()
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
        'can_manage_any_booking': bookings.filter(
            status__in=['pending', 'confirmed'],
            check_in_date__gt=today,
        ).exists(),
        'live_version': f"{bookings.count()}:{latest_update.isoformat() if latest_update else 'none'}",
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

        if form.instance.check_in_date <= timezone.now().date():
            form.add_error('check_in_date', 'Check-in must be at least 1 day in advance')
            return self.form_invalid(form, unavailable_ranges=unavailable_ranges)

        if form.instance.num_guests > property_obj.max_guests:
            form.add_error('num_guests', f'This property accommodates maximum {property_obj.max_guests} guests')
            return self.form_invalid(form, unavailable_ranges=unavailable_ranges)

        num_nights = (form.instance.check_out_date - form.instance.check_in_date).days
        form.instance.total_price = num_nights * property_obj.price_per_night
        form.instance.guest = self.request.user
        form.instance.property = property_obj

        response = super().form_valid(form)
        messages.success(self.request, 'Booking request submitted successfully!')
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'ok': True,
                'message': 'Booking request submitted successfully.',
                'redirect_url': reverse('bookings:booking_list'),
                'total_price': str(self.object.total_price),
                'status': self.object.status,
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
    if booking.check_in_date <= timezone.now().date():
        messages.error(request, 'This booking can no longer be cancelled from your account because the stay has already started.')
        return redirect('bookings:booking_list')

    booking.status = 'cancelled'
    booking.save(update_fields=['status', 'updated_at'])
    messages.success(request, f'{booking.property.name} has been cancelled.')
    return redirect('bookings:booking_list')


@login_required
def reschedule_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, guest=request.user)
    if booking.status not in ['pending', 'confirmed']:
        messages.error(request, 'Only active bookings can be rescheduled.')
        return redirect('bookings:booking_list')
    if booking.check_in_date <= timezone.now().date():
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
            elif rescheduled.check_in_date <= timezone.now().date():
                form.add_error('check_in_date', 'Check-in must be at least 1 day in advance')
            elif rescheduled.num_guests > booking.property.max_guests:
                form.add_error('num_guests', f'This property accommodates maximum {booking.property.max_guests} guests')
            else:
                nights = (rescheduled.check_out_date - rescheduled.check_in_date).days
                rescheduled.total_price = nights * booking.property.price_per_night
                rescheduled.save()
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
