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

    # Property management routes
    path('properties/', views.my_listings, name='my_listings'),
    path('properties/add/', views.add_listing, name='add_listing'),
    path('properties/<int:property_id>/edit/', views.edit_listing, name='edit_listing'),
    path('properties/<int:property_id>/delete/', views.delete_listing, name='delete_listing'),
    path('properties/<int:property_id>/', views.view_listing, name='view_listing'),
    
    # Booking management
    path('bookings/', views.property_bookings, name='property_bookings'),

    # Default root URL
    path('', views.dashboard, name='home'),
]