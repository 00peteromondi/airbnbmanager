from django.urls import path, include
from django.contrib import admin
from django.views.generic import RedirectView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls', namespace='core')),
    path('guests/', include('guests.urls', namespace='guests')),
    path('hosts/', include('hosts.urls', namespace='hosts')),
    path('properties/', include('properties.urls', namespace='properties')),
    path('bookings/', include('bookings.urls', namespace='bookings')),
    path('users/', include('users.urls', namespace='users')),
    
    # Redirect common auth URLs to appropriate pages
    path('login/', RedirectView.as_view(pattern_name='guests:guest_login', permanent=False)),
    path('register/', RedirectView.as_view(pattern_name='guests:guest_signup', permanent=False)),
    path('signup/', RedirectView.as_view(pattern_name='guests:guest_signup', permanent=False)),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Add static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)  