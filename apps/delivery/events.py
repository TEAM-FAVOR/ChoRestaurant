from django.conf import settings

from apps.delivery.models import Delivery, DeliveryStatus
from apps.delivery.realtime import (
    publish_delivery_location,
    publish_delivery_status,
    publish_order_status,
)
from apps.delivery.tasks import prune_rider_locations, recompute_eta
from apps.notifications.events import notify_order_event
from apps.notifications.models import NotificationChannel
from apps.notifications.services import notify_users

ORDER_STATUS_FOR_DELIVERY_STATUS = {
    DeliveryStatus.IN_TRANSIT: "OUT_FOR_DELIVERY",
    DeliveryStatus.DELIVERED: "DELIVERED",
    DeliveryStatus.FAILED: "CANCELLED",
    DeliveryStatus.CANCELLED: "CANCELLED",
}

EVENT_FOR_DELIVERY_STATUS = {
    DeliveryStatus.ASSIGNED: "delivery.assigned",
    DeliveryStatus.IN_TRANSIT: "delivery.in_transit",
    DeliveryStatus.DELIVERED: "delivery.delivered",
    DeliveryStatus.FAILED: "delivery.failed",
    DeliveryStatus.CANCELLED: "delivery.cancelled",
}


def _enqueue_task(task, *, args=None, kwargs=None):
    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        return task.apply(args=args or (), kwargs=kwargs or {}, throw=False)
    return task.apply_async(args=args or (), kwargs=kwargs or {})


def _rider_user(delivery):
    return delivery.rider.user if delivery.rider_id else None


def _notify_rider(delivery, title, message, event):
    rider_user = _rider_user(delivery)
    if rider_user is None:
        return []
    return notify_users(
        users=[rider_user],
        title=title,
        message=message,
        channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
        order_reference=delivery.order_reference,
        delivery_id=delivery.pk,
        event=event,
    )


def delivery_assigned(delivery_id: int):
    delivery = Delivery.objects.select_related("rider", "rider__user", "customer").filter(
        pk=delivery_id
    ).first()
    if delivery is None:
        return

    publish_delivery_status(
        delivery.pk,
        DeliveryStatus.ASSIGNED,
        order_reference=delivery.order_reference,
    )
    publish_order_status(
        delivery.order_reference,
        "READY_FOR_PICKUP",
        delivery_id=delivery.pk,
        eta_minutes=delivery.eta_minutes,
    )
    _notify_rider(
        delivery,
        "New delivery assignment",
        f"You have been assigned delivery for order {delivery.order_reference}.",
        EVENT_FOR_DELIVERY_STATUS[DeliveryStatus.ASSIGNED],
    )
    if delivery.customer_id:
        notify_users(
            users=[delivery.customer],
            title="Rider assigned",
            message=f"A rider has been assigned to order {delivery.order_reference}.",
            channels=[NotificationChannel.IN_APP],
            order_reference=delivery.order_reference,
            delivery_id=delivery.pk,
            event=EVENT_FOR_DELIVERY_STATUS[DeliveryStatus.ASSIGNED],
        )
    _enqueue_task(recompute_eta, args=[delivery.pk])


def delivery_status_changed(delivery_id: int, previous_status: str, new_status: str):
    delivery = Delivery.objects.select_related("rider", "rider__user", "customer").filter(
        pk=delivery_id
    ).first()
    if delivery is None:
        return

    publish_delivery_status(
        delivery.pk,
        new_status,
        order_reference=delivery.order_reference,
        previous_status=previous_status,
    )

    order_status = ORDER_STATUS_FOR_DELIVERY_STATUS.get(new_status)
    if order_status:
        notify_order_event(
            user=delivery.customer,
            order_reference=delivery.order_reference,
            status=order_status,
            delivery_id=delivery.pk,
            message=f"Order {delivery.order_reference}: {new_status.replace('_', ' ').lower()}.",
            extra_context={"eta_minutes": delivery.eta_minutes},
        )

    event = EVENT_FOR_DELIVERY_STATUS.get(new_status, "delivery.updated")
    _notify_rider(
        delivery,
        f"Delivery {new_status.replace('_', ' ').lower()}",
        f"Delivery for order {delivery.order_reference} is now {new_status.replace('_', ' ').lower()}.",
        event,
    )

    if new_status == DeliveryStatus.IN_TRANSIT:
        _enqueue_task(recompute_eta, args=[delivery.pk])
    if new_status in (DeliveryStatus.DELIVERED, DeliveryStatus.FAILED, DeliveryStatus.CANCELLED):
        _enqueue_task(prune_rider_locations)


def rider_location_recorded(delivery_id: int, latitude, longitude, recorded_at=None):
    delivery = Delivery.objects.filter(pk=delivery_id).first()
    if delivery is None:
        return
    publish_delivery_location(
        delivery.pk,
        latitude,
        longitude,
        recorded_at=recorded_at,
        eta_minutes=delivery.eta_minutes,
    )
    _enqueue_task(recompute_eta, args=[delivery.pk])
