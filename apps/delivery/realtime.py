from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone


def order_group_name(order_reference: str) -> str:
    return f"order_{order_reference}"


def delivery_group_name(delivery_id: int) -> str:
    return f"delivery_{delivery_id}"


def _group_send(group_name: str, payload: dict) -> None:
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    async_to_sync(channel_layer.group_send)(group_name, payload)


def publish_order_status(
    order_reference: str,
    status: str,
    *,
    delivery_id: int | None = None,
    eta_minutes: int | None = None,
) -> None:
    _group_send(
        order_group_name(order_reference),
        {
            "type": "status",
            "order_reference": order_reference,
            "status": status,
            "eta_minutes": eta_minutes,
            "delivery_id": delivery_id,
            "updated_at": timezone.now().isoformat(),
        },
    )


def publish_delivery_location(
    delivery_id: int,
    latitude,
    longitude,
    *,
    recorded_at=None,
    eta_minutes: int | None = None,
) -> None:
    timestamp = recorded_at or timezone.now()
    _group_send(
        delivery_group_name(delivery_id),
        {
            "type": "location",
            "delivery_id": delivery_id,
            "lat": str(latitude),
            "lng": str(longitude),
            "eta_minutes": eta_minutes,
            "ts": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
        },
    )


def publish_delivery_status(
    delivery_id: int,
    status: str,
    *,
    order_reference: str = "",
    previous_status: str = "",
) -> None:
    _group_send(
        delivery_group_name(delivery_id),
        {
            "type": "status",
            "delivery_id": delivery_id,
            "order_reference": order_reference,
            "status": status,
            "previous_status": previous_status,
            "updated_at": timezone.now().isoformat(),
        },
    )


def publish_delivery_eta(
    delivery_id: int,
    eta_minutes: int | None,
    *,
    order_reference: str = "",
) -> None:
    payload = {
        "type": "eta",
        "delivery_id": delivery_id,
        "order_reference": order_reference,
        "eta_minutes": eta_minutes,
        "updated_at": timezone.now().isoformat(),
    }
    _group_send(delivery_group_name(delivery_id), payload)
    if order_reference:
        _group_send(order_group_name(order_reference), payload)
