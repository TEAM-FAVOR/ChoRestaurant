from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import RiderProfile
from apps.core.maps import MapsFacade
from apps.core.utils import haversine_distance_km
from apps.delivery.models import (
    ACTIVE_STATUSES,
    Delivery,
    DeliveryStatus,
    RiderLocation,
)
from apps.delivery.realtime import publish_delivery_eta


@shared_task(name="delivery.recompute_eta")
def recompute_eta(delivery_id: int):
    delivery = (
        Delivery.objects.select_related("rider")
        .filter(pk=delivery_id, status__in=ACTIVE_STATUSES)
        .first()
    )
    if delivery is None:
        return None

    position = delivery.locations.order_by("-recorded_at").first()
    rider_lat = position.latitude if position else delivery.current_lat
    rider_lng = position.longitude if position else delivery.current_lng
    if (
        rider_lat is None
        or rider_lng is None
        or delivery.destination_lat is None
        or delivery.destination_lng is None
    ):
        return None

    remaining_km = haversine_distance_km(
        rider_lat,
        rider_lng,
        delivery.destination_lat,
        delivery.destination_lng,
    )
    eta_minutes = MapsFacade.estimate_travel_minutes(remaining_km)
    if delivery.eta_minutes != eta_minutes:
        delivery.eta_minutes = eta_minutes
        delivery.save(update_fields=["eta_minutes", "updated_at"])
    publish_delivery_eta(
        delivery.pk,
        eta_minutes,
        order_reference=delivery.order_reference,
    )
    return eta_minutes


@shared_task(name="delivery.prune_rider_locations")
def prune_rider_locations():
    retention_minutes = getattr(settings, "LOCATION_HISTORY_RETENTION_MINUTES", 60)
    cutoff = timezone.now() - timedelta(minutes=retention_minutes)
    completed_ids = list(
        Delivery.objects.filter(
            status=DeliveryStatus.DELIVERED,
            delivered_at__lt=cutoff,
        ).values_list("pk", flat=True)
    )
    deleted_count = 0
    if completed_ids:
        deleted_count, _ = RiderLocation.objects.filter(delivery_id__in=completed_ids).delete()

    cleared_riders = 0
    rider_ids = list(
        Delivery.objects.filter(status=DeliveryStatus.DELIVERED, delivered_at__lt=cutoff)
        .exclude(rider_id=None)
        .values_list("rider_id", flat=True)
        .distinct()
    )
    for rider_id in rider_ids:
        if Delivery.objects.filter(rider_id=rider_id, status__in=ACTIVE_STATUSES).exists():
            continue
        updated = RiderProfile.objects.filter(pk=rider_id).exclude(
            Q(current_lat__isnull=True) & Q(current_lng__isnull=True)
        ).update(current_lat=None, current_lng=None, updated_at=timezone.now())
        cleared_riders += updated

    return {"deleted_locations": deleted_count, "cleared_riders": cleared_riders}


@shared_task(name="delivery.release_stale_rider_locations")
def release_stale_rider_locations():
    stale_minutes = getattr(settings, "RIDER_LOCATION_STALE_MINUTES", 15)
    cutoff = timezone.now() - timedelta(minutes=stale_minutes)
    rider_ids = (
        Delivery.objects.filter(status__in=ACTIVE_STATUSES)
        .exclude(rider_id=None)
        .values_list("rider_id", flat=True)
        .distinct()
    )
    cleared = RiderProfile.objects.filter(
        pk__in=rider_ids,
        last_seen__lt=cutoff,
    ).exclude(Q(current_lat__isnull=True) & Q(current_lng__isnull=True)).update(
        current_lat=None,
        current_lng=None,
        updated_at=timezone.now(),
    )
    return {"cleared_riders": cleared}
