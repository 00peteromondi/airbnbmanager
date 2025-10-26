from django.shortcuts import redirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin

class RoleSelectionMiddleware(MiddlewareMixin):
    """
    Middleware to handle role selection for new users
    """
    def process_request(self, request):
        if (request.user.is_authenticated and 
            not request.user.role and 
            not any([
                request.path.startswith('/users/role-selection/'),
                request.path.startswith('/admin/'),
                request.path.startswith('/static/'),
                request.path.startswith('/media/'),
                request.path == reverse('users:logout'),
            ])):
            return redirect('users:role_selection')