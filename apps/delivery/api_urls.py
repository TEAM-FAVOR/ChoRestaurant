from django.urls import path

from apps.delivery.api_views import (
    AvailableRidersAPIView,
    DeliveryDetailAPIView,
    DeliveryListAPIView,
    DeliveryStatusAPIView,
    DeliveryTrackAPIView,
    RiderAvailabilityAPIView,
    RiderConsentAPIView,
    RiderListCreateAPIView,
    RiderLocationAPIView,
)

app_name = "delivery-api"

urlpatterns = [
    path("riders/", RiderListCreateAPIView.as_view(), name="rider-list-create"),
    path("riders/available/", AvailableRidersAPIView.as_view(), name="riders-available"),
    path("riders/me/", RiderAvailabilityAPIView.as_view(), name="rider-me"),
    path("riders/me/consent/", RiderConsentAPIView.as_view(), name="rider-consent"),
    path("", DeliveryListAPIView.as_view(), name="delivery-list-create"),
    path("<int:pk>/", DeliveryDetailAPIView.as_view(), name="delivery-detail"),
    path("<int:pk>/status/", DeliveryStatusAPIView.as_view(), name="delivery-status"),
    path("<int:pk>/location/", RiderLocationAPIView.as_view(), name="delivery-location"),
    path(
        "track/<str:order_reference>/",
        DeliveryTrackAPIView.as_view(),
        name="delivery-track",
    ),
]
