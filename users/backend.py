from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db import models

CustomUser = get_user_model()

class CustomUserBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Try to fetch user by username or email
            user = CustomUser.objects.get(
                models.Q(username=username) | 
                models.Q(email=username)
            )
            if user.check_password(password):
                return user
        except CustomUser.DoesNotExist:
            return None
    
    def get_user(self, user_id):
        try:
            return CustomUser.objects.get(pk=user_id)
        except CustomUser.DoesNotExist:
            return None