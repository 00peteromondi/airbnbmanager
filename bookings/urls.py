from django.urls import path
from . import views

urlpatterns = [
    # Example: path('', views.property_list, name='property_list'),
    # Add your property-related URLs here
    path('', views.UserBookingListView.as_view(), name='booking_list'),
]