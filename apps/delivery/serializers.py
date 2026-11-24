from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.accounts.models import RiderProfile, VehicleType
from apps.delivery.models import Delivery, DeliveryStatus, RiderLocation

User = get_user_model()


class RiderSummarySerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = RiderProfile
        fields = (
            "id",
            "username",
            "full_name",
            "vehicle_type",
            "plate_number",
            "is_available",
            "is_verified",
            "location_consent",
            "current_lat",
            "current_lng",
            "last_seen",
        )
        read_only_fields = fields

    def get_full_name(self, obj: RiderProfile) -> str:
        return obj.user.get_full_name() or obj.user.username


class RiderLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiderLocation
        fields = ("id", "latitude", "longitude", "recorded_at")
        read_only_fields = fields


class DeliverySerializer(serializers.ModelSerializer):
    rider = RiderSummarySerializer(read_only=True)
    customer_username = serializers.CharField(source="customer.username", read_only=True)
    latest_location = RiderLocationSerializer(read_only=True)
    allowed_statuses = serializers.SerializerMethodField()

    class Meta:
        model = Delivery
        fields = (
            "id",
            "order_reference",
            "order_id",
            "rider",
            "customer",
            "customer_username",
            "status",
            "allowed_statuses",
            "assigned_at",
            "picked_up_at",
            "delivered_at",
            "destination_lat",
            "destination_lng",
            "destination_address",
            "current_lat",
            "current_lng",
            "eta_minutes",
            "distance_km",
            "latest_location",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_allowed_statuses(self, obj: Delivery):
        return list(obj.allowed_statuses())


class DeliveryAssignSerializer(serializers.Serializer):
    order_reference = serializers.CharField(max_length=24)
    order_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    customer_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    rider_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    destination_lat = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        allow_null=True,
    )
    destination_lng = serializers.DecimalField(
        max_digits=9,
        decimal_places=6,
        required=False,
        allow_null=True,
    )
    destination_address = serializers.CharField(max_length=255, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate_order_reference(self, value: str) -> str:
        return value.strip().upper()


class DeliveryStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=DeliveryStatus.choices)


class RiderLocationCreateSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)


class RiderRegistrationSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, required=False)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    vehicle_type = serializers.ChoiceField(choices=VehicleType.choices, required=False)
    plate_number = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    is_available = serializers.BooleanField(required=False, default=True)
    is_verified = serializers.BooleanField(required=False, default=False)
    location_consent = serializers.BooleanField(required=False, default=False)

    def validate_username(self, value: str) -> str:
        if User.objects.filter(username__iexact=value.strip()).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value.strip()

    def validate_email(self, value: str) -> str:
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate(self, attrs):
        password = attrs.get("password")
        password_confirm = attrs.get("password_confirm")
        if password_confirm is not None and password != password_confirm:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        validate_password(password)
        return attrs


class RiderAvailabilitySerializer(serializers.Serializer):
    is_available = serializers.BooleanField()


class RiderConsentSerializer(serializers.Serializer):
    location_consent = serializers.BooleanField()
