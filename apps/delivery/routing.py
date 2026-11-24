from django.urls import re_path

from apps.delivery.consumers import DeliveryConsumer, NotificationConsumer, OrderConsumer

websocket_urlpatterns = [
    re_path(r"^ws/orders/(?P<reference>[-\w]+)/$", OrderConsumer.as_asgi()),
    re_path(r"^ws/delivery/(?P<delivery_id>\d+)/$", DeliveryConsumer.as_asgi()),
    re_path(r"^ws/notifications/$", NotificationConsumer.as_asgi()),
]
