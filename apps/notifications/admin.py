from django.contrib import admin

from apps.notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "channel",
        "status",
        "event",
        "order_reference",
        "is_read",
        "created_at",
    )
    list_filter = ("channel", "status", "is_read")
    search_fields = ("title", "message", "order_reference", "user__username")
    readonly_fields = ("sent_at", "created_at", "updated_at")
