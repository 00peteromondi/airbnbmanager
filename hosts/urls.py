from django.urls import path
from . import views
from django.contrib.auth.views import LoginView # Import Django's built-in login view

app_name = 'hosts'  # Namespace for the hosts app   

urlpatterns = [
    # Main authentication and dashboard routes
    path('register/', views.register_host, name='register'),
    path('login/', LoginView.as_view(template_name='hosts/login.html'), name='login'),
    path('logout/', views.logout_host, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # Listing management routes
    path('listings/', views.my_listings, name='my_listings'),
    path('listings/add/', views.add_listing, name='add_listing'),
    # You can add URLs for edit and delete listings here
    path('listings/<int:listing_id>/edit/', views.edit_listing, name='edit_listing'),
    path('listings/<int:listing_id>/delete/', views.delete_listing, name='delete_listing'),
    # URL for viewing a specific listing (if needed)
    path('listings/<int:listing_id>/', views.view_listing, name='view_listing'),

    # Default root URL
    path('', views.dashboard, name='home'),
]

