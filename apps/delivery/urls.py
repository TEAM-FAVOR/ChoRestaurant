from django.urls import path

from apps.delivery.views import (
    CustomerTrackingView,
    RiderDashboardView,
    RiderDeliveryDetailView,
)

app_name = "delivery"

urlpatterns = [
    path("rider/", RiderDashboardView.as_view(), name="rider-dashboard"),
    path(
        "rider/deliveries/<int:pk>/",
        RiderDeliveryDetailView.as_view(),
        name="rider-delivery-detail",
    ),
    path(
        "track/<str:order_reference>/",
        CustomerTrackingView.as_view(),
        name="customer-tracking",
    ),
]
