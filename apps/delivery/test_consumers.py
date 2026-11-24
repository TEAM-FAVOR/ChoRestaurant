from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.layers import channel_layers
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import AnonymousUser
from django.test import TestCase, override_settings

from apps.accounts.models import RiderProfile, User, UserRole
from apps.delivery.realtime import publish_delivery_location
from apps.delivery.services import assign_delivery
from config.asgi import application

IN_MEMORY_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}


@override_settings(CHANNEL_LAYERS=IN_MEMORY_LAYERS)
class DeliveryConsumerTests(TestCase):
    def setUp(self):
        channel_layers.backends = {}
        self.staff = User.objects.create_user(
            username="ws-staff",
            email="ws-staff@example.com",
            password="Password123!",
            role=UserRole.STAFF,
        )
        self.customer = User.objects.create_user(
            username="ws-customer",
            email="ws-customer@example.com",
            password="Password123!",
            role=UserRole.CUSTOMER,
        )
        self.other_customer = User.objects.create_user(
            username="ws-other",
            email="ws-other@example.com",
            password="Password123!",
            role=UserRole.CUSTOMER,
        )
        self.rider_user = User.objects.create_user(
            username="ws-rider",
            email="ws-rider@example.com",
            password="Password123!",
            role=UserRole.RIDER,
        )
        self.rider = RiderProfile.objects.get(user=self.rider_user)
        self.rider.is_verified = True
        self.rider.save()
        self.delivery = assign_delivery(
            order_reference="ORD-WS-001",
            customer=self.customer,
            actor=self.staff,
        )

    def tearDown(self):
        channel_layers.backends = {}

    def _communicator(self, path, user):
        communicator = WebsocketCommunicator(
            application,
            path,
            headers=[(b"origin", b"http://testserver")],
        )
        communicator.scope["user"] = user
        return communicator

    def test_rider_receives_live_location_broadcast(self):
        async def scenario():
            communicator = self._communicator(
                f"/ws/delivery/{self.delivery.pk}/",
                self.rider_user,
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            hello = await communicator.receive_json_from()
            self.assertEqual(hello["type"], "connected")

            await database_sync_to_async(publish_delivery_location)(
                self.delivery.pk,
                "5.574000",
                "-0.197000",
            )
            message = await communicator.receive_json_from()
            self.assertEqual(message["type"], "location")
            self.assertEqual(message["lat"], "5.574000")
            await communicator.disconnect()

        async_to_sync(scenario)()

    def test_customer_cannot_subscribe_to_another_customers_delivery(self):
        async def scenario():
            communicator = self._communicator(
                f"/ws/delivery/{self.delivery.pk}/",
                self.other_customer,
            )
            connected, _ = await communicator.connect()
            self.assertFalse(connected)
            await communicator.disconnect()

        async_to_sync(scenario)()

    def test_owner_can_subscribe_to_order_status(self):
        async def scenario():
            communicator = self._communicator(
                "/ws/orders/ORD-WS-001/",
                self.customer,
            )
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            message = await communicator.receive_json_from()
            self.assertEqual(message["type"], "connected")
            await communicator.disconnect()

        async_to_sync(scenario)()

    def test_anonymous_websocket_is_rejected(self):
        async def scenario():
            communicator = self._communicator(
                f"/ws/delivery/{self.delivery.pk}/",
                AnonymousUser(),
            )
            connected, _ = await communicator.connect()
            self.assertFalse(connected)
            await communicator.disconnect()

        async_to_sync(scenario)()
