from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def user_group_name(user_id: int) -> str:
    return f"user_{user_id}"


def publish_user_notification(user_id: int, payload: dict) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(
        user_group_name(user_id),
        {"type": "notification", "notification": payload},
    )
