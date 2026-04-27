from django.db import models
from users.models import CustomUser
from datetime import time

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

    STAY_DETAIL_CHOICES = (
        ('family_friendly', 'Family friendly'),
        ('remote_work_ready', 'Remote work ready'),
        ('long_term_stays', 'Long-term stays welcome'),
        ('business_travel', 'Business travel friendly'),
        ('wellness_retreat', 'Wellness retreat'),
        ('accessible_stay', 'Accessible stay'),
        ('waterfront_escape', 'Waterfront escape'),
    )

    POLICY_CHOICES = (
        ('no_smoking', 'No smoking'),
        ('no_pets', 'No pets'),
        ('no_parties', 'No parties'),
        ('self_check_in', 'Self check-in'),
        ('children_allowed', 'Children allowed'),
        ('early_check_in', 'Early check-in available'),
        ('late_check_out', 'Late check-out available'),
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
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    max_guests = models.PositiveIntegerField()
    bedrooms = models.PositiveIntegerField()
    beds = models.PositiveIntegerField(default=1)
    bathrooms = models.DecimalField(max_digits=3, decimal_places=1)
    sqft = models.PositiveIntegerField(null=True, blank=True)
    amenities = models.JSONField(default=list)
    stay_details = models.JSONField(default=list, blank=True)
    policies = models.JSONField(default=list, blank=True)
    average_rating = models.FloatField(default=0.0)
    check_in_time = models.TimeField(default=time(15, 0))
    check_out_time = models.TimeField(default=time(11, 0))
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


    @property
    def amenities_list(self):
        return [dict(self.AMENITY_CHOICES).get(amenity, amenity) for amenity in self.amenities]

    @property
    def stay_detail_labels(self):
        details = self.stay_details or []
        return [dict(self.STAY_DETAIL_CHOICES).get(detail, detail.replace('_', ' ').title()) for detail in details]

    @property
    def policy_labels(self):
        policies = self.policies or []
        return [dict(self.POLICY_CHOICES).get(policy, policy.replace('_', ' ').title()) for policy in policies]

class PropertyImage(models.Model):
    property = models.ForeignKey(Property, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='property_images/')
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
