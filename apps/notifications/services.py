from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.accounts.models import CustomerProfile
from apps.notifications.models import Notification, NotificationChannel
from apps.notifications.tasks import send_user_notification

User = get_user_model()

EVENT_TITLES = {
    "order.placed": "Order received",
    "order.confirmed": "Order confirmed",
    "order.preparing": "Order being prepared",
    "order.ready_for_pickup": "Order ready for pickup",
    "order.out_for_delivery": "Your rider is on the way",
    "order.delivered": "Order delivered",
    "order.cancelled": "Order cancelled",
    "payment.success": "Payment successful",
    "payment.failed": "Payment failed",
    "payment.refunded": "Refund issued",
    "delivery.assigned": "Delivery assigned",
    "delivery.in_transit": "Delivery in transit",
    "delivery.delivered": "Delivery completed",
    "delivery.failed": "Delivery failed",
    "delivery.cancelled": "Delivery cancelled",
}
DEFAULT_TITLE = "Order update"


def allowed_channels(user, requested_channels):
    channels = []
    for channel in requested_channels or [NotificationChannel.IN_APP]:
        if channel not in NotificationChannel.values:
            raise ValidationError(f"Unsupported notification channel: {channel}")
        if channel == NotificationChannel.IN_APP:
            channels.append(channel)
            continue
        profile = CustomerProfile.objects.filter(user=user).first()
        if profile is None:
            if channel == NotificationChannel.EMAIL:
                channels.append(channel)
            continue
        if channel == NotificationChannel.EMAIL and profile.notify_email:
            channels.append(channel)
        if channel == NotificationChannel.SMS and profile.notify_sms:
            channels.append(channel)
    return list(dict.fromkeys(channels))


def enqueue_notification(
    *,
    user,
    title,
    message,
    channel=NotificationChannel.IN_APP,
    order_reference="",
    delivery_id=None,
    event="",
    context=None,
):
    if user is None or not getattr(user, "pk", None):
        return None
    channels = allowed_channels(user, [channel])
    if not channels:
        return None
    task_kwargs = {
        "user_id": user.pk,
        "channel": channels[0],
        "title": title[:150],
        "message": message,
        "order_reference": order_reference or "",
        "delivery_id": delivery_id,
        "event": event,
        "context": context or {},
    }
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        return send_user_notification.apply(kwargs=task_kwargs, throw=False)
    return send_user_notification.apply_async(kwargs=task_kwargs)


def notify_users(
    *,
    users,
    title,
    message,
    channels=None,
    order_reference="",
    delivery_id=None,
    event="",
    context=None,
):
    requested = channels or [
        NotificationChannel.IN_APP,
        NotificationChannel.EMAIL,
    ]
    results = []
    for user in users:
        for channel in requested:
            result = enqueue_notification(
                user=user,
                title=title,
                message=message,
                channel=channel,
                order_reference=order_reference,
                delivery_id=delivery_id,
                event=event,
                context=context,
            )
            if result is not None:
                results.append(result)
    return results


def unread_count(user) -> int:
    return Notification.objects.for_user(user).unread().count()


def mark_read(notification: Notification) -> Notification:
    notification.mark_read()
    return notification


def mark_all_read(user) -> int:
    return Notification.objects.for_user(user).unread().mark_all_read()


def notification_payload(notification: Notification) -> dict:
    return {
        "id": notification.pk,
        "title": notification.title,
        "message": notification.message,
        "event": notification.event,
        "order_reference": notification.order_reference,
        "delivery_id": notification.delivery_id,
        "channel": notification.channel,
        "status": notification.status,
        "is_read": notification.is_read,
        "created_at": notification.created_at.isoformat(),
        "sent_at": notification.sent_at.isoformat() if notification.sent_at else None,
    }
