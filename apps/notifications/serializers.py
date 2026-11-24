from rest_framework import serializers

from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            "id",
            "order_reference",
            "delivery_id",
            "event",
            "title",
            "message",
            "channel",
            "status",
            "is_read",
            "sent_at",
            "retry_count",
            "last_error",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class NotificationBroadcastSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
    )
    title = serializers.CharField(max_length=150)
    message = serializers.CharField()
    channels = serializers.ListField(
        child=serializers.ChoiceField(choices=["IN_APP", "EMAIL", "SMS"]),
        required=False,
        allow_empty=False,
    )
    order_reference = serializers.CharField(max_length=24, required=False, allow_blank=True)
    event = serializers.CharField(max_length=80, required=False, allow_blank=True)


class OrderNotificationSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    order_reference = serializers.CharField(max_length=24)
    status = serializers.CharField(max_length=40)
    message = serializers.CharField(required=False, allow_blank=True)
    delivery_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    notify_staff = serializers.BooleanField(required=False, default=False)
