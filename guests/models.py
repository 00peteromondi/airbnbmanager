from django.db import models
from django.conf import settings

class Guest(models.Model):
    # Use settings.AUTH_USER_MODEL to reference your custom user model
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    # Add any other fields specific to a guest profile here
    # For example, you might want to store their full name, address, etc.
    full_name = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f"Guest Profile for {self.user.username}"
