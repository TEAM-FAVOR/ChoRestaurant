from django.contrib import admin

from apps.delivery.models import Delivery, RiderLocation


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "order_reference",
        "rider",
        "customer",
        "status",
        "eta_minutes",
        "assigned_at",
    )
    list_filter = ("status",)
    search_fields = ("order_reference", "rider__user__username", "customer__username")
    readonly_fields = ("assigned_at", "picked_up_at", "delivered_at", "created_at", "updated_at")


@admin.register(RiderLocation)
class RiderLocationAdmin(admin.ModelAdmin):
    list_display = ("id", "delivery", "rider", "latitude", "longitude", "recorded_at")
    list_filter = ("rider",)
    search_fields = ("delivery__order_reference", "rider__user__username")
    readonly_fields = ("recorded_at",)
