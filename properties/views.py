from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import Property
from bookings.models import Booking
from django.shortcuts import get_object_or_404, render, redirect


from bookings.forms import BookingForm
from django.db.models import Sum
from django.utils import timezone
from django.db.models import Q
from datetime import datetime
from bookings.utils import check_property_availability, get_available_properties
from django.contrib.auth.decorators import login_required

class PropertyListView(ListView):
    model = Property
    context_object_name = 'properties'

class PropertyCreateView(LoginRequiredMixin, CreateView):
    model = Property
    fields = ['name', 'description', 'property_type', 'address', 'price_per_night',
              'max_guests', 'bedrooms', 'amenities', 'check_in_time', 'check_out_time']

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

class PropertyUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Property
    fields = ['name', 'description', 'property_type', 'address', 'price_per_night',
              'max_guests', 'bedrooms', 'amenities', 'check_in_time', 'check_out_time', 'is_active']

    def test_func(self):
        property = self.get_object()
        return self.request.user == property.owner

class PropertyDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Property
    success_url = '/'

    def test_func(self):
        property = self.get_object()
        return self.request.user == property.owner



class PropertyDetailView(DetailView):
    model = Property
    context_object_name = 'property'
    pk_url_kwarg = 'property_id'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['booking_form'] = BookingForm(initial={
            'property': self.object,
            'num_guests': 1
        })
        # Add guest range for the select dropdown
        context['guest_range'] = range(1, self.object.max_guests + 1)
        
        # Add amenities in a format that's easy to display
        context['amenities_display'] = [
            (amenity, dict(Property.AMENITY_CHOICES).get(amenity, amenity))
            for amenity in self.object.amenities
        ]
        return context

from django.db.models import Q
from datetime import datetime

def property_search(request):
    properties = Property.objects.filter(is_active=True)

    # Search query
    query = request.GET.get('q')
    if query:
        properties = properties.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(address__icontains=query) |
            Q(amenities__icontains=query)
        )

    # Property type filter
    property_type = request.GET.get('property_type')
    if property_type:
        properties = properties.filter(property_type=property_type)

    # Price range
    min_price = request.GET.get('min_price')
    if min_price:
        properties = properties.filter(price_per_night__gte=min_price)

    max_price = request.GET.get('max_price')
    if max_price:
        properties = properties.filter(price_per_night__lte=max_price)

    # Guests
    guests = request.GET.get('guests')
    if guests:
        properties = properties.filter(max_guests__gte=guests)

    # Dates availability
    check_in = request.GET.get('check_in')
    check_out = request.GET.get('check_out')

    if check_in and check_out:
        try:
            check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
            check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()

            # Find properties that have conflicting bookings
            booked_properties = Booking.objects.filter(
                check_in_date__lt=check_out_date,
                check_out_date__gt=check_in_date,
                status__in=['confirmed', 'pending']
            ).values_list('property_id', flat=True)

            properties = properties.exclude(id__in=booked_properties)
        except ValueError:
            pass

    context = {
        'properties': properties,
        'search_query': query or '',
        'selected_type': property_type or '',
        'min_price': min_price or '',
        'max_price': max_price or '',
        'guests': guests or '',
        'check_in': check_in or '',
        'check_out': check_out or '',
    }

    return render(request, 'properties/property_list.html', context)

# hosts/views.py
@login_required
def dashboard(request):
    if not request.user.is_host:
        return redirect('hosts:become_host')
    
    properties = Property.objects.filter(owner=request.user)
    total_properties = properties.count()
    
    # Get booking statistics
    bookings = Booking.objects.filter(property__owner=request.user)
    total_bookings = bookings.count()
    pending_bookings = bookings.filter(status='pending').count()
    revenue = bookings.filter(status__in=['completed', 'checked_out']).aggregate(
        total_revenue=Sum('total_price')
    )['total_revenue'] or 0
    
    # Recent bookings
    recent_bookings = bookings.order_by('-created_at')[:5]
    
    context = {
        'total_properties': total_properties,
        'total_bookings': total_bookings,
        'pending_bookings': pending_bookings,
        'revenue': revenue,
        'recent_bookings': recent_bookings,
        'properties': properties,
    }
    return render(request, 'hosts/dashboard.html', context)
