from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import Booking

@receiver(post_save, sender=Booking)
def send_booking_notification(sender, instance, created, **kwargs):
    if created:
        # Notify property owner
        subject = f"New Booking Request for {instance.property.name}"
        context = {'booking': instance}
        message = render_to_string('emails/new_booking_owner.txt', context)
        html_message = render_to_string('emails/new_booking_owner.html', context)

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [instance.property.owner.email],
            html_message=html_message,
            fail_silently=False,
        )

        # Notify guest
        guest_subject = f"Booking Request Submitted: {instance.property.name}"
        guest_message = render_to_string('emails/new_booking_guest.txt', context)
        guest_html_message = render_to_string('emails/new_booking_guest.html', context)

        send_mail(
            guest_subject,
            guest_message,
            settings.DEFAULT_FROM_EMAIL,
            [instance.guest.email],
            html_message=guest_html_message,
            fail_silently=False,
        )

    elif not created and 'status' in instance.get_dirty_fields():
        # Notify guest of status change
        subject = f"Booking Update: {instance.property.name}"
        context = {'booking': instance}
        message = render_to_string('emails/booking_status_update.txt', context)
        html_message = render_to_string('emails/booking_status_update.html', context)

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [instance.guest.email],
            html_message=html_message,
            fail_silently=False,
        )
