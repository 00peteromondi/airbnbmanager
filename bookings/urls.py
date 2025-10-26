from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    # Example: path('', views.property_list, name='property_list'),
    # Add your property-related URLs here
    path('', views.UserBookingListView.as_view(), name='booking_list'),
    path('create/<int:property_id>/', views.BookingCreateView.as_view(), name='create_booking'),
    path('update-status/<int:booking_id>/<str:status>/', views.update_booking_status, name='update_booking_status'),
    path('update-notes/<int:booking_id>/', views.update_booking_notes, name='update_booking_notes'),
]