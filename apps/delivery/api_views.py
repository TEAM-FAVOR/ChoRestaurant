from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import RiderProfile
from apps.core.permissions import IsRider, IsStaffOrAdmin
from apps.delivery.models import Delivery
from apps.delivery.serializers import (
    DeliveryAssignSerializer,
    DeliverySerializer,
    DeliveryStatusSerializer,
    RiderAvailabilitySerializer,
    RiderConsentSerializer,
    RiderLocationCreateSerializer,
    RiderRegistrationSerializer,
    RiderSummarySerializer,
)
from apps.delivery.services import (
    assign_delivery,
    list_deliveries,
    list_riders,
    record_rider_location,
    register_rider,
    set_rider_availability,
    set_rider_location_consent,
    update_delivery_status,
)


class RiderListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        available_only = request.query_params.get("available_only", "").lower() in (
            "1",
            "true",
            "yes",
        )
        riders = list_riders(available_only=available_only)
        return Response(RiderSummarySerializer(riders, many=True).data)

    def post(self, request):
        serializer = RiderRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        payload.pop("password_confirm", None)
        user = register_rider(actor=request.user, **payload)
        return Response(
            {
                "message": "Rider registered successfully.",
                "user_id": user.pk,
                "username": user.username,
                "rider": RiderSummarySerializer(user.rider_profile).data,
            },
            status=status.HTTP_201_CREATED,
        )


class AvailableRidersAPIView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def get(self, request):
        riders = list_riders(available_only=True)
        return Response(RiderSummarySerializer(riders, many=True).data)


class RiderAvailabilityAPIView(APIView):
    permission_classes = [IsAuthenticated, IsRider]

    def get(self, request):
        profile, _ = RiderProfile.objects.get_or_create(user=request.user)
        return Response(RiderSummarySerializer(profile).data)

    def patch(self, request):
        serializer = RiderAvailabilitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile, _ = RiderProfile.objects.get_or_create(user=request.user)
        profile = set_rider_availability(
            profile,
            serializer.validated_data["is_available"],
        )
        return Response(RiderSummarySerializer(profile).data)


class RiderConsentAPIView(APIView):
    permission_classes = [IsAuthenticated, IsRider]

    def patch(self, request):
        serializer = RiderConsentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile, _ = RiderProfile.objects.get_or_create(user=request.user)
        profile = set_rider_location_consent(
            profile,
            serializer.validated_data["location_consent"],
        )
        return Response(RiderSummarySerializer(profile).data)


class DeliveryListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rider_id = request.query_params.get("rider_id")
        if request.query_params.get("rider", "").lower() in ("1", "true", "yes", "me"):
            profile = getattr(request.user, "rider_profile", None)
            if profile is None:
                return Response([], status=status.HTTP_200_OK)
            rider_id = profile.pk
        deliveries = list_deliveries(
            request.user,
            status=request.query_params.get("status", ""),
            rider_id=rider_id,
            customer_id=request.query_params.get("customer_id"),
            order_reference=request.query_params.get("order_reference", ""),
        )
        return Response(DeliverySerializer(deliveries, many=True).data)

    def post(self, request):
        serializer = DeliveryAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = dict(serializer.validated_data)
        payload["customer"] = payload.pop("customer_id", None)
        payload["rider"] = payload.pop("rider_id", None)
        delivery = assign_delivery(actor=request.user, **payload)
        return Response(
            DeliverySerializer(delivery).data,
            status=status.HTTP_201_CREATED,
        )


class DeliveryDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk: int):
        delivery = _visible_delivery_or_none(request.user, pk)
        if delivery is None:
            return Response(
                {"detail": "Delivery not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(DeliverySerializer(delivery).data)


class DeliveryStatusAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        serializer = DeliveryStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        delivery = get_object_or_404(Delivery, pk=pk)
        delivery = update_delivery_status(
            delivery,
            serializer.validated_data["status"],
            actor=request.user,
        )
        return Response(DeliverySerializer(delivery).data)


class RiderLocationAPIView(APIView):
    permission_classes = [IsAuthenticated, IsRider]

    def post(self, request, pk: int):
        serializer = RiderLocationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        delivery = get_object_or_404(Delivery, pk=pk)
        location = record_rider_location(
            delivery,
            request.user,
            serializer.validated_data["latitude"],
            serializer.validated_data["longitude"],
        )
        delivery.refresh_from_db()
        return Response(
            {
                "message": "Location updated.",
                "location": {
                    "latitude": str(location.latitude),
                    "longitude": str(location.longitude),
                    "recorded_at": location.recorded_at.isoformat(),
                },
                "eta_minutes": delivery.eta_minutes,
            },
            status=status.HTTP_201_CREATED,
        )


class DeliveryTrackAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_reference: str):
        from apps.delivery.services import get_delivery_for_order

        delivery = get_delivery_for_order(
            request.user,
            order_reference.strip().upper(),
        )
        if delivery is None:
            return Response(
                {"detail": "Delivery not found for this order."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(DeliverySerializer(delivery).data)


def _visible_delivery_or_none(user, pk: int):
    from apps.delivery.services import get_delivery_for_user

    return get_delivery_for_user(user, pk)
