from asgiref.sync import async_to_sync

try:
    from channels.layers import get_channel_layer
except Exception:  # pragma: no cover - Channels optional in some environments
    get_channel_layer = None


def announce_live_update(groups, message='updated'):
    if not groups or get_channel_layer is None:
        return

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    payload = {
        'type': 'live.update',
        'groups': list(dict.fromkeys(groups)),
        'message': message,
    }
    for group in payload['groups']:
        async_to_sync(channel_layer.group_send)(group, payload)
