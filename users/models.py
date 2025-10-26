from django.contrib.auth.models import AbstractUser
from django.db import models
from cloudinary.models import CloudinaryField
from django.utils import timezone

class CustomUser(AbstractUser):
    # Role system
    ROLE_CHOICES = (
        ('guest', 'Guest'),
        ('host', 'Host'),
        ('both', 'Both Host and Guest'),
    )
    
    role = models.CharField(
        max_length=10, 
        choices=ROLE_CHOICES, 
        default='guest'
    )
    
    # Profile information
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    profile_picture = CloudinaryField(
        'profile_picture',
        folder='airbnb_manager/profiles/',
        transformation={'quality': 'auto', 'width': 300, 'height': 300, 'crop': 'fill'},
        default=None,
        blank=True,
        null=True
    )
    date_of_birth = models.DateField(blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    
    # Address information
    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    
    # Verification fields
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'auth_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return f"{self.username} ({self.email})"
    
    # Property methods for easy role checking
    @property
    def is_guest_user(self):
        return self.role in ['guest', 'both']
    
    @property
    def is_host_user(self):
        return self.role in ['host', 'both']
    
    def get_display_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def save(self, *args, **kwargs):
        # Ensure email is lowercase
        if self.email:
            self.email = self.email.lower()
        
        # Set username to email if not set
        if not self.username and self.email:
            self.username = self.email
        
        super().save(*args, **kwargs)

class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='profile')
    
    # Social links
    website = models.URLField(blank=True)
    facebook = models.URLField(blank=True)
    twitter = models.URLField(blank=True)
    instagram = models.URLField(blank=True)
    linkedin = models.URLField(blank=True)
    
    # Notification preferences
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    promotional_emails = models.BooleanField(default=False)
    
    # Privacy settings
    profile_public = models.BooleanField(default=True)
    show_email = models.BooleanField(default=False)
    show_phone = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Profile for {self.user.username}"

# Signal to create user profile automatically
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()