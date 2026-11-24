from django.contrib.auth import get_user_model
from django.db.models import Q

from apps.core.permissions import ROLE_ADMIN, ROLE_STAFF
from apps.delivery.realtime import publish_order_status
from apps.notifications.models import NotificationChannel
from apps.notifications.services import EVENT_TITLES, DEFAULT_TITLE, notify_users


def _title_for(event: str) -> str:
    return EVENT_TITLES.get(event, DEFAULT_TITLE)


def _staff_users():
    return get_user_model().objects.filter(
        Q(role__in=(ROLE_STAFF, ROLE_ADMIN)) | Q(is_superuser=True),
        is_active=True,
    )


def notify_order_event(
    *,
    user,
    order_reference: str,
    status: str,
    delivery_id: int | None = None,
    message: str = "",
    notify_staff: bool = False,
    extra_context: dict | None = None,
):
    normalized_status = str(status).strip().upper()
    event = f"order.{normalized_status.lower()}"
    title = _title_for(event)
    body = message or f"Your order {order_reference} is now {normalized_status.replace('_', ' ').lower()}."
    context = {"status": normalized_status, **(extra_context or {})}
    results = []

    if user is not None:
        results.extend(
            notify_users(
                users=[user],
                title=title,
                message=body,
                channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
                order_reference=order_reference,
                delivery_id=delivery_id,
                event=event,
                context=context,
            )
        )

    if notify_staff:
        results.extend(
            notify_users(
                users=_staff_users(),
                title=f"Order {order_reference}: {normalized_status.replace('_', ' ').lower()}",
                message=body,
                channels=[NotificationChannel.IN_APP],
                order_reference=order_reference,
                delivery_id=delivery_id,
                event=event,
                context=context,
            )
        )

    publish_order_status(
        order_reference,
        normalized_status,
        delivery_id=delivery_id,
        eta_minutes=(extra_context or {}).get("eta_minutes"),
    )
    return results


def notify_payment_event(
    *,
    user,
    order_reference: str,
    status: str,
    message: str = "",
    delivery_id: int | None = None,
):
    normalized_status = str(status).strip().lower()
    event = f"payment.{normalized_status}"
    return notify_users(
        users=[user] if user is not None else [],
        title=_title_for(event),
        message=message or f"Payment update for order {order_reference}: {normalized_status}.",
        channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
        order_reference=order_reference,
        delivery_id=delivery_id,
        event=event,
        context={"status": normalized_status},
    )
