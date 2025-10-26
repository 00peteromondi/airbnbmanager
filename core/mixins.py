from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin

from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.mixins import AccessMixin

class LogoutRequiredMixin(AccessMixin):
    """Verify that the current user is NOT authenticated."""
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            messages.info(request, "You're already logged in!")
            
            # Determine redirect URL based on user role
            if not request.user.role:
                return redirect('users:role_selection')
            elif request.user.role == 'both':
                active_role = request.session.get('active_role', 'guest')
                return redirect('hosts:dashboard' if active_role == 'host' else 'guests:guest_dashboard')
            elif request.user.role == 'host':
                return redirect('hosts:dashboard')
            else:
                return redirect('guests:guest_dashboard')
                
        return super().dispatch(request, *args, **kwargs)

class GuestRequiredMixin(AccessMixin):
    """Verify that the current user is a guest."""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to access this page.")
            return redirect('guests:guest_login')
        
        # Check if user has guest role
        if not (request.user.role in ['guest', 'both']):
            messages.error(request, "This page is only available for guests.")
            return redirect('core:home')
        
        # If user has both roles but is in host mode, redirect
        if (request.user.role == 'both' and 
            request.session.get('active_role') == 'host'):
            messages.info(request, "Please switch to guest mode to access this page.")
            return redirect('hosts:dashboard')
        
        return super().dispatch(request, *args, **kwargs)

class HostRequiredMixin(AccessMixin):
    """Verify that the current user is a host."""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to access this page.")
            return redirect('hosts:login')
        
        # Check if user has host role
        if not (request.user.role in ['host', 'both']):
            messages.error(request, "This page is only available for hosts.")
            return redirect('core:home')
        
        # If user has both roles but is in guest mode, redirect
        if (request.user.role == 'both' and 
            request.session.get('active_role') == 'guest'):
            messages.info(request, "Please switch to host mode to access this page.")
            return redirect('guests:guest_dashboard')
        
        return super().dispatch(request, *args, **kwargs)

class LoginRequiredMixin(AccessMixin):
    """Verify that the current user is authenticated."""
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to access this page.")
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)
    
class RoleBasedAccessMixin:
    """Mixins to handle role-based access control."""
    
    def get_redirect_url(self):
        """Get redirect URL based on user role."""
        user = self.request.user
        if user.role == 'host' or (user.role == 'both' and self.request.session.get('active_role') == 'host'):
            return 'hosts:dashboard'
        elif user.role == 'guest' or (user.role == 'both' and self.request.session.get('active_role') == 'guest'):
            return 'guests:guest_dashboard'
        else:
            return 'core:home'
        
class UserPassesTestMixin(AccessMixin):
    """Verify that the current user passes a test condition."""
    
    def test_func(self):
        """Override this method to define the test condition."""
        return False  # Default to False, must be overridden
    
    def dispatch(self, request, *args, **kwargs):
        if not self.test_func():
            messages.error(request, "You do not have permission to access this page.")
            return self.handle_no_permission()
        return super().dispatch(request, *args, **kwargs)