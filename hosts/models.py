from django.db import models
from django.conf import settings
from django.utils import timezone
from cloudinary.models import CloudinaryField
from users.models import CustomUser
from decimal import Decimal

class Host(models.Model):
    PAYOUT_METHOD_CHOICES = (
        ('mpesa', 'M-Pesa'),
        ('bank', 'Bank transfer'),
    )

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
    payout_method = models.CharField(max_length=20, choices=PAYOUT_METHOD_CHOICES, default='mpesa')
    mpesa_phone_number = models.CharField(max_length=20, blank=True)
    payout_reference_name = models.CharField(max_length=120, blank=True)
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
        self.id_verified = self.user.government_id_status == 'verified'
        self.email_verified = self.user.email_verified
        self.phone_verified = self.user.phone_verified
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
            self.user.government_id_document or self.government_id, self.tax_id,
            self.mpesa_phone_number if self.payout_method == 'mpesa' else self.bank_name
        ]
        completed = sum(1 for field in required_fields if field)
        return int((completed / len(required_fields)) * 100)


class HostSubscription(models.Model):
    STATUS_CHOICES = (
        ('trialing', 'Trialing'),
        ('active', 'Active'),
        ('past_due', 'Past Due'),
        ('canceled', 'Canceled'),
    )

    PLAN_CHOICES = (
        ('essential', 'Essential'),
        ('growth', 'Growth'),
        ('signature', 'Signature'),
    )

    host = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='host_subscription',
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='growth')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trialing')
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    mpesa_phone_number = models.CharField(max_length=20, blank=True)
    ai_messages_used = models.PositiveIntegerField(default=0)
    is_auto_renew = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    trial_ends_at = models.DateTimeField(blank=True, null=True)
    current_period_end = models.DateTimeField(blank=True, null=True)
    next_billing_date = models.DateTimeField(blank=True, null=True)
    canceled_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.host.get_display_name()} - {self.get_plan_display()} ({self.get_status_display()})"

    @classmethod
    def plan_catalog(cls):
        return {
            'essential': {
                'name': 'Essential',
                'price': Decimal('0.00'),
                'listing_limit': 3,
                'ai_messages': 30,
                'features': [
                    'Inbox with guest messaging',
                    'Instant booking, payment, and status alerts',
                    'Core listing and host performance summaries',
                    'Export-ready PDF reports',
                ],
            },
            'growth': {
                'name': 'Growth',
                'price': Decimal('2900.00'),
                'listing_limit': 15,
                'ai_messages': 180,
                'features': [
                    'Everything in Essential',
                    'Priority BayStays AI planning support',
                    'Deeper report insights and recommendations',
                    'Higher active listing capacity',
                ],
            },
            'signature': {
                'name': 'Signature',
                'price': Decimal('6900.00'),
                'listing_limit': 60,
                'ai_messages': 600,
                'features': [
                    'Everything in Growth',
                    'High-volume assistant usage',
                    'Multi-listing portfolio oversight',
                    'Premium host workspace readiness tooling',
                ],
            },
        }

    @property
    def plan_details(self):
        return self.plan_catalog().get(self.plan, self.plan_catalog()['growth'])

    @property
    def listing_limit(self):
        return self.plan_details['listing_limit']

    @property
    def ai_message_limit(self):
        return self.plan_details['ai_messages']

    @property
    def ai_messages_remaining(self):
        return max(self.ai_message_limit - self.ai_messages_used, 0)

    def is_active(self):
        now = timezone.now()
        if self.status == 'active':
            return True
        return self.status == 'trialing' and self.trial_ends_at and self.trial_ends_at > now

    def sync_status(self):
        now = timezone.now()
        changed = False
        if self.status == 'trialing' and self.trial_ends_at and self.trial_ends_at <= now:
            self.status = 'past_due'
            changed = True
        elif self.status == 'active' and self.current_period_end and self.current_period_end <= now:
            self.status = 'past_due'
            changed = True
        if changed:
            self.save(update_fields=['status', 'updated_at'])
        return self.status

    def save(self, *args, **kwargs):
        details = self.plan_details
        self.monthly_price = details['price']
        if not self.started_at:
            self.started_at = timezone.now()
        super().save(*args, **kwargs)


class HostSubscriptionCharge(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('initiated', 'Initiated'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )

    subscription = models.ForeignKey(HostSubscription, on_delete=models.CASCADE, related_name='charges')
    plan = models.CharField(max_length=20, choices=HostSubscription.PLAN_CHOICES)
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
        return f"{self.subscription.host.get_display_name()} - {self.plan} ({self.status})"
