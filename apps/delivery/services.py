from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import RiderProfile, UserRole
from apps.accounts.services import get_available_riders, register_user, update_rider_gps
from apps.core.maps import MapsFacade
from apps.core.permissions import ROLE_ADMIN, ROLE_STAFF, user_has_role
from apps.core.utils import haversine_distance_km
from apps.delivery import integrations
from apps.delivery.events import (
    delivery_assigned,
    delivery_status_changed,
    rider_location_recorded,
)
from apps.delivery.models import (
    ACTIVE_STATUSES,
    Delivery,
    DeliveryStatus,
    RiderLocation,
)

User = get_user_model()


def _assert_dispatch_user(actor):
    if actor is not None and not user_has_role(actor, ROLE_STAFF, ROLE_ADMIN):
        raise PermissionDenied("Only restaurant staff or administrators can manage deliveries.")


def _validate_coordinates(latitude, longitude):
    if latitude is None and longitude is None:
        return None, None
    if latitude is None or longitude is None:
        raise ValidationError("Both latitude and longitude are required.")
    try:
        lat = Decimal(str(latitude))
        lng = Decimal(str(longitude))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValidationError("Latitude and longitude must be valid numbers.") from exc
    if not Decimal("-90") <= lat <= Decimal("90"):
        raise ValidationError("Latitude must be between -90 and 90.")
    if not Decimal("-180") <= lng <= Decimal("180"):
        raise ValidationError("Longitude must be between -180 and 180.")
    return lat, lng


def _resolve_user(value):
    if value is None or isinstance(value, User):
        return value
    return User.objects.filter(pk=value).first()


def _resolve_rider(value):
    if value is None or isinstance(value, RiderProfile):
        return value
    return RiderProfile.objects.select_related("user").filter(pk=value).first()


def register_rider(
    *,
    username: str,
    email: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    phone: str = "",
    vehicle_type: str = "MOTORCYCLE",
    plate_number: str = "",
    is_available: bool = True,
    is_verified: bool = False,
    location_consent: bool = False,
    actor=None,
):
    _assert_dispatch_user(actor)
    user = register_user(
        username=username,
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        phone=phone,
        role=UserRole.RIDER,
        vehicle_type=vehicle_type,
        plate_number=plate_number,
    )
    profile = user.rider_profile
    profile.is_available = is_available
    profile.is_verified = is_verified
    profile.location_consent = location_consent
    profile.save(
        update_fields=[
            "is_available",
            "is_verified",
            "location_consent",
            "updated_at",
        ]
    )
    return user


def list_riders(available_only: bool = False):
    if available_only:
        return get_available_riders()
    return RiderProfile.objects.select_related("user").all()


def set_rider_availability(profile: RiderProfile, is_available: bool) -> RiderProfile:
    profile.is_available = is_available
    profile.save(update_fields=["is_available", "updated_at"])
    return profile


def set_rider_verification(profile: RiderProfile, is_verified: bool, actor=None) -> RiderProfile:
    _assert_dispatch_user(actor)
    profile.is_verified = is_verified
    profile.save(update_fields=["is_verified", "updated_at"])
    return profile


def set_rider_location_consent(profile: RiderProfile, has_consent: bool) -> RiderProfile:
    profile.location_consent = has_consent
    if not has_consent:
        profile.current_lat = None
        profile.current_lng = None
        profile.save(
            update_fields=[
                "location_consent",
                "current_lat",
                "current_lng",
                "updated_at",
            ]
        )
        return profile
    profile.save(update_fields=["location_consent", "updated_at"])
    return profile


def select_rider(destination_lat=None, destination_lng=None):
    lat, lng = _validate_coordinates(destination_lat, destination_lng)
    origin_lat, origin_lng = MapsFacade.get_restaurant_origin()
    target_lat = lat if lat is not None else origin_lat
    target_lng = lng if lng is not None else origin_lng

    candidates = []
    for profile in get_available_riders():
        rider_lat = profile.current_lat if profile.current_lat is not None else origin_lat
        rider_lng = profile.current_lng if profile.current_lng is not None else origin_lng
        distance = haversine_distance_km(rider_lat, rider_lng, target_lat, target_lng)
        candidates.append((distance, profile.pk, profile))

    if not candidates:
        raise ValidationError("No available verified riders for assignment.")
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


@transaction.atomic
def assign_delivery(
    *,
    order_reference: str,
    order_id=None,
    customer=None,
    rider=None,
    destination_lat=None,
    destination_lng=None,
    destination_address: str = "",
    notes: str = "",
    actor=None,
):
    _assert_dispatch_user(actor)
    reference = (order_reference or "").strip().upper()
    if not reference:
        raise ValidationError("An order reference is required.")

    if Delivery.objects.filter(order_reference=reference).exists():
        raise ValidationError("A delivery already exists for this order reference.")

    details = integrations.get_order_delivery_details(reference)
    customer = _resolve_user(customer) or details["customer"]
    order_id = order_id if order_id is not None else details["order_id"]
    destination_lat = destination_lat if destination_lat is not None else details["destination_lat"]
    destination_lng = destination_lng if destination_lng is not None else details["destination_lng"]
    destination_address = destination_address or details["destination_address"]
    lat, lng = _validate_coordinates(destination_lat, destination_lng)

    profile = _resolve_rider(rider)
    if profile is None:
        profile = select_rider(lat, lng)
    elif not profile.is_available or not profile.is_verified or not profile.user.is_active:
        raise ValidationError("Selected rider is not available for assignment.")

    distance_km = None
    eta_minutes = None
    if lat is not None and lng is not None:
        distance_km = MapsFacade.calculate_distance_from_restaurant(lat, lng)
        eta_minutes = MapsFacade.estimate_travel_minutes(distance_km)

    delivery = Delivery.objects.create(
        order_reference=reference,
        order_id=order_id,
        rider=profile,
        customer=customer,
        status=DeliveryStatus.ASSIGNED,
        assigned_at=timezone.now(),
        destination_lat=lat,
        destination_lng=lng,
        destination_address=destination_address or "",
        distance_km=distance_km,
        eta_minutes=eta_minutes,
        notes=notes or "",
    )
    RiderProfile.objects.filter(pk=profile.pk).update(is_available=False)
    profile.is_available = False
    delivery.rider = profile

    transaction.on_commit(lambda: delivery_assigned(delivery.pk))
    return delivery


def _can_manage_delivery(delivery, actor) -> bool:
    if actor is None:
        return False
    if user_has_role(actor, ROLE_STAFF, ROLE_ADMIN):
        return True
    return (
        user_has_role(actor, "RIDER")
        and delivery.rider_id is not None
        and delivery.rider.user_id == actor.pk
    )


@transaction.atomic
def update_delivery_status(delivery: Delivery, new_status: str, actor=None):
    if new_status not in DeliveryStatus.values:
        raise ValidationError({"status": f"Unsupported delivery status: {new_status}"})
    if not _can_manage_delivery(delivery, actor):
        raise PermissionDenied("You cannot update this delivery.")

    try:
        previous_status = delivery.apply_status(new_status)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    if delivery.is_terminal:
        _release_rider(delivery)

    transaction.on_commit(
        lambda: delivery_status_changed(delivery.pk, previous_status, new_status)
    )
    return delivery


def _release_rider(delivery: Delivery) -> None:
    if delivery.rider_id is None:
        return
    if Delivery.objects.filter(rider_id=delivery.rider_id, status__in=ACTIVE_STATUSES).exists():
        return
    RiderProfile.objects.filter(pk=delivery.rider_id).update(
        is_available=True,
        updated_at=timezone.now(),
    )
    profile = delivery.rider
    profile.is_available = True
    profile.clear_location()


@transaction.atomic
def record_rider_location(delivery: Delivery, rider_user, latitude, longitude):
    if not rider_user.is_rider:
        raise PermissionDenied("Only dispatch riders can share location.")
    if delivery.rider_id is None or delivery.rider.user_id != rider_user.pk:
        raise PermissionDenied("This delivery is not assigned to you.")
    if delivery.status != DeliveryStatus.IN_TRANSIT:
        raise ValidationError("Location sharing is only allowed during an active delivery.")
    if not delivery.rider.location_consent:
        raise ValidationError("Rider has not granted GPS location sharing consent.")

    lat, lng = _validate_coordinates(latitude, longitude)
    if lat is None or lng is None:
        raise ValidationError("Latitude and longitude are required.")

    update_rider_gps(rider_user, lat, lng)
    min_interval = getattr(settings, "GPS_MIN_INTERVAL_SECONDS", 2)
    latest = delivery.locations.order_by("-recorded_at").first()
    if latest and (timezone.now() - latest.recorded_at).total_seconds() < min_interval:
        return latest

    location = RiderLocation.objects.create(
        delivery=delivery,
        rider=delivery.rider,
        latitude=lat,
        longitude=lng,
        recorded_at=timezone.now(),
    )
    Delivery.objects.filter(pk=delivery.pk).update(
        current_lat=lat,
        current_lng=lng,
        updated_at=timezone.now(),
    )
    delivery.current_lat = lat
    delivery.current_lng = lng

    transaction.on_commit(
        lambda: rider_location_recorded(delivery.pk, lat, lng, location.recorded_at)
    )
    return location


def list_deliveries(user, *, status="", rider_id=None, customer_id=None, order_reference=""):
    queryset = Delivery.objects.visible_to(user).select_related(
        "rider", "rider__user", "customer"
    )
    if status:
        queryset = queryset.filter(status=status)
    if rider_id:
        queryset = queryset.filter(rider_id=rider_id)
    if customer_id:
        queryset = queryset.filter(customer_id=customer_id)
    if order_reference:
        queryset = queryset.filter(order_reference=order_reference)
    return queryset


def get_delivery_for_user(user, delivery_id: int):
    return Delivery.objects.visible_to(user).select_related(
        "rider", "rider__user", "customer"
    ).filter(pk=delivery_id).first()


def get_delivery_for_order(user, order_reference: str):
    return Delivery.objects.visible_to(user).select_related(
        "rider", "rider__user", "customer"
    ).filter(order_reference=order_reference).first()


def get_rider_deliveries(user):
    if not user.is_rider:
        return Delivery.objects.none()
    profile = RiderProfile.objects.filter(user=user).first()
    if profile is None:
        return Delivery.objects.none()
    return Delivery.objects.assigned_to(profile).select_related("customer")
