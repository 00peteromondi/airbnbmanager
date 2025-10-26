from django.shortcuts import redirect
from django.contrib import messages
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

class AuthenticationGuardMiddleware(MiddlewareMixin):
    """
    Middleware to prevent authenticated users from accessing auth pages
    and handle role-based redirects
    """
    
    # Pages that should ONLY be accessible to logged-out users
    AUTH_PAGES = [
        '/guests/login/',
        '/guests/signup/',
        '/hosts/login/',
        '/hosts/register/',
        '/users/login/',
        '/users/register/',
    ]
    
    # Pages that require specific roles
    GUEST_ONLY_PAGES = [
        '/guests/dashboard/',
        '/guests/properties/',
        '/bookings/',  # All booking pages
    ]
    
    HOST_ONLY_PAGES = [
        '/hosts/dashboard/',
        '/hosts/listings/',
        '/hosts/listings/add/',
        '/hosts/listings/edit/',
        '/hosts/listings/delete/',
    ]

    def process_request(self, request):
        # Skip for static files and admin
        if (request.path.startswith('/static/') or 
            request.path.startswith('/media/') or 
            request.path.startswith('/admin/')):
            return None

        # Check if user is authenticated
        if request.user.is_authenticated:
            # Prevent access to auth pages (login/register)
            if any(request.path.startswith(auth_page) for auth_page in self.AUTH_PAGES):
                messages.info(request, "You're already logged in!")
                return redirect(self._get_redirect_url(request))
            
            # Check role-based access
            return self._check_role_access(request)
        else:
            # For non-authenticated users, allow access to auth pages
            # but redirect from protected pages
            if any(request.path.startswith(protected) for protected in self.GUEST_ONLY_PAGES + self.HOST_ONLY_PAGES):
                messages.error(request, "Please log in to access this page.")
                return redirect('guests:guest_login')

        return None

    def _check_role_access(self, request):
        """Check if user has permission to access the current page based on role"""
        user = request.user
        
        # Guest-only pages check
        if any(request.path.startswith(page) for page in self.GUEST_ONLY_PAGES):
            if not (user.role in ['guest', 'both']):
                messages.error(request, "This page is only available for guests.")
                return redirect('core:home')
            
            # If user has both roles but is in host mode
            if (user.role == 'both' and 
                request.session.get('active_role') == 'host'):
                messages.info(request, "Please switch to guest mode to access this page.")
                return redirect('hosts:dashboard')

        # Host-only pages check
        if any(request.path.startswith(page) for page in self.HOST_ONLY_PAGES):
            if not (user.role in ['host', 'both']):
                messages.error(request, "This page is only available for hosts.")
                return redirect('core:home')
            
            # If user has both roles but is in guest mode
            if (user.role == 'both' and 
                request.session.get('active_role') == 'guest'):
                messages.info(request, "Please switch to host mode to access this page.")
                return redirect('guests:guest_dashboard')
        
        return None

    def _get_redirect_url(self, request):
        """Determine the best redirect URL based on user role and active session"""
        user = request.user
        
        if not user.role:
            return 'users:role_selection'
        
        if user.role == 'both':
            active_role = request.session.get('active_role', 'guest')
            return 'hosts:dashboard' if active_role == 'host' else 'guests:guest_dashboard'
        elif user.role == 'host':
            return 'hosts:dashboard'
        else:  # guest
            return 'guests:guest_dashboard'

class SessionTimeoutMiddleware(MiddlewareMixin):
    """
    Middleware to handle session timeout and automatic logout
    """
    
    def process_request(self, request):
        if request.user.is_authenticated:
            # Update session on every request to prevent timeout during active use
            request.session.modified = True