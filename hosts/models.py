from django.db import models
from django.conf import settings
from django.utils import timezone
from cloudinary.models import CloudinaryField
from users.models import CustomUser

class Host(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='host_profile'
    )
    
    # Host-specific information
    company_name = models.CharField(max_length=200, blank=True)
    tax_id = models.CharField(max_length=50, blank=True)
    hosting_since = models.DateTimeField(auto_now_add=True)
    
    # Bank/payment information
    bank_name = models.CharField(max_length=100, blank=True)
    account_number = models.CharField(max_length=50, blank=True)
    routing_number = models.CharField(max_length=50, blank=True)
    
    # Verification documents
    government_id = CloudinaryField(
        'government_id',
        folder='airbnb_manager/verification/hosts/',
        blank=True,
        null=True
    )
    business_license = CloudinaryField(
        'business_license',
        folder='airbnb_manager/verification/hosts/',
        blank=True,
        null=True
    )
    
    # Host verification status
    id_verified = models.BooleanField(default=False)
    address_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    fully_verified = models.BooleanField(default=False)
    
    # Host statistics
    total_properties = models.PositiveIntegerField(default=0)
    total_bookings = models.PositiveIntegerField(default=0)
    total_earnings = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    response_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    response_time = models.PositiveIntegerField(default=0)
    
    # Host preferences
    instant_book = models.BooleanField(default=False)
    auto_approval = models.BooleanField(default=False)
    same_day_bookings = models.BooleanField(default=False)
    
    # Superhost status
    is_superhost = models.BooleanField(default=False)
    superhost_since = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        verbose_name = 'Host'
        verbose_name_plural = 'Hosts'
    
    def __str__(self):
        return f"Host: {self.user.get_display_name()}"
    
    def save(self, *args, **kwargs):
        self.fully_verified = all([
            self.id_verified,
            self.address_verified, 
            self.email_verified,
            self.phone_verified
        ])
        
        self.update_superhost_status()
        super().save(*args, **kwargs)
    
    def update_superhost_status(self):
        criteria_met = all([
            self.total_bookings >= 10,
            self.average_rating >= 4.8,
            self.response_rate >= 90,
            self.response_time <= 2,
            self.fully_verified
        ])
        
        if criteria_met and not self.is_superhost:
            self.is_superhost = True
            self.superhost_since = timezone.now()
        elif not criteria_met and self.is_superhost:
            self.is_superhost = False
            self.superhost_since = None
    
    @property
    def completion_percentage(self):
        required_fields = [
            self.user.first_name, self.user.last_name, self.user.email,
            self.user.phone_number, self.user.profile_picture,
            self.government_id, self.tax_id
        ]
        completed = sum(1 for field in required_fields if field)
        return int((completed / len(required_fields)) * 100)