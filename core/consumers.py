import json
from urllib.parse import parse_qs

from channels.generic.websocket import AsyncWebsocketConsumer


class LiveUpdateConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        params = parse_qs(self.scope.get('query_string', b'').decode('utf-8'))
        groups = []
        for raw_value in params.get('groups', []):
            groups.extend([
                item.strip() for item in raw_value.split(',')
                if item.strip()
            ])

        self.live_groups = list(dict.fromkeys(groups))
        for group in self.live_groups:
            await self.channel_layer.group_add(group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        for group in getattr(self, 'live_groups', []):
            await self.channel_layer.group_discard(group, self.channel_name)

    async def live_update(self, event):
        await self.send(text_data=json.dumps({
            'groups': event.get('groups', []),
            'message': event.get('message', ''),
        }))
