from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    """
    A custom user model that extends Django's AbstractUser.
    This is the central user model for the entire project.

    """

    is_host = models.BooleanField(default=False)
    is_guest = models.BooleanField(default=False)
    
    USER_TYPES = (
        ('host', 'Host'),
        ('guest', 'Guest'),
    )
    user_type = models.CharField(max_length=10, choices=USER_TYPES)
    phone_number = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    
    
    
    
    # You can add more fields here if needed for all users
    # For example, a phone number field, etc.
    

    def __str__(self):
        return self.username
