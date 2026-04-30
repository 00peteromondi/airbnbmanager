import logging

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Booking
from users.notifications import notify_booking_created, notify_booking_status

logger = logging.getLogger(__name__)


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
    """
    Keep booking persistence independent from downstream notifications.

    Booking creation/status updates should still succeed even if email delivery
    or notification rendering fails.
    """
    try:
        if created:
            send_booking_request_email(instance)
        else:
            old_status = getattr(instance, '_old_status', None)
            if old_status and old_status != instance.status:
                send_booking_status_update(instance, old_status=old_status)
    except Exception:
        logger.exception('Booking notification pipeline failed for booking %s', instance.pk)


def send_booking_request_email(booking):
    """Route booking request notifications through the shared BayStays pipeline."""
    notify_booking_created(booking, send_email=True)


def send_booking_status_update(booking, old_status=''):
    """Route booking status notifications through the shared BayStays pipeline."""
    notify_booking_status(booking, old_status, send_email=True)
