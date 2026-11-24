from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import IsStaffOrAdmin
from apps.notifications.models import Notification
from apps.notifications.serializers import (
    NotificationBroadcastSerializer,
    NotificationSerializer,
    OrderNotificationSerializer,
)
from apps.notifications.services import mark_all_read, notify_users, unread_count

User = get_user_model()


class NotificationListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        queryset = Notification.objects.for_user(request.user)
        unread_only = request.query_params.get("unread", "").lower() in ("1", "true", "yes")
        channel = request.query_params.get("channel")
        if unread_only:
            queryset = queryset.unread()
        if channel:
            queryset = queryset.filter(channel=channel)
        return Response(NotificationSerializer(queryset, many=True).data)


class NotificationUnreadCountAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"unread_count": unread_count(request.user)})


class NotificationMarkReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        notification = Notification.objects.for_user(request.user).filter(pk=pk).first()
        if notification is None:
            return Response(
                {"detail": "Notification not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        notification.mark_read()
        return Response(NotificationSerializer(notification).data)


class NotificationMarkAllReadAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        updated = mark_all_read(request.user)
        return Response({"updated_count": updated})


class NotificationBroadcastAPIView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        serializer = NotificationBroadcastSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        users = User.objects.filter(
            pk__in=payload["user_ids"],
            is_active=True,
        )
        results = notify_users(
            users=users,
            title=payload["title"],
            message=payload["message"],
            channels=payload.get("channels"),
            order_reference=payload.get("order_reference", ""),
            event=payload.get("event", "broadcast"),
        )
        return Response(
            {"message": "Notification queued.", "queued_count": len(results)},
            status=status.HTTP_202_ACCEPTED,
        )


class OrderNotificationAPIView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrAdmin]

    def post(self, request):
        from apps.notifications.events import notify_order_event

        serializer = OrderNotificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        user = User.objects.filter(pk=payload["user_id"]).first()
        if user is None:
            return Response(
                {"detail": "User not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        notify_order_event(
            user=user,
            order_reference=payload["order_reference"].strip().upper(),
            status=payload["status"],
            message=payload.get("message", ""),
            delivery_id=payload.get("delivery_id"),
            notify_staff=payload.get("notify_staff", False),
        )
        return Response(
            {"message": "Order notification queued."},
            status=status.HTTP_202_ACCEPTED,
        )
