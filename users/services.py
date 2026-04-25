import json
import os
import random
import urllib.request
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from .models import VerificationCode


def generate_verification_code():
    return f"{random.randint(0, 999999):06d}"


def create_verification_code(user, channel):
    VerificationCode.objects.filter(user=user, channel=channel, is_used=False).update(is_used=True)
    return VerificationCode.objects.create(
        user=user,
        channel=channel,
        code=generate_verification_code(),
        expires_at=VerificationCode.expiry_time(),
    )


def send_email_verification_code(request, user, verification):
    subject = "Verify your BayStays email"
    context = {
        'user': user,
        'code': verification.code,
        'expires_at': verification.expires_at,
    }
    html_body = render_to_string('users/emails/email_verification.html', context, request=request)
    text_body = render_to_string('users/emails/email_verification.txt', context, request=request)
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@baystays.app'),
        to=[user.email],
    )
    email.attach_alternative(html_body, "text/html")
    email.send(fail_silently=False)


def send_phone_verification_code(user, verification):
    api_key = os.environ.get('BREVO_SMS_API_KEY')
    sender = os.environ.get('BREVO_SMS_SENDER')
    if not api_key or not sender or not user.phone_number:
        return False

    payload = {
        "sender": sender,
        "recipient": user.phone_number,
        "content": f"Your BayStays verification code is {verification.code}. It expires in 15 minutes.",
        "type": "transactional",
    }
    request = urllib.request.Request(
        url="https://api.brevo.com/v3/transactionalSMS/sms",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "api-key": api_key,
            "accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return 200 <= response.status < 300


def mark_channel_verified(user, channel):
    if channel == 'email':
        user.email_verified = True
        user.save(update_fields=['email_verified'])
    elif channel == 'phone':
        user.phone_verified = True
        user.save(update_fields=['phone_verified'])


def validate_verification_code(user, channel, code):
    verification = VerificationCode.objects.filter(
        user=user,
        channel=channel,
        code=str(code).strip(),
        is_used=False,
    ).first()
    if not verification:
        return None, "That verification code is not valid."
    if verification.is_expired:
        verification.is_used = True
        verification.save(update_fields=['is_used'])
        return None, "That verification code has expired. Request a fresh one."
    verification.is_used = True
    verification.save(update_fields=['is_used'])
    mark_channel_verified(user, channel)
    return verification, None
