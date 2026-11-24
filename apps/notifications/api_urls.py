from django.urls import path

from apps.notifications.api_views import (
    NotificationBroadcastAPIView,
    NotificationListAPIView,
    NotificationMarkAllReadAPIView,
    NotificationMarkReadAPIView,
    NotificationUnreadCountAPIView,
    OrderNotificationAPIView,
)

app_name = "notifications-api"

urlpatterns = [
    path("", NotificationListAPIView.as_view(), name="notification-list"),
    path("unread-count/", NotificationUnreadCountAPIView.as_view(), name="notification-unread-count"),
    path("read-all/", NotificationMarkAllReadAPIView.as_view(), name="notification-read-all"),
    path("<int:pk>/read/", NotificationMarkReadAPIView.as_view(), name="notification-read"),
    path("broadcast/", NotificationBroadcastAPIView.as_view(), name="notification-broadcast"),
    path("order-event/", OrderNotificationAPIView.as_view(), name="order-notification"),
]
