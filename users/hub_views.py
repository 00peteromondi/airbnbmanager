from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from bookings.models import Booking
from hosts.services import ensure_host_subscription

from .assistant import assistant_reply, persist_assistant_exchange
from .models import AssistantChat, Conversation, Message, Notification


def _conversation_queryset(user):
    return Conversation.objects.filter(Q(host=user) | Q(guest=user)).select_related(
        'booking',
        'property',
        'host',
        'guest',
    ).prefetch_related('messages').order_by('-last_message_at')


def _notifications_context(user):
    notifications = Notification.objects.filter(user=user).order_by('-created_at')
    latest = notifications.values_list('updated_at', flat=True).first()
    return {
        'notifications': notifications[:24],
        'unread_count': notifications.filter(is_read=False).count(),
        'live_version': f"{notifications.count()}:{latest.isoformat() if latest else 'none'}",
    }


def _inbox_context(user):
    conversations = list(_conversation_queryset(user)[:20])
    for conversation in conversations:
        conversation.peer = conversation.other_participant(user)
        conversation.unread_count = conversation.unread_count_for(user)
        conversation.latest_message = conversation.messages.order_by('-created_at').first()
    latest = conversations[0].updated_at if conversations else None
    return {
        'conversations': conversations,
        'unread_total': sum(conversation.unread_count for conversation in conversations),
        'live_version': f"{len(conversations)}:{latest.isoformat() if latest else 'none'}",
    }


def _conversation_message_payload(message, user):
    return {
        'id': message.id,
        'body': message.body,
        'created_at': message.created_at,
        'sender_id': message.sender_id,
        'sender_name': message.sender.get_display_name(),
        'is_own': message.sender_id == user.id,
    }


def _assistant_page_label(request, path=''):
    resolved_path = path or request.path
    match = getattr(request, 'resolver_match', None)
    view_name = getattr(match, 'view_name', '')
    if view_name:
        return view_name.split(':')[-1].replace('_', ' ').strip().title()
    return resolved_path.strip('/').replace('-', ' ').replace('/', ' / ').title() or 'Current Page'


def _assistant_ui_context(request, surface='hub', path=''):
    resolved_path = path or request.path
    match = getattr(request, 'resolver_match', None)
    return {
        'surface': surface,
        'path': resolved_path,
        'view_name': getattr(match, 'view_name', ''),
        'url_name': getattr(match, 'url_name', ''),
        'section': (getattr(match, 'namespaces', None) or ['core'])[-1],
        'page_label': _assistant_page_label(request, path=resolved_path),
        'user_role': getattr(request.user, 'role', 'guest'),
    }


def _assistant_context(user, path='', surface='hub'):
    subscription = ensure_host_subscription(user) if user.role in ['host', 'both'] else None
    history = AssistantChat.objects.filter(user=user).order_by('created_at')[:16]
    return {
        'history': history,
        'subscription': subscription,
        'current_path': path,
        'assistant_surface': surface,
    }


def _get_conversation_or_404(user, conversation_id):
    return get_object_or_404(
        Conversation.objects.select_related('booking', 'property', 'host', 'guest'),
        Q(host=user) | Q(guest=user),
        id=conversation_id,
    )


@login_required
def notifications(request):
    return render(request, 'users/notifications.html', _notifications_context(request.user))


@login_required
def notifications_live(request):
    context = _notifications_context(request.user)
    return JsonResponse({
        'html': render_to_string('users/_notifications_content.html', context, request=request),
        'version': context['live_version'],
    })


@login_required
@require_POST
def notification_mark_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.mark_read()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    return redirect('users:notifications')


@login_required
@require_POST
def notification_mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True, read_at=timezone.now())
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True})
    return redirect('users:notifications')


@login_required
def inbox(request):
    return render(request, 'users/inbox.html', _inbox_context(request.user))


@login_required
def inbox_live(request):
    context = _inbox_context(request.user)
    return JsonResponse({
        'html': render_to_string('users/_inbox_content.html', context, request=request),
        'version': context['live_version'],
    })


@login_required
def start_booking_conversation(request, booking_id):
    booking = get_object_or_404(Booking.objects.select_related('property', 'guest'), id=booking_id)
    if request.user.id not in [booking.guest_id, booking.property.owner_id]:
        messages.error(request, 'You do not have access to that BayStays conversation.')
        return redirect('core:home')

    conversation, _ = Conversation.objects.get_or_create(
        booking=booking,
        defaults={
            'property': booking.property,
            'host': booking.property.owner,
            'guest': booking.guest,
        },
    )
    return redirect('users:conversation_detail', conversation_id=conversation.id)


@login_required
def conversation_detail(request, conversation_id):
    conversation = _get_conversation_or_404(request.user, conversation_id)
    conversation.mark_read_for(request.user)
    messages_qs = conversation.messages.select_related('sender').order_by('created_at')

    if request.method == 'POST':
        body = (request.POST.get('body') or '').strip()
        if not body:
            return JsonResponse({'ok': False, 'error': 'Write a message before sending.'}, status=400)
        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            body=body,
        )
        conversation.last_message_at = message.created_at
        conversation.save(update_fields=['last_message_at', 'updated_at'])
        payload = _conversation_message_payload(message, request.user)
        payload['created_at_display'] = message.created_at.strftime('%b %d, %Y %I:%M %p')
        return JsonResponse({'ok': True, 'message': payload})

    latest = messages_qs.values_list('created_at', flat=True).last()
    return render(request, 'users/conversation_detail.html', {
        'conversation': conversation,
        'peer': conversation.other_participant(request.user),
        'messages': messages_qs,
        'message_version': latest.isoformat() if latest else 'none',
    })


@login_required
def conversation_thread(request, conversation_id):
    conversation = _get_conversation_or_404(request.user, conversation_id)
    conversation.mark_read_for(request.user)
    messages_qs = conversation.messages.select_related('sender').order_by('created_at')
    latest = messages_qs.values_list('created_at', flat=True).last()
    return JsonResponse({
        'html': render_to_string('users/_conversation_messages.html', {
            'conversation': conversation,
            'messages': messages_qs,
        }, request=request),
        'version': latest.isoformat() if latest else 'none',
    })


@login_required
def assistant_hub(request):
    return render(request, 'users/assistant.html', _assistant_context(request.user, path=request.path, surface='hub'))


@login_required
def assistant_widget(request):
    context = _assistant_context(request.user, path=request.GET.get('path', request.path), surface='widget')
    return JsonResponse({
        'ok': True,
        'html': render_to_string('users/_assistant_widget.html', context, request=request),
    })


@login_required
@require_POST
def assistant_generate(request):
    prompt = (request.POST.get('prompt') or '').strip()
    if not prompt:
        return JsonResponse({'ok': False, 'error': 'Prompt is required.'}, status=400)

    subscription = ensure_host_subscription(request.user) if request.user.role in ['host', 'both'] else None
    if subscription and subscription.ai_messages_remaining <= 0:
        return JsonResponse({
            'ok': False,
            'error': f"You have used all {subscription.ai_message_limit} AI prompts on your current BayStays plan. Upgrade or wait for the next billing cycle to continue.",
        }, status=403)
    path = request.POST.get('path', request.path)
    surface = request.POST.get('surface', 'widget')
    response = assistant_reply(
        prompt,
        user=request.user,
        context=_assistant_ui_context(request, surface=surface, path=path),
        path=path,
    )
    persist_assistant_exchange(request.user, prompt, response)
    if subscription:
        subscription.ai_messages_used += 1
        subscription.save(update_fields=['ai_messages_used', 'updated_at'])
    return JsonResponse({'ok': True, 'response': response})
