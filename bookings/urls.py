from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    path('', views.UserBookingListView.as_view(), name='booking_list'),
    path('live/', views.booking_list_live, name='booking_list_live'),
    path('payments/mpesa/callback/', views.mpesa_callback, name='mpesa_callback'),
    path('create/<int:property_id>/', views.BookingCreateView.as_view(), name='create_booking'),
    path('<int:booking_id>/pay/', views.pay_booking, name='pay_booking'),
    path('<int:booking_id>/cancel/', views.cancel_booking, name='cancel_booking'),
    path('<int:booking_id>/reschedule/', views.reschedule_booking, name='reschedule_booking'),
    path('update-status/<int:booking_id>/<str:status>/', views.update_booking_status, name='update_booking_status'),
    path('update-notes/<int:booking_id>/', views.update_booking_notes, name='update_booking_notes'),
]
