from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from .models import Booking
from .forms import BookingForm
from properties.models import Property
from django.urls import reverse

class BookingCreateView(LoginRequiredMixin, CreateView):
    model = Booking
    form_class = BookingForm
    
    def form_valid(self, form):
        property = get_object_or_404(Property, pk=self.kwargs['property_id'])
        
        # Check availability
        overlapping_bookings = Booking.objects.filter(
            property=property,
            check_in_date__lt=form.instance.check_out_date,
            check_out_date__gt=form.instance.check_in_date,
            status__in=['confirmed', 'pending']
        )
        
        if overlapping_bookings.exists():
            form.add_error(None, "These dates are not available")
            return self.form_invalid(form)
        
        # Validate check-in is at least tomorrow
        if form.instance.check_in_date <= timezone.now().date():
            form.add_error('check_in_date', "Check-in must be at least 1 day in advance")
            return self.form_invalid(form)
        
        # Validate number of guests
        if form.instance.num_guests > property.max_guests:
            form.add_error('num_guests', f"This property accommodates maximum {property.max_guests} guests")
            return self.form_invalid(form)
        
        # Calculate total price
        num_nights = (form.instance.check_out_date - form.instance.check_in_date).days
        form.instance.total_price = num_nights * property.price_per_night
        form.instance.guest = self.request.user
        form.instance.property = property
        
        messages.success(self.request, "Booking request submitted successfully!")
        return super().form_valid(form)
    
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
        
        # Add statistics to context
        context['stats'] = {
            'total_bookings': bookings.count(),
            'pending_bookings': bookings.filter(status='pending').count(),
            'confirmed_bookings': bookings.filter(status='confirmed').count(),
            'cancelled_bookings': bookings.filter(status='cancelled').count(),
        }
        return context

def update_booking_status(request, booking_id, status):
    """Update booking status (for hosts)"""
    if request.method == 'POST':
        booking = get_object_or_404(Booking, id=booking_id, property__owner=request.user)
        valid_statuses = ['confirmed', 'cancelled']
        
        if status in valid_statuses:
            booking.status = status
            booking.save()
            
            messages.success(request, f"Booking has been {status} successfully!")
        else:
            messages.error(request, "Invalid status")
    
    return redirect('hosts:owner_bookings')

def update_booking_notes(request, booking_id):
    """Update admin notes for a booking"""
    if request.method == 'POST':
        booking = get_object_or_404(Booking, id=booking_id, property__owner=request.user)
        booking.admin_notes = request.POST.get('admin_notes', '')
        booking.save()
        
        messages.success(request, "Notes updated successfully!")
    
    return redirect('hosts:owner_bookings')

class BookingUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Booking
    fields = ['status', 'admin_notes']

    def test_func(self):
        return self.request.user == self.get_object().property.owner

    def form_valid(self, form):
        booking = self.get_object()
        if booking.status != form.cleaned_data['status']:
            messages.info(self.request, f"Booking status changed to {form.cleaned_data['status']}")
        return super().form_valid(form)


class UserBookingListView(LoginRequiredMixin, ListView):
    model = Booking
    template_name = 'bookings/user_bookings.html'
    context_object_name = 'bookings'

    def get_queryset(self):
        return Booking.objects.filter(guest=self.request.user).order_by('-created_at')

