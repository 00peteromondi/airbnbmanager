from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import Booking


@receiver(pre_save, sender=Booking)
def track_booking_changes(sender, instance, **kwargs):
    """Track previous booking status before saving so we can compare in post_save."""
    if instance.pk:
        try:
            instance._old_status = Booking.objects.get(pk=instance.pk).status
        except Booking.DoesNotExist:
            instance._old_status = None


@receiver(post_save, sender=Booking)
def handle_booking_notifications(sender, instance, created, **kwargs):
    """Single handler for booking notifications (creation and status updates)."""
    if created:
        send_booking_request_email(instance)
    else:
        old_status = getattr(instance, '_old_status', None)
        if old_status and old_status != instance.status:
            send_booking_status_update(instance)


def send_booking_request_email(booking):
    """Send booking request emails to host and guest"""
    subject_host = f"New Booking Request - {booking.property.name}"
    context = {'booking': booking}
    html_message_host = render_to_string('emails/booking_request_host.html', context)
    plain_message_host = render_to_string('emails/booking_request_host.txt', context)

    send_mail(
        subject_host,
        plain_message_host,
        settings.DEFAULT_FROM_EMAIL,
        [booking.property.owner.email],
        html_message=html_message_host,
        fail_silently=False,
    )

    subject_guest = f"Booking Request Submitted - {booking.property.name}"
    html_message_guest = render_to_string('emails/booking_request_guest.html', context)
    plain_message_guest = render_to_string('emails/booking_request_guest.txt', context)

    send_mail(
        subject_guest,
        plain_message_guest,
        settings.DEFAULT_FROM_EMAIL,
        [booking.guest.email],
        html_message=html_message_guest,
        fail_silently=False,
    )


def send_booking_status_update(booking):
    """Send status update to guest"""
    subject = f"Booking Status Update - {booking.property.name}"
    context = {'booking': booking}
    html_message = render_to_string('emails/booking_status_update.html', context)
    plain_message = render_to_string('emails/booking_status_update.txt', context)

    send_mail(
        subject,
        plain_message,
        settings.DEFAULT_FROM_EMAIL,
        [booking.guest.email],
        html_message=html_message,
        fail_silently=False,
    )