from django.contrib.auth.models import AbstractUser
from django.db import models
from cloudinary.models import CloudinaryField
from django.utils import timezone
from datetime import timedelta

class CustomUser(AbstractUser):
    GOVERNMENT_ID_STATUS_CHOICES = (
        ('not_submitted', 'Not Submitted'),
        ('pending', 'Pending Review'),
        ('verified', 'Verified'),
        ('rejected', 'Rejected'),
    )

    GOVERNMENT_ID_TYPE_CHOICES = (
        ('national_id', 'National ID'),
        ('passport', 'Passport'),
        ('drivers_license', 'Driver License'),
        ('alien_id', 'Alien ID'),
    )

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
    government_id_type = models.CharField(max_length=30, choices=GOVERNMENT_ID_TYPE_CHOICES, blank=True)
    government_id_number = models.CharField(max_length=80, blank=True)
    government_id_document = CloudinaryField(
        'government_id_document',
        folder='airbnb_manager/verification/users/',
        default=None,
        blank=True,
        null=True
    )
    government_id_status = models.CharField(
        max_length=20,
        choices=GOVERNMENT_ID_STATUS_CHOICES,
        default='not_submitted',
    )
    government_id_verified_at = models.DateTimeField(blank=True, null=True)
    
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

        if not self.government_id_document:
            self.government_id_status = 'not_submitted'
            self.government_id_verified_at = None
        elif self.government_id_status == 'verified' and not self.government_id_verified_at:
            self.government_id_verified_at = timezone.now()
        elif self.government_id_status != 'verified':
            self.government_id_verified_at = None
        
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


class VerificationCode(models.Model):
    CHANNEL_CHOICES = (
        ('email', 'Email'),
        ('phone', 'Phone'),
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='verification_codes')
    channel = models.CharField(max_length=10, choices=CHANNEL_CHOICES)
    code = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.channel}"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @classmethod
    def expiry_time(cls):
        return timezone.now() + timedelta(minutes=15)


class Notification(models.Model):
    KIND_CHOICES = (
        ('system', 'System'),
        ('booking', 'Booking'),
        ('payment', 'Payment'),
        ('message', 'Message'),
        ('subscription', 'Subscription'),
        ('report', 'Report'),
    )

    LEVEL_CHOICES = (
        ('info', 'Info'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('urgent', 'Urgent'),
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='system')
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='info')
    title = models.CharField(max_length=255)
    body = models.TextField()
    action_url = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    emailed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.get_display_name()} - {self.title}"

    def mark_read(self):
        if self.is_read:
            return
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=['is_read', 'read_at', 'updated_at'])


class Conversation(models.Model):
    booking = models.OneToOneField(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='conversation',
    )
    property = models.ForeignKey(
        'properties.Property',
        on_delete=models.CASCADE,
        related_name='conversations',
    )
    host = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='host_conversations',
    )
    guest = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='guest_conversations',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_message_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ['-last_message_at', '-updated_at']

    def __str__(self):
        return f"Conversation #{self.id} for booking {self.booking_id}"

    def other_participant(self, user):
        if user.id == self.host_id:
            return self.guest
        return self.host

    def unread_count_for(self, user):
        return self.messages.exclude(sender=user).filter(is_read=False).count()

    def mark_read_for(self, user):
        unread = self.messages.exclude(sender=user).filter(is_read=False)
        now = timezone.now()
        unread.update(is_read=True, read_at=now)


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_conversation_messages')
    body = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender.get_display_name()}: {self.body[:40]}"


class AssistantChat(models.Model):
    ROLE_CHOICES = (
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    )

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='assistant_chats')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.get_display_name()} [{self.role}]"

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
