from django.db.models import Q

from .models import Conversation, Notification


def communication_hub(request):
    context = {
        'unread_notification_count': 0,
        'unread_message_count': 0,
        'communication_attention_count': 0,
        'header_notifications': [],
    }
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return context

    unread_notifications = Notification.objects.filter(user=request.user, is_read=False)
    conversations = Conversation.objects.filter(Q(host=request.user) | Q(guest=request.user)).select_related(
        'booking',
        'property',
        'host',
        'guest',
    )
    unread_message_count = sum(conversation.unread_count_for(request.user) for conversation in conversations[:8])

    context.update({
        'unread_notification_count': unread_notifications.count(),
        'unread_message_count': unread_message_count,
        'communication_attention_count': unread_notifications.count() + unread_message_count,
        'header_notifications': unread_notifications[:4],
    })
    return context
