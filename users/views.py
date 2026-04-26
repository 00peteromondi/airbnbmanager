import json
import random
import urllib.error
import urllib.request

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.mail import EmailMultiAlternatives
from django.db.models import Avg, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from bookings.models import Booking
from hosts.models import Host
from properties.models import Property

from .forms import (
    CustomUserCreationForm,
    ProfileDetailsForm,
    ProfilePreferencesForm,
    RoleSelectionForm,
)
from .models import VerificationCode


def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('core:home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {'form': form})


def _issue_verification_code(user, channel):
    VerificationCode.objects.filter(user=user, channel=channel, is_used=False).update(is_used=True)
    return VerificationCode.objects.create(
        user=user,
        channel=channel,
        code=f'{random.randint(0, 999999):06d}',
        expires_at=VerificationCode.expiry_time(),
    )


def _send_brevo_email_code(user, code):
    subject = 'Verify your BayStays email'
    verify_minutes = 15
    text_body = (
        f'Hi {user.get_display_name()},\n\n'
        f'Use this BayStays verification code to confirm your email address: {code}\n\n'
        f'The code expires in {verify_minutes} minutes.'
    )
    html_body = (
        '<div style="font-family:Arial,sans-serif;max-width:540px;margin:0 auto;padding:24px;">'
        '<div style="background:#cf2338;color:#ffffff;padding:18px 22px;border-radius:14px 14px 0 0;">'
        '<h1 style="margin:0;font-size:24px;">BayStays email verification</h1>'
        '</div>'
        '<div style="border:1px solid #e2e8f0;border-top:none;padding:24px 22px 26px;border-radius:0 0 14px 14px;">'
        f'<p style="margin:0 0 16px;color:#0f172a;">Hi {user.get_display_name()},</p>'
        '<p style="margin:0 0 18px;color:#475569;">Use the code below in your BayStays profile to verify this email address.</p>'
        f'<div style="font-size:32px;font-weight:800;letter-spacing:0.32em;color:#cf2338;margin:14px 0 18px;">{code}</div>'
        f'<p style="margin:0;color:#64748b;">This code expires in {verify_minutes} minutes.</p>'
        '</div>'
        '</div>'
    )
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html_body, 'text/html')
    message.send(fail_silently=False)


def _send_brevo_phone_code(user, code):
    api_key = getattr(settings, 'BREVO_SMS_API_KEY', '')
    sender = getattr(settings, 'BREVO_SMS_SENDER', '')
    if not api_key or not sender:
        return False, None

    payload = json.dumps({
        'sender': sender,
        'recipient': user.phone_number,
        'content': f'Your BayStays verification code is {code}. It expires in 15 minutes.',
        'type': 'transactional',
        'tag': 'baystays-phone-verification',
    }).encode('utf-8')

    request = urllib.request.Request(
        'https://api.brevo.com/v3/transactionalSMS/sms',
        data=payload,
        headers={
            'accept': 'application/json',
            'api-key': api_key,
            'content-type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=12):
            return True, None
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode('utf-8')
        except Exception:
            detail = ''
        return False, detail or 'Brevo SMS returned an error.'
    except Exception as exc:  # pragma: no cover - network/runtime dependent
        return False, str(exc)


def _verify_code(user, channel, raw_code):
    if not raw_code:
        return None
    return VerificationCode.objects.filter(
        user=user,
        channel=channel,
        code=str(raw_code).strip(),
        is_used=False,
        expires_at__gt=timezone.now(),
    ).order_by('-created_at').first()


@login_required
def profile(request):
    profile_obj = request.user.profile
    if request.method == 'POST':
        form_scope = request.POST.get('form_scope')
        if form_scope == 'preferences':
            details_form = ProfileDetailsForm(instance=request.user)
            preferences_form = ProfilePreferencesForm(request.POST, instance=profile_obj)
            password_form = PasswordChangeForm(request.user)
            if preferences_form.is_valid():
                preferences_form.save()
                messages.success(request, 'Your BayStays preferences have been updated.')
                return redirect('users:profile')
        elif form_scope == 'password':
            details_form = ProfileDetailsForm(instance=request.user)
            preferences_form = ProfilePreferencesForm(instance=profile_obj)
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Your BayStays password has been changed successfully.')
                return redirect('users:profile')
        else:
            previous_email = request.user.email
            previous_phone = request.user.phone_number
            details_form = ProfileDetailsForm(request.POST, request.FILES, instance=request.user)
            preferences_form = ProfilePreferencesForm(instance=profile_obj)
            password_form = PasswordChangeForm(request.user)
            if details_form.is_valid():
                user = details_form.save(commit=False)
                if previous_email.strip().lower() != (user.email or '').strip().lower():
                    user.email_verified = False
                if (previous_phone or '').strip() != (user.phone_number or '').strip():
                    user.phone_verified = False
                user.save()
                messages.success(request, 'Your BayStays profile has been updated.')
                return redirect('users:profile')
        messages.error(request, 'Please correct the highlighted profile details and try again.')
    else:
        details_form = ProfileDetailsForm(instance=request.user)
        preferences_form = ProfilePreferencesForm(instance=profile_obj)
        password_form = PasswordChangeForm(request.user)

    guest_bookings = Booking.objects.filter(guest=request.user).exclude(status='cancelled')
    host_properties = Property.objects.filter(owner=request.user)
    host_bookings = Booking.objects.filter(property__owner=request.user)
    host_profile = Host.objects.filter(user=request.user).first()

    context = {
        'details_form': details_form,
        'preferences_form': preferences_form,
        'password_form': password_form,
        'guest_stats': {
            'total_bookings': guest_bookings.count(),
            'upcoming_trips': guest_bookings.filter(status__in=['pending', 'confirmed']).count(),
            'completed_trips': guest_bookings.filter(status__in=['completed', 'checked_out']).count(),
            'spend': guest_bookings.filter(status__in=['confirmed', 'completed']).aggregate(total=Sum('total_price'))['total'] or 0,
        },
        'host_stats': {
            'total_properties': host_properties.count(),
            'live_properties': host_properties.filter(is_active=True).count(),
            'total_bookings': host_bookings.count(),
            'revenue': host_bookings.filter(status__in=['confirmed', 'completed']).aggregate(total=Sum('total_price'))['total'] or 0,
            'avg_rating': host_properties.aggregate(avg=Avg('average_rating'))['avg'] or 0,
        },
        'host_profile': host_profile,
        'recent_guest_bookings': guest_bookings.select_related('property').order_by('-created_at')[:4],
        'recent_host_bookings': host_bookings.select_related('property', 'guest').order_by('-created_at')[:4],
        'email_verification_pending': VerificationCode.objects.filter(
            user=request.user,
            channel='email',
            is_used=False,
            expires_at__gt=timezone.now(),
        ).exists(),
        'phone_verification_pending': VerificationCode.objects.filter(
            user=request.user,
            channel='phone',
            is_used=False,
            expires_at__gt=timezone.now(),
        ).exists(),
    }
    return render(request, 'users/profile.html', context)


@login_required
def send_email_verification(request):
    if request.method != 'POST':
        return redirect('users:profile')
    if not request.user.email:
        messages.error(request, 'Add an email address in your profile before requesting verification.')
        return redirect('users:profile')

    verification = _issue_verification_code(request.user, 'email')
    try:
        _send_brevo_email_code(request.user, verification.code)
    except Exception:
        verification.delete()
        messages.error(request, 'We could not send the verification email right now. Please check your Brevo SMTP settings and try again.')
        return redirect('users:profile')

    messages.success(request, f'We sent a verification code to {request.user.email}.')
    return redirect('users:profile')


@login_required
def verify_email_code(request):
    if request.method != 'POST':
        return redirect('users:profile')
    verification = _verify_code(request.user, 'email', request.POST.get('email_code'))
    if not verification:
        messages.error(request, 'That email verification code is invalid or has expired.')
        return redirect('users:profile')

    verification.is_used = True
    verification.save(update_fields=['is_used'])
    request.user.email_verified = True
    request.user.save(update_fields=['email_verified'])
    messages.success(request, 'Your email address is now verified on BayStays.')
    return redirect('users:profile')


@login_required
def send_phone_verification(request):
    if request.method != 'POST':
        return redirect('users:profile')
    if not request.user.phone_number:
        messages.error(request, 'Add a phone number in your profile before requesting verification.')
        return redirect('users:profile')

    verification = _issue_verification_code(request.user, 'phone')
    delivered, detail = _send_brevo_phone_code(request.user, verification.code)

    if delivered:
        messages.success(request, f'We sent a verification code to {request.user.phone_number}.')
        return redirect('users:profile')

    if settings.DEBUG:
        messages.warning(
            request,
            f'Phone delivery is not fully configured yet. Use this local verification code for testing: {verification.code}'
        )
    else:
        verification.delete()
        messages.error(request, 'We could not send the phone verification code right now. Please review your Brevo SMS settings and try again.')
        if detail:
            messages.info(request, detail[:180])
    return redirect('users:profile')


@login_required
def verify_phone_code(request):
    if request.method != 'POST':
        return redirect('users:profile')
    verification = _verify_code(request.user, 'phone', request.POST.get('phone_code'))
    if not verification:
        messages.error(request, 'That phone verification code is invalid or has expired.')
        return redirect('users:profile')

    verification.is_used = True
    verification.save(update_fields=['is_used'])
    request.user.phone_verified = True
    request.user.save(update_fields=['phone_verified'])
    messages.success(request, 'Your phone number is now verified on BayStays.')
    return redirect('users:profile')


@login_required
def role_selection(request):
    """
    View for new users to select their role (Host, Guest, or Both)
    """
    if request.user.role:
        return redirect(get_redirect_url(request.user))

    if request.method == 'POST':
        form = RoleSelectionForm(request.POST, instance=request.user)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Welcome! You're now registered as a {user.get_role_display()}.")
            return redirect(get_redirect_url(user))
    else:
        form = RoleSelectionForm(instance=request.user)

    return render(request, 'users/role_selection.html', {'form': form})


def get_redirect_url(user):
    if user.role == 'host':
        return 'hosts:dashboard'
    if user.role == 'both':
        return 'core:home'
    return 'guests:guest_dashboard'


@login_required
def switch_role(request, role):
    if request.user.role != 'both':
        messages.error(request, "You don't have permission to switch roles.")
        return redirect('core:home')

    valid_roles = ['host', 'guest']
    if role not in valid_roles:
        messages.error(request, 'Invalid role selection.')
        return redirect('core:home')

    request.session['active_role'] = role
    request.session.modified = True

    messages.success(request, f"Switched to {role.capitalize()} mode.")

    if role == 'host':
        return redirect('hosts:dashboard')
    return redirect('guests:guest_dashboard')


@login_required
def get_active_role(request):
    active_role = request.session.get('active_role', 'guest')
    return JsonResponse({'active_role': active_role})
