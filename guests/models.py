from django.db import models
from django.conf import settings
from cloudinary.models import CloudinaryField

class Guest(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='guest_profile'
    )
    
    # Guest-specific fields
    full_name = models.CharField(max_length=200, blank=True)
    preferred_language = models.CharField(max_length=10, default='en')
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)
    
    # Guest preferences
    smoking = models.BooleanField(default=False)
    pets = models.BooleanField(default=False)
    children = models.BooleanField(default=False)
    
    # Verification documents
    government_id = CloudinaryField(
        'government_id',
        folder='airbnb_manager/verification/guests/',
        blank=True,
        null=True
    )
    id_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(blank=True, null=True)
    
    # Statistics
    total_bookings = models.PositiveIntegerField(default=0)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    member_since = models.DateTimeField(auto_now_add=True)
    
    # Loyalty program
    loyalty_points = models.PositiveIntegerField(default=0)
    loyalty_tier = models.CharField(
        max_length=20,
        choices=[
            ('bronze', 'Bronze'),
            ('silver', 'Silver'), 
            ('gold', 'Gold'),
            ('platinum', 'Platinum')
        ],
        default='bronze'
    )
    
    class Meta:
        verbose_name = 'Guest'
        verbose_name_plural = 'Guests'
    
    def __str__(self):
        return f"Guest: {self.user.get_display_name()}"
    
    def save(self, *args, **kwargs):
        if not self.full_name and self.user:
            self.full_name = self.user.get_full_name()
        super().save(*args, **kwargs)
    
    @property
    def is_verified(self):
        return self.id_verified
    
    def update_loyalty_tier(self):
        if self.total_bookings >= 50 or self.total_spent >= 10000:
            self.loyalty_tier = 'platinum'
        elif self.total_bookings >= 20 or self.total_spent >= 5000:
            self.loyalty_tier = 'gold'
        elif self.total_bookings >= 10 or self.total_spent >= 1000:
            self.loyalty_tier = 'silver'
        else:
            self.loyalty_tier = 'bronze'
        self.save()