from django.db import models
from django.conf import settings

class Host(models.Model):
    """
    A profile model for hosts. This is not the main user model.
    It extends the CustomUser model with a OneToOne relationship.
    """
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True, related_name='host_profile')
    
    # Add host-specific fields here
    # E.g., hosting_since, properties_count, etc.
    
    def __str__(self):
        return f"Host: {self.user.username}"

# Model for a host's property listing
class Listing(models.Model):
    # A foreign key links each listing to a specific host
    host = models.ForeignKey('users.CustomUser', related_name='listings', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()

    # New fields to match the properties list template
    PROPERTY_TYPE_CHOICES = [
        ('Apartment', 'Apartment'),
        ('Villa', 'Villa'),
        ('Loft', 'Loft'),
        ('Studio', 'Studio'),
        ('Other', 'Other'),
    ]
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPE_CHOICES, default='Other')
    beds = models.IntegerField(default=1)
    baths = models.IntegerField(default=1)
    sqft = models.IntegerField(default=500)
    
    status = models.CharField(
        max_length=20,
        choices=[('Active', 'Active'), ('Inactive', 'Inactive')],
        default='Active'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
