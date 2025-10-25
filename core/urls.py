from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    # Example: path('', views.property_list, name='property_list'),
    # Add your property-related URLs here
    path('', views.home, name='home'),
    path('all_properties/', views.properties_list, name='properties_list'),
    path('hosts/', views.hosts_view, name='hosts'),
    
    # Placeholder paths for the other links in the hosts.html template.
    # You will need to create the corresponding views and templates for these.
    path('start-hosting/', views.start_hosting_view, name='start_hosting'),
    path('become-a-host-now/', views.become_a_host_now_view, name='become_a_host_now'),
]