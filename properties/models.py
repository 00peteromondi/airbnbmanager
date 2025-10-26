from django.db import models
from users.models import CustomUser
from datetime import time
from cloudinary.models import CloudinaryField

class Property(models.Model):
    PROPERTY_TYPES = (
        ('apartment', 'Apartment'),
        ('house', 'House'),
        ('villa', 'Villa'),
        ('condo', 'Condominium'),
        ('loft', 'Loft'),
        ('studio', 'Studio'),
    )

    AMENITY_CHOICES = (
        ('wifi', 'WiFi'),
        ('kitchen', 'Kitchen'),
        ('parking', 'Parking'),
        ('pool', 'Swimming Pool'),
        ('gym', 'Gym'),
        ('ac', 'Air Conditioning'),
        ('heating', 'Heating'),
        ('tv', 'TV'),
        ('washer', 'Washer'),
        ('dryer', 'Dryer'),
        ('breakfast', 'Breakfast Included'),
        ('workspace', 'Dedicated Workspace'),
        ('fireplace', 'Fireplace'),
        ('balcony', 'Balcony'),
        ('garden', 'Garden'),
        ('bbq', 'BBQ Grill'),
        ('hot_tub', 'Hot Tub'),
        ('security', 'Security System'),
        ('elevator', 'Elevator'),
        ('accessible', 'Wheelchair Accessible'),
    )

    owner = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='properties')
    name = models.CharField(max_length=200)
    description = models.TextField()
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPES)
    address = models.TextField()
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100, default='Kenya')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)  # Changed from 'price'
    # Backwards-compatible price_per_night field. Some parts of the codebase
    # and templates expect `price_per_night` so we keep both fields and
    # synchronize them in save(). This avoids immediate migration issues.
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # Additional fields expected by views/templates
    beds = models.PositiveIntegerField(default=1)
    baths = models.DecimalField(max_digits=4, decimal_places=1, default=1.0)
    sqft = models.PositiveIntegerField(null=True, blank=True)
    max_guests = models.PositiveIntegerField()
    bedrooms = models.PositiveIntegerField()
    bathrooms = models.DecimalField(max_digits=3, decimal_places=1)
    amenities = models.JSONField(default=list)
    average_rating = models.FloatField(default=0.0)
    check_in_time = models.TimeField(default=time(15, 0))
    check_out_time = models.TimeField(default=time(11, 0))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # Keep price and price_per_night in sync for backward compatibility
        try:
            # If price_per_night not provided, populate it from price
            if (self.price_per_night is None or self.price_per_night == '') and hasattr(self, 'price'):
                self.price_per_night = self.price

            # If price_per_night provided but price missing/different, update price too
            if hasattr(self, 'price') and self.price_per_night is not None and self.price != self.price_per_night:
                self.price = self.price_per_night
        except Exception:
            pass

        super().save(*args, **kwargs)

    @property
    def amenities_list(self):
        return [dict(self.AMENITY_CHOICES).get(amenity, amenity) for amenity in self.amenities]

class PropertyImage(models.Model):
    property = models.ForeignKey(Property, related_name='images', on_delete=models.CASCADE)
    image = CloudinaryField('property_images', folder='airbnb_manager/properties/')
    caption = models.CharField(max_length=100, blank=True)
    is_primary = models.BooleanField(default=False)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def save(self, *args, **kwargs):
        if self.is_primary:
            PropertyImage.objects.filter(property=self.property, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Image for {self.property.name}"

class Review(models.Model):
    property = models.ForeignKey(Property, related_name='reviews', on_delete=models.CASCADE)
    user = models.ForeignKey('users.CustomUser', on_delete=models.CASCADE, related_name='property_reviews')
    rating = models.FloatField(choices=[(i/2, str(i/2)) for i in range(2, 11)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Review by {self.user.username} for {self.property.name}"