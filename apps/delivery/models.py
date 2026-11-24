from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.accounts.models import RiderProfile
from apps.core.models import TimeStampedModel

LATITUDE_VALIDATORS = [
    MinValueValidator(Decimal("-90.000000")),
    MaxValueValidator(Decimal("90.000000")),
]
LONGITUDE_VALIDATORS = [
    MinValueValidator(Decimal("-180.000000")),
    MaxValueValidator(Decimal("180.000000")),
]


class DeliveryStatus(models.TextChoices):
    ASSIGNED = "ASSIGNED", "Assigned"
    IN_TRANSIT = "IN_TRANSIT", "In Transit"
    DELIVERED = "DELIVERED", "Delivered"
    FAILED = "FAILED", "Failed"
    CANCELLED = "CANCELLED", "Cancelled"


ACTIVE_STATUSES = (DeliveryStatus.ASSIGNED, DeliveryStatus.IN_TRANSIT)
TERMINAL_STATUSES = (
    DeliveryStatus.DELIVERED,
    DeliveryStatus.FAILED,
    DeliveryStatus.CANCELLED,
)
LOCATION_SHARING_STATUSES = (DeliveryStatus.IN_TRANSIT,)

ALLOWED_TRANSITIONS = {
    DeliveryStatus.ASSIGNED: (
        DeliveryStatus.IN_TRANSIT,
        DeliveryStatus.FAILED,
        DeliveryStatus.CANCELLED,
    ),
    DeliveryStatus.IN_TRANSIT: (
        DeliveryStatus.DELIVERED,
        DeliveryStatus.FAILED,
        DeliveryStatus.CANCELLED,
    ),
    DeliveryStatus.DELIVERED: (),
    DeliveryStatus.FAILED: (),
    DeliveryStatus.CANCELLED: (),
}


class DeliveryQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status__in=ACTIVE_STATUSES)

    def terminal(self):
        return self.filter(status__in=TERMINAL_STATUSES)

    def assigned_to(self, rider_profile):
        return self.filter(rider=rider_profile)

    def visible_to(self, user):
        if not user or not user.is_authenticated:
            return self.none()
        if user.is_admin_role or user.is_restaurant_staff:
            return self.all()
        if user.is_rider:
            return self.filter(rider__user=user)
        return self.filter(customer=user)


class Delivery(TimeStampedModel):
    order_reference = models.CharField(max_length=24, unique=True, db_index=True)
    order_id = models.PositiveBigIntegerField(unique=True, null=True, blank=True)
    rider = models.ForeignKey(
        RiderProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries",
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deliveries",
    )
    status = models.CharField(
        max_length=20,
        choices=DeliveryStatus.choices,
        default=DeliveryStatus.ASSIGNED,
        db_index=True,
    )
    assigned_at = models.DateTimeField(default=timezone.now)
    picked_up_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    destination_lat = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=LATITUDE_VALIDATORS,
    )
    destination_lng = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=LONGITUDE_VALIDATORS,
    )
    destination_address = models.CharField(max_length=255, blank=True)
    current_lat = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=LATITUDE_VALIDATORS,
    )
    current_lng = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        validators=LONGITUDE_VALIDATORS,
    )
    eta_minutes = models.PositiveIntegerField(null=True, blank=True)
    distance_km = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    notes = models.TextField(blank=True)

    objects = DeliveryQuerySet.as_manager()

    class Meta:
        db_table = "delivery_delivery"
        verbose_name = "Delivery"
        verbose_name_plural = "Deliveries"
        ordering = ["-assigned_at"]
        indexes = [
            models.Index(fields=["rider", "status"], name="idx_delivery_rider"),
            models.Index(fields=["status"], name="idx_delivery_status"),
            models.Index(fields=["customer"], name="idx_delivery_customer"),
        ]

    def __str__(self) -> str:
        return f"Delivery({self.order_reference} - {self.status})"

    @property
    def is_active(self) -> bool:
        return self.status in ACTIVE_STATUSES

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES

    @property
    def can_share_location(self) -> bool:
        return (
            self.status in LOCATION_SHARING_STATUSES
            and self.rider_id is not None
            and bool(self.rider.location_consent)
        )

    @property
    def latest_location(self):
        return self.locations.order_by("-recorded_at").first()

    def allowed_statuses(self):
        return ALLOWED_TRANSITIONS.get(self.status, ())

    def can_transition_to(self, new_status: str) -> bool:
        return new_status in self.allowed_statuses()

    def apply_status(self, new_status: str) -> str:
        if not self.can_transition_to(new_status):
            raise ValueError(
                f"Cannot change delivery from {self.status} to {new_status}."
            )
        previous_status = self.status
        self.status = new_status
        now = timezone.now()
        if new_status == DeliveryStatus.IN_TRANSIT and self.picked_up_at is None:
            self.picked_up_at = now
        if new_status == DeliveryStatus.DELIVERED:
            self.delivered_at = now
        self.save(
            update_fields=[
                "status",
                "picked_up_at",
                "delivered_at",
                "updated_at",
            ]
        )
        return previous_status


class RiderLocation(models.Model):
    delivery = models.ForeignKey(
        Delivery,
        on_delete=models.CASCADE,
        related_name="locations",
    )
    rider = models.ForeignKey(
        RiderProfile,
        on_delete=models.CASCADE,
        related_name="location_history",
    )
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=LATITUDE_VALIDATORS,
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=LONGITUDE_VALIDATORS,
    )
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "delivery_riderlocation"
        verbose_name = "Rider Location"
        verbose_name_plural = "Rider Locations"
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["delivery", "-recorded_at"], name="idx_riderloc_delivery"),
            models.Index(fields=["rider", "-recorded_at"], name="idx_riderloc_rider"),
        ]

    def __str__(self) -> str:
        return f"RiderLocation({self.rider_id} at {self.latitude}, {self.longitude})"
