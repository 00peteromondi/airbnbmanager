from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'users'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    path('role-selection/', views.role_selection, name='role_selection'),
    path('switch-role/<str:role>/', views.switch_role, name='switch_role'),
    path('get-active-role/', views.get_active_role, name='get_active_role'),
    path('profile/', views.profile, name='profile'),
]
