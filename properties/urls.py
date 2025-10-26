from django.urls import path
from . import views

app_name = 'properties'

urlpatterns = [
    # Example: path('', views.property_list, name='property_list'),
    # Add your property-related URLs here
    path('', views.property_search, name='property_search'),
    path('<int:property_id>/', views.PropertyDetailView.as_view(), name='property_detail'),

]