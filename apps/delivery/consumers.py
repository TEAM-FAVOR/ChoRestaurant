from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from apps.delivery.integrations import get_order_owner_id
from apps.delivery.models import Delivery
from apps.delivery.realtime import delivery_group_name, order_group_name
from apps.notifications.realtime import user_group_name


class OrderConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.order_reference = self.scope["url_route"]["kwargs"]["reference"]
        self.group_name = order_group_name(self.order_reference)
        user = self.scope.get("user")

        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        if not await self._can_access(user):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json(
            {
                "type": "connected",
                "order_reference": self.order_reference,
            }
        )

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("action") == "ping":
            await self.send_json({"type": "pong"})

    async def status(self, event):
        await self.send_json(
            {
                "type": "status",
                "order_reference": event.get("order_reference"),
                "status": event.get("status"),
                "eta_minutes": event.get("eta_minutes"),
                "delivery_id": event.get("delivery_id"),
                "updated_at": event.get("updated_at"),
            }
        )

    async def eta(self, event):
        await self.send_json(
            {
                "type": "eta",
                "delivery_id": event.get("delivery_id"),
                "order_reference": event.get("order_reference"),
                "eta_minutes": event.get("eta_minutes"),
                "updated_at": event.get("updated_at"),
            }
        )

    @database_sync_to_async
    def _can_access(self, user):
        if user.is_admin_role or user.is_restaurant_staff:
            return True
        if Delivery.objects.filter(
            order_reference=self.order_reference,
            customer=user,
        ).exists():
            return True
        if user.is_rider and Delivery.objects.filter(
            order_reference=self.order_reference,
            rider__user=user,
        ).exists():
            return True
        return get_order_owner_id(self.order_reference) == user.pk


class DeliveryConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.delivery_id = int(self.scope["url_route"]["kwargs"]["delivery_id"])
        self.group_name = delivery_group_name(self.delivery_id)
        user = self.scope.get("user")

        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return
        delivery = await self._get_delivery()
        if delivery is None or not await self._can_access(user, delivery):
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json(
            {
                "type": "connected",
                "delivery_id": self.delivery_id,
                "order_reference": delivery["order_reference"],
                "status": delivery["status"],
                "eta_minutes": delivery["eta_minutes"],
                "lat": delivery["lat"],
                "lng": delivery["lng"],
            }
        )

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("action") == "ping":
            await self.send_json({"type": "pong"})

    async def location(self, event):
        await self.send_json(
            {
                "type": "location",
                "delivery_id": event.get("delivery_id"),
                "lat": event.get("lat"),
                "lng": event.get("lng"),
                "eta_minutes": event.get("eta_minutes"),
                "ts": event.get("ts"),
            }
        )

    async def status(self, event):
        await self.send_json(
            {
                "type": "status",
                "delivery_id": event.get("delivery_id"),
                "order_reference": event.get("order_reference"),
                "status": event.get("status"),
                "previous_status": event.get("previous_status"),
                "updated_at": event.get("updated_at"),
            }
        )

    async def eta(self, event):
        await self.send_json(
            {
                "type": "eta",
                "delivery_id": event.get("delivery_id"),
                "order_reference": event.get("order_reference"),
                "eta_minutes": event.get("eta_minutes"),
                "updated_at": event.get("updated_at"),
            }
        )

    @database_sync_to_async
    def _get_delivery(self):
        delivery = (
            Delivery.objects.filter(pk=self.delivery_id)
            .select_related("rider", "rider__user", "customer")
            .first()
        )
        if delivery is None:
            return None
        return {
            "order_reference": delivery.order_reference,
            "status": delivery.status,
            "eta_minutes": delivery.eta_minutes,
            "lat": str(delivery.current_lat) if delivery.current_lat is not None else None,
            "lng": str(delivery.current_lng) if delivery.current_lng is not None else None,
            "delivery": delivery,
        }

    @database_sync_to_async
    def _can_access(self, user, delivery_payload):
        delivery = delivery_payload["delivery"]
        if user.is_admin_role or user.is_restaurant_staff:
            return True
        if delivery.customer_id == user.pk:
            return True
        return delivery.rider_id is not None and delivery.rider.user_id == user.pk


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if user is None or not user.is_authenticated:
            await self.close(code=4401)
            return

        self.user_id = user.pk
        self.group_name = user_group_name(self.user_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send_json({"type": "connected", "user_id": self.user_id})

    async def disconnect(self, code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive_json(self, content, **kwargs):
        if content.get("action") == "ping":
            await self.send_json({"type": "pong"})

    async def notification(self, event):
        await self.send_json(
            {
                "type": "notification",
                "notification": event.get("notification"),
            }
        )
