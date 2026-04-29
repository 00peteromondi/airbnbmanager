from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import hub_views

app_name = 'users'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    path('role-selection/', views.role_selection, name='role_selection'),
    path('switch-role/<str:role>/', views.switch_role, name='switch_role'),
    path('get-active-role/', views.get_active_role, name='get_active_role'),
    path('profile/', views.profile, name='profile'),
    path('profile/send-email-code/', views.send_email_verification, name='send_email_verification'),
    path('profile/verify-email-code/', views.verify_email_code, name='verify_email_code'),
    path('profile/send-phone-code/', views.send_phone_verification, name='send_phone_verification'),
    path('profile/verify-phone-code/', views.verify_phone_code, name='verify_phone_code'),
    path('password-strength/', views.password_strength, name='password_strength'),
    path('notifications/', hub_views.notifications, name='notifications'),
    path('notifications/live/', hub_views.notifications_live, name='notifications_live'),
    path('notifications/<int:notification_id>/read/', hub_views.notification_mark_read, name='notification_mark_read'),
    path('notifications/read-all/', hub_views.notification_mark_all_read, name='notification_mark_all_read'),
    path('inbox/', hub_views.inbox, name='inbox'),
    path('inbox/live/', hub_views.inbox_live, name='inbox_live'),
    path('inbox/start/<int:booking_id>/', hub_views.start_booking_conversation, name='start_booking_conversation'),
    path('inbox/<int:conversation_id>/', hub_views.conversation_detail, name='conversation_detail'),
    path('inbox/<int:conversation_id>/thread/', hub_views.conversation_thread, name='conversation_thread'),
    path('assistant/', hub_views.assistant_hub, name='assistant_hub'),
    path('assistant/widget/', hub_views.assistant_widget, name='assistant_widget'),
    path('assistant/generate/', hub_views.assistant_generate, name='assistant_generate'),
]
