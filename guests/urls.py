from django.urls import path
from . import views
from .views import GuestSignUpView, GuestLoginView

app_name = 'guests'

urlpatterns = [
    path('signup/', GuestSignUpView.as_view(), name='guest_signup'),
    path('login/', GuestLoginView.as_view(), name='guest_login'),
    path('logout/', views.guest_logout_view, name='guest_logout'),
    path('dashboard/', views.guest_dashboard_view, name='guest_dashboard'),
    path('properties/', views.guest_properties_view, name='guest_properties'),
]
