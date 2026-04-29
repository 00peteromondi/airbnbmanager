import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.db import models
from django.utils import timezone

from .models import Conversation, Message


class ConversationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'conversation-{self.conversation_id}'

        if not self.scope['user'].is_authenticated:
            await self.close()
            return

        if not await self.user_has_access():
            await self.close()
            return

        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        payload = json.loads(text_data or '{}')
        if payload.get('type') == 'typing':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'conversation.typing',
                    'user_id': self.scope['user'].id,
                    'user_name': self.scope['user'].get_display_name(),
                    'is_typing': bool(payload.get('is_typing')),
                },
            )
            return

        body = (payload.get('body') or '').strip()
        if not body:
            return

        message = await self.create_message(body)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'conversation.message',
                'message': message,
            },
        )

    async def conversation_message(self, event):
        await self.send(text_data=json.dumps(event['message']))

    async def conversation_typing(self, event):
        if event['user_id'] == self.scope['user'].id:
            return
        await self.send(text_data=json.dumps({
            'type': 'typing',
            'user_id': event['user_id'],
            'user_name': event['user_name'],
            'is_typing': event['is_typing'],
        }))

    @database_sync_to_async
    def user_has_access(self):
        return Conversation.objects.filter(
            id=self.conversation_id,
        ).filter(
            models.Q(host=self.scope['user']) | models.Q(guest=self.scope['user'])
        ).exists()

    @database_sync_to_async
    def create_message(self, body):
        conversation = Conversation.objects.select_related('host', 'guest').get(id=self.conversation_id)
        message = Message.objects.create(
            conversation=conversation,
            sender=self.scope['user'],
            body=body,
        )
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=['last_message_at', 'updated_at'])
        return {
            'type': 'message',
            'id': message.id,
            'body': message.body,
            'created_at': message.created_at.strftime('%b %d, %Y %I:%M %p'),
            'sender_id': message.sender_id,
            'sender_name': message.sender.get_display_name(),
            'is_own': message.sender_id == self.scope['user'].id,
        }
