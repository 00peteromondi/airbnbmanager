from django.urls import path

from core.consumers import LiveUpdateConsumer
from users.consumers import ConversationConsumer


websocket_urlpatterns = [
    path('ws/live/', LiveUpdateConsumer.as_asgi()),
    path('ws/conversations/<int:conversation_id>/', ConversationConsumer.as_asgi()),
]
