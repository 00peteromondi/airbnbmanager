from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .models import Property, Review
from bookings.models import Booking
from django.shortcuts import get_object_or_404, render, redirect
from django.template.loader import render_to_string


from bookings.forms import BookingForm
from .forms import ReviewForm
from django.db.models import Sum, Max
from django.utils import timezone
from django.db.models import Q, Avg
from datetime import datetime
import json
from bookings.utils import check_property_availability, get_available_properties
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages

AMENITY_ICONS = {
    'wifi': 'fa-solid fa-wifi',
    'kitchen': 'fa-solid fa-kitchen-set',
    'parking': 'fa-solid fa-square-parking',
    'pool': 'fa-solid fa-person-swimming',
    'gym': 'fa-solid fa-dumbbell',
    'ac': 'fa-solid fa-fan',
    'heating': 'fa-solid fa-temperature-high',
    'tv': 'fa-solid fa-tv',
    'washer': 'fa-solid fa-soap',
    'dryer': 'fa-solid fa-wind',
    'breakfast': 'fa-solid fa-mug-hot',
    'workspace': 'fa-solid fa-laptop',
    'fireplace': 'fa-solid fa-fire',
    'balcony': 'fa-solid fa-umbrella-beach',
    'garden': 'fa-solid fa-seedling',
    'bbq': 'fa-solid fa-fire-burner',
    'hot_tub': 'fa-solid fa-hot-tub-person',
    'security': 'fa-solid fa-shield-halved',
    'elevator': 'fa-solid fa-elevator',
    'accessible': 'fa-solid fa-wheelchair',
}


def _property_detail_context_data(property_obj, user):
    booking_form = BookingForm(initial={'property': property_obj, 'num_guests': 1})
    booking_form.fields['num_guests'].widget.attrs.update({
        'min': 1,
        'max': property_obj.max_guests,
    })
    reviews = property_obj.reviews.select_related('user')
    user_review = None
    can_review = False
    existing_guest_bookings = Booking.objects.none()
    is_owner_viewing = False
    can_book_listing = property_obj.owner_id != getattr(user, 'id', None)
    if user.is_authenticated:
        is_owner_viewing = property_obj.owner_id == user.id
        user_review = reviews.filter(user=user).first()
        can_review = Booking.objects.filter(
            property=property_obj,
            guest=user,
        ).exclude(status='cancelled').exists()
        existing_guest_bookings = Booking.objects.filter(
            property=property_obj,
            guest=user,
        ).exclude(status='cancelled').order_by('-check_in_date')

    unavailable_bookings = Booking.objects.filter(
        property=property_obj,
        status__in=['confirmed', 'pending', 'checked_in']
    ).order_by('check_in_date')
    unavailable_periods_json = json.dumps([
        {
            'check_in': booking.check_in_date.isoformat(),
            'check_out': booking.check_out_date.isoformat(),
            'status': booking.status,
        }
        for booking in unavailable_bookings
    ])

    booking_latest = unavailable_bookings.order_by('-updated_at').values_list('updated_at', flat=True).first()
    review_latest = reviews.order_by('-updated_at').values_list('updated_at', flat=True).first()
    latest_update = max(
        [stamp for stamp in [property_obj.updated_at, booking_latest, review_latest] if stamp is not None],
        default=None,
    )

    return {
        'booking_form': booking_form,
        'review_form': ReviewForm(instance=user_review),
        'reviews': reviews[:6],
        'reviews_count': reviews.count(),
        'guest_range': range(1, property_obj.max_guests + 1),
        'can_review': can_review,
        'current_user_rating': user_review.rating if user_review else 0,
        'rating_choices': Review._meta.get_field('rating').choices,
        'is_owner_viewing': is_owner_viewing,
        'can_book_listing': can_book_listing,
        'existing_guest_bookings': existing_guest_bookings[:4],
        'has_existing_booking': existing_guest_bookings.exists(),
        'unavailable_periods': unavailable_bookings[:6],
        'unavailable_periods_json': unavailable_periods_json,
        'amenities_display': [
            (
                amenity,
                dict(Property.AMENITY_CHOICES).get(amenity, amenity),
                AMENITY_ICONS.get(amenity, 'fa-solid fa-circle-check'),
            )
            for amenity in property_obj.amenities
        ],
        'live_version': f"{property_obj.id}:{reviews.count()}:{unavailable_bookings.count()}:{latest_update.isoformat() if latest_update else 'none'}",
    }

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
        context.update(_property_detail_context_data(self.object, self.request.user))
        return context


def property_detail_live(request, property_id):
    property_obj = get_object_or_404(Property, pk=property_id, is_active=True)
    context = _property_detail_context_data(property_obj, request.user)
    return JsonResponse({
        'version': context['live_version'],
        'reviews_html': render_to_string('properties/_reviews_list.html', context, request=request),
        'availability_html': render_to_string('properties/_availability_panel.html', context, request=request),
        'reviews_count': context['reviews_count'],
        'average_rating': f"{property_obj.average_rating:.1f}",
        'unavailable_ranges': json.loads(context['unavailable_periods_json']),
    })


@login_required
def submit_review(request, property_id):
    property = get_object_or_404(Property, pk=property_id, is_active=True)
    if request.method != 'POST':
        return redirect('properties:property_detail', property_id=property.id)

    if not Booking.objects.filter(property=property, guest=request.user).exclude(status='cancelled').exists():
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'errors': {'review': ['You can only review stays you have booked.']}}, status=403)
        messages.error(request, "You can only review stays you have booked.")
        return redirect('properties:property_detail', property_id=property.id)

    review = Review.objects.filter(property=property, user=request.user).first()
    form = ReviewForm(request.POST, instance=review)
    if form.is_valid():
        review = form.save(commit=False)
        review.property = property
        review.user = request.user
        review.save()
        property.average_rating = property.reviews.aggregate(avg=Avg('rating'))['avg'] or 0
        property.save(update_fields=['average_rating'])
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'ok': True,
                'message': 'Review saved successfully.',
                'review_id': review.id,
                'rating': f"{review.rating:.1f}",
                'comment': review.comment,
                'reviewer': request.user.get_display_name(),
                'created_at': review.created_at.strftime('%b %d, %Y'),
                'reviews_count': property.reviews.count(),
                'average_rating': f"{property.average_rating:.1f}",
            })
        messages.success(request, "Review saved successfully.")
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
        messages.error(request, "Please review the rating details and try again.")
    return redirect('properties:property_detail', property_id=property.id)

from django.db.models import Q
from datetime import datetime

def property_search(request):
    properties = Property.objects.filter(is_active=True).select_related('owner').prefetch_related('images', 'reviews')

    # Search query
    query = request.GET.get('q', '').strip()
    if query:
        properties = properties.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(address__icontains=query) |
            Q(city__icontains=query) |
            Q(country__icontains=query)
        )

    # Property type filter
    property_type = request.GET.get('property_type', '').strip()
    if property_type:
        properties = properties.filter(property_type=property_type)

    # Price range
    min_price = request.GET.get('min_price', '').strip()
    if min_price:
        try:
            properties = properties.filter(price_per_night__gte=float(min_price))
        except (ValueError, TypeError):
            pass

    max_price = request.GET.get('max_price', '').strip()
    if max_price:
        try:
            properties = properties.filter(price_per_night__lte=float(max_price))
        except (ValueError, TypeError):
            pass

    # Guests
    guests = request.GET.get('guests', '').strip()
    if guests:
        try:
            properties = properties.filter(max_guests__gte=int(guests))
        except (ValueError, TypeError):
            pass

    # Dates availability
    check_in = request.GET.get('check_in', '').strip()
    check_out = request.GET.get('check_out', '').strip()

    if check_in and check_out:
        try:
            check_in_date = datetime.strptime(check_in, '%Y-%m-%d').date()
            check_out_date = datetime.strptime(check_out, '%Y-%m-%d').date()

            # Validate dates
            if check_in_date < check_out_date:
                # Find properties that have conflicting bookings
                booked_properties = Booking.objects.filter(
                    check_in_date__lt=check_out_date,
                    check_out_date__gt=check_in_date,
                    status__in=['confirmed', 'pending', 'checked_in']
                ).values_list('property_id', flat=True)

                properties = properties.exclude(id__in=booked_properties)
        except ValueError:
            pass

    # Sorting
    sort_by = request.GET.get('sort', 'recommended')
    if sort_by == 'price_low':
        properties = properties.order_by('price_per_night')
    elif sort_by == 'price_high':
        properties = properties.order_by('-price_per_night')
    elif sort_by == 'rating':
        properties = properties.order_by('-average_rating', '-id')
    else:  # recommended (default)
        properties = properties.order_by('-average_rating', '-id')

    # Get user's booked properties for status display
    user_booked_property_ids = []
    if request.user.is_authenticated and (request.user.role == 'guest' or request.user.role == 'both'):
        user_booked_property_ids = list(
            Booking.objects.filter(
                guest=request.user,
                status__in=['confirmed', 'checked_in', 'completed']
            ).values_list('property_id', flat=True).distinct()
        )

    # Get property types for filter dropdown
    property_types = dict(Property.PROPERTY_TYPES)

    context = {
        'properties': properties,
        'search_query': query,
        'selected_type': property_type,
        'min_price': min_price,
        'max_price': max_price,
        'guests': guests,
        'check_in': check_in,
        'check_out': check_out,
        'property_types': property_types,
        'user_booked_property_ids': user_booked_property_ids,
        'user_role': request.user.role if request.user.is_authenticated else 'anonymous',
    }

    return render(request, 'properties/property_list.html', context)
