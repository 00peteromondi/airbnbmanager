from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

# Get the custom user model dynamically.
CustomUser = get_user_model()

class CustomUserBackend(ModelBackend):
    """
    A custom authentication backend that authenticates against the CustomUser model.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            user = CustomUser.objects.get(username=username)
        except CustomUser.DoesNotExist:
            return None
        
        if user.check_password(password):
            return user
        return None
    
    def get_user(self, user_id):
        try:
            return CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return None
