from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Message
from .notifications import notify_message_received


@receiver(post_save, sender=Message)
def handle_message_created(sender, instance, created, **kwargs):
    if not created:
        return
    conversation = instance.conversation
    conversation.last_message_at = instance.created_at or timezone.now()
    conversation.save(update_fields=['last_message_at', 'updated_at'])
    notify_message_received(instance)
