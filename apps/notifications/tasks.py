import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.db import DatabaseError
from django.utils import timezone

from apps.notifications.models import Notification, NotificationChannel, NotificationStatus
from apps.notifications.realtime import publish_user_notification

logger = logging.getLogger(__name__)

MAX_NOTIFICATION_RETRIES = 3
MAX_RETRY_COUNTDOWN = 300


@shared_task(bind=True, max_retries=MAX_NOTIFICATION_RETRIES, name="notifications.send_user_notification")
def send_user_notification(
    self,
    user_id,
    channel,
    title,
    message,
    order_reference="",
    delivery_id=None,
    event="",
    context=None,
    notification_id=None,
):
    payload = {
        "user_id": user_id,
        "channel": channel,
        "title": title,
        "message": message,
        "order_reference": order_reference,
        "delivery_id": delivery_id,
        "event": event,
        "context": context or {},
    }

    if notification_id:
        notification = Notification.objects.filter(pk=notification_id, user_id=user_id).first()
        if notification is None:
            return None
        notification.retry_count = self.request.retries
        notification.save(update_fields=["retry_count", "updated_at"])
    else:
        notification = Notification.objects.create(
            user_id=user_id,
            title=title,
            message=message,
            channel=channel,
            order_reference=order_reference or "",
            delivery_id=delivery_id,
            event=event or "",
            status=NotificationStatus.PENDING,
            context=context or {},
        )

    try:
        if channel == NotificationChannel.IN_APP:
            publish_user_notification(
                user_id,
                {
                    "id": notification.pk,
                    "title": title,
                    "message": message,
                    "event": event,
                    "order_reference": order_reference,
                    "delivery_id": delivery_id,
                    "created_at": timezone.now().isoformat(),
                },
            )
        elif channel == NotificationChannel.EMAIL:
            send_mail(
                subject=title,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[_recipient_email(user_id)],
                fail_silently=False,
            )
        elif channel == NotificationChannel.SMS:
            if not getattr(settings, "NOTIFICATION_SMS_GATEWAY_URL", ""):
                raise RuntimeError("SMS gateway is not configured.")
            raise RuntimeError("SMS delivery is not implemented in this deployment.")
        else:
            raise RuntimeError(f"Unsupported notification channel: {channel}")

        notification.mark_sent()
        return notification.pk
    except Exception as exc:
        notification.mark_failed(exc)
        logger.exception(
            "Notification delivery failed for user=%s channel=%s event=%s notification=%s",
            user_id,
            channel,
            event,
            notification.pk,
        )
        if isinstance(exc, DatabaseError):
            return notification.pk
        if self.request.retries < self.max_retries:
            retry_kwargs = dict(self.request.kwargs or {})
            retry_kwargs["notification_id"] = notification.pk
            raise self.retry(
                exc=exc,
                countdown=min(2 ** self.request.retries, MAX_RETRY_COUNTDOWN),
                kwargs=retry_kwargs,
            )
        return notification.pk


def _recipient_email(user_id: int) -> str:
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.filter(pk=user_id).only("email").first()
    if user is None or not user.email:
        raise RuntimeError(f"User {user_id} has no email address for notification delivery.")
    return user.email


@shared_task(name="notifications.send_order_notification")
def send_order_notification(
    user_id,
    order_reference,
    title,
    message,
    channels=None,
    event="",
    delivery_id=None,
    context=None,
):
    requested_channels = channels or [NotificationChannel.IN_APP, NotificationChannel.EMAIL]
    result = []
    for channel in requested_channels:
        notification_id = send_user_notification(
            user_id=user_id,
            channel=channel,
            title=title,
            message=message,
            order_reference=order_reference,
            delivery_id=delivery_id,
            event=event,
            context=context or {},
        )
        result.append(notification_id)
    return result
