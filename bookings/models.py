from django.db import models
import builtins
from properties.models import Property
from users.models import CustomUser

# bookings/models.py - Add these features
class Booking(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('initiated', 'Initiated'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )

    REVENUE_ACTIVE_STATUSES = ['confirmed', 'checked_in', 'checked_out', 'completed']

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
        ('completed', 'Completed'),
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out'),
    )
    
    guest = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='bookings')
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    num_guests = models.PositiveIntegerField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    special_requests = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    checked_in_at = models.DateTimeField(blank=True, null=True)
    checked_out_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    
    # Payment fields
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_intent_id = models.CharField(max_length=100, blank=True)
    
    def calculate_total_price(self):
        nights = (self.check_out_date - self.check_in_date).days
        return nights * self.property.price_per_night
    
    def save(self, *args, **kwargs):
        if not self.total_price:
            self.total_price = self.calculate_total_price()
        super().save(*args, **kwargs)

    @builtins.property
    def is_paid(self):
        return self.payment_status == 'paid'

    @builtins.property
    def can_host_collect_revenue(self):
        return self.status in self.REVENUE_ACTIVE_STATUSES and self.payment_status == 'paid'
    
    def __str__(self):
        return f"{self.guest.email} - {self.property.name}"


class BookingPayment(models.Model):
    PROVIDER_CHOICES = (
        ('mpesa', 'M-Pesa'),
    )

    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('initiated', 'Initiated'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    )

    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='payments')
    guest = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='booking_payments')
    host = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='hosted_booking_payments')
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='mpesa')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    phone_number = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    checkout_request_id = models.CharField(max_length=120, blank=True)
    merchant_request_id = models.CharField(max_length=120, blank=True)
    transaction_reference = models.CharField(max_length=120, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment for {self.booking.property.name} ({self.status})"


class HostWithdrawal(models.Model):
    STATUS_CHOICES = (
        ('requested', 'Requested'),
        ('processing', 'Processing'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('rejected', 'Rejected'),
    )

    host = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='withdrawal_requests')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    mpesa_phone_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='requested')
    reference = models.CharField(max_length=120, blank=True)
    notes = models.TextField(blank=True)
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-requested_at']

    def __str__(self):
        return f"Withdrawal {self.amount} for {self.host.get_display_name()}"

# Add booking reviews
class Review(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(choices=[(i, i) for i in range(1, 6)])
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Review for {self.booking.property.name}"
