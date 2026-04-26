from django.urls import path
from . import views
from django.contrib.auth.views import LoginView

app_name = 'hosts'

urlpatterns = [
    # Main authentication and dashboard routes
    path('register/', views.HostRegistrationView.as_view(), name='register'),
    path('login/', LoginView.as_view(template_name='hosts/login.html'), name='login'),
    path('logout/', views.logout_host, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/live/', views.dashboard_live, name='dashboard_live'),

    # Property management routes
    path('properties/', views.my_listings, name='my_listings'),
    path('properties/live/', views.my_listings_live, name='my_listings_live'),
    path('properties/add/', views.add_listing, name='add_listing'),
    path('properties/<int:property_id>/toggle-status/', views.toggle_listing_status, name='toggle_listing_status'),
    path('properties/<int:property_id>/edit/', views.edit_listing, name='edit_listing'),
    path('properties/<int:property_id>/delete/', views.delete_listing, name='delete_listing'),
    path('properties/<int:property_id>/', views.view_listing, name='view_listing'),
    
    # Booking management
    path('bookings/', views.property_bookings, name='property_bookings'),
    path('bookings/live/', views.property_bookings_live, name='property_bookings_live'),
    path('bookings/<int:booking_id>/<str:status>/', views.update_booking_status, name='update_booking_status'),
    path('finance/withdrawals/request/', views.request_withdrawal, name='request_withdrawal'),

    # Default root URL
    path('', views.dashboard, name='home'),
]
