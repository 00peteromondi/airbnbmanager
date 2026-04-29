from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from core.realtime import announce_live_update

from .models import Notification


def absolute_url(path=''):
    base = getattr(settings, 'SITE_URL', 'http://127.0.0.1:8000').rstrip('/')
    if not path:
        return base
    if path.startswith('http://') or path.startswith('https://'):
        return path
    return f"{base}{path if path.startswith('/') else f'/{path}'}"


def _notification_groups(user_id):
    return [f'user-alerts-{user_id}']


def _email_enabled(user):
    profile = getattr(user, 'profile', None)
    if profile is None:
        return True
    return bool(getattr(profile, 'email_notifications', True))


def _send_transactional_email(user, title, body, action_url='', action_label='Open BayStays'):
    if not getattr(user, 'email', '') or not _email_enabled(user):
        return False

    full_action_url = absolute_url(action_url) if action_url else absolute_url('/users/profile/')
    context = {
        'user': user,
        'title': title,
        'body': body,
        'action_url': full_action_url,
        'action_label': action_label,
    }
    text_body = render_to_string('emails/notification_email.txt', context)
    html_body = render_to_string('emails/notification_email.html', context)

    message = EmailMultiAlternatives(
        subject=title,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html_body, 'text/html')
    message.send(fail_silently=False)
    return True


def create_notification(
    *,
    user,
    title,
    body,
    kind='system',
    level='info',
    action_url='',
    email_subject='',
    action_label='Open BayStays',
    metadata=None,
    send_email=True,
):
    notification = Notification.objects.create(
        user=user,
        title=title,
        body=body,
        kind=kind,
        level=level,
        action_url=action_url,
        metadata=metadata or {},
    )

    if send_email:
        try:
            emailed = _send_transactional_email(
                user,
                email_subject or title,
                body,
                action_url=action_url,
                action_label=action_label,
            )
            if emailed:
                notification.emailed_at = timezone.now()
                notification.save(update_fields=['emailed_at', 'updated_at'])
        except Exception:
            # Keep in-app notifications resilient even if email delivery is unavailable.
            pass

    announce_live_update(_notification_groups(user.id), message='notification-created')
    return notification


def notify_booking_created(booking, send_email=True):
    host_url = reverse('hosts:property_bookings')
    guest_url = reverse('bookings:booking_list')
    create_notification(
        user=booking.property.owner,
        title=f"New booking request for {booking.property.name}",
        body=f"{booking.guest.get_display_name()} requested {booking.check_in_date} to {booking.check_out_date}.",
        kind='booking',
        level='info',
        action_url=host_url,
        action_label='Review request',
        metadata={'booking_id': booking.id},
        send_email=send_email,
    )
    create_notification(
        user=booking.guest,
        title=f"Booking request sent for {booking.property.name}",
        body="Your BayStays booking request is in and the host can now review it.",
        kind='booking',
        level='success',
        action_url=guest_url,
        action_label='View booking',
        metadata={'booking_id': booking.id},
        send_email=send_email,
    )


def notify_booking_status(booking, old_status='', send_email=True):
    guest_url = reverse('bookings:booking_list')
    host_url = reverse('hosts:property_bookings')
    status_label = booking.get_status_display()
    create_notification(
        user=booking.guest,
        title=f"{booking.property.name} is now {status_label.lower()}",
        body=f"Your reservation status changed from {old_status or 'the previous state'} to {status_label.lower()}.",
        kind='booking',
        level='success' if booking.status in ['confirmed', 'checked_in', 'checked_out', 'completed'] else 'warning',
        action_url=guest_url,
        action_label='Open booking',
        metadata={'booking_id': booking.id, 'status': booking.status},
        send_email=send_email,
    )
    create_notification(
        user=booking.property.owner,
        title=f"Booking status updated for {booking.property.name}",
        body=f"{booking.guest.get_display_name()}'s reservation is now {status_label.lower()}.",
        kind='booking',
        level='info',
        action_url=host_url,
        action_label='Open booking queue',
        metadata={'booking_id': booking.id, 'status': booking.status},
        send_email=send_email,
    )


def notify_booking_rescheduled(booking):
    title = f"Stay dates changed for {booking.property.name}"
    body = f"The reservation now runs from {booking.check_in_date} to {booking.check_out_date} for {booking.num_guests} guest(s)."
    create_notification(
        user=booking.property.owner,
        title=title,
        body=f"{booking.guest.get_display_name()} rescheduled. {body}",
        kind='booking',
        level='warning',
        action_url=reverse('hosts:property_bookings'),
        action_label='Review booking',
        metadata={'booking_id': booking.id},
    )
    create_notification(
        user=booking.guest,
        title=title,
        body=f"Your BayStays booking was rescheduled. {body}",
        kind='booking',
        level='success',
        action_url=reverse('bookings:booking_list'),
        action_label='View booking',
        metadata={'booking_id': booking.id},
    )


def notify_payment_update(payment):
    booking = payment.booking
    guest_level = 'success' if payment.status == 'paid' else 'warning' if payment.status == 'initiated' else 'urgent'
    host_level = 'success' if payment.status == 'paid' else 'info'
    guest_body = (
        f"Payment for {booking.property.name} is {payment.get_status_display().lower()}."
        if payment.status != 'paid'
        else f"Payment for {booking.property.name} was received successfully."
    )
    host_body = (
        f"{booking.guest.get_display_name()} just settled KES {payment.amount:,.0f} for {booking.property.name}."
        if payment.status == 'paid'
        else f"Payment state for {booking.property.name} is now {payment.get_status_display().lower()}."
    )
    create_notification(
        user=booking.guest,
        title=f"Payment update for {booking.property.name}",
        body=guest_body,
        kind='payment',
        level=guest_level,
        action_url=reverse('bookings:guest_payments_center'),
        action_label='Open payments',
        metadata={'booking_id': booking.id, 'payment_id': payment.id},
    )
    create_notification(
        user=booking.property.owner,
        title=f"Payment activity on {booking.property.name}",
        body=host_body,
        kind='payment',
        level=host_level,
        action_url=reverse('hosts:dashboard'),
        action_label='Open host finance',
        metadata={'booking_id': booking.id, 'payment_id': payment.id},
    )


def notify_message_received(message):
    recipient = message.conversation.other_participant(message.sender)
    create_notification(
        user=recipient,
        title=f"New message from {message.sender.get_display_name()}",
        body=message.body[:180],
        kind='message',
        level='info',
        action_url=reverse('users:conversation_detail', args=[message.conversation_id]),
        action_label='Reply now',
        metadata={'conversation_id': message.conversation_id, 'message_id': message.id},
    )


def notify_subscription_update(subscription, title, body, level='info'):
    create_notification(
        user=subscription.host,
        title=title,
        body=body,
        kind='subscription',
        level=level,
        action_url=reverse('hosts:subscription_manage'),
        action_label='Manage plan',
        metadata={'subscription_id': subscription.id, 'plan': subscription.plan, 'status': subscription.status},
    )


def notify_report_ready(user, title, body, action_url):
    create_notification(
        user=user,
        title=title,
        body=body,
        kind='report',
        level='success',
        action_url=action_url,
        action_label='Open report',
    )


def notify_withdrawal_update(withdrawal, title, body, level='info'):
    create_notification(
        user=withdrawal.host,
        title=title,
        body=body,
        kind='payment',
        level=level,
        action_url=reverse('hosts:dashboard'),
        action_label='Open finance',
        metadata={'withdrawal_id': withdrawal.id},
    )
