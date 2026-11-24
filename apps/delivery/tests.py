from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import RiderProfile, User, UserRole
from apps.delivery.models import Delivery, DeliveryStatus, RiderLocation
from apps.delivery.services import (
    assign_delivery,
    record_rider_location,
    update_delivery_status,
)


class DeliveryServiceTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="dispatcher",
            email="dispatcher@example.com",
            password="Password123!",
            role=UserRole.STAFF,
        )
        self.customer = User.objects.create_user(
            username="customer",
            email="customer@example.com",
            password="Password123!",
            role=UserRole.CUSTOMER,
        )
        self.rider_user = User.objects.create_user(
            username="rider",
            email="rider@example.com",
            password="Password123!",
            role=UserRole.RIDER,
        )
        self.other_rider_user = User.objects.create_user(
            username="rider2",
            email="rider2@example.com",
            password="Password123!",
            role=UserRole.RIDER,
        )
        self.rider = RiderProfile.objects.get(user=self.rider_user)
        self.rider.is_verified = True
        self.rider.is_available = True
        self.rider.location_consent = True
        self.rider.current_lat = Decimal("5.605000")
        self.rider.current_lng = Decimal("-0.184000")
        self.rider.save()
        self.other_rider = RiderProfile.objects.get(user=self.other_rider_user)
        self.other_rider.is_verified = True
        self.other_rider.is_available = False
        self.other_rider.save()

    def _assign(self, **overrides):
        payload = {
            "order_reference": "ORD-TEST-001",
            "customer": self.customer,
            "destination_lat": Decimal("5.573100"),
            "destination_lng": Decimal("-0.196900"),
            "destination_address": "Osu, Accra",
            "actor": self.staff,
        }
        payload.update(overrides)
        return assign_delivery(**payload)

    def test_assign_delivery_selects_available_rider_and_estimates_route(self):
        delivery = self._assign()
        self.assertEqual(delivery.status, DeliveryStatus.ASSIGNED)
        self.assertEqual(delivery.rider_id, self.rider.pk)
        self.assertEqual(delivery.customer_id, self.customer.pk)
        self.assertIsNotNone(delivery.distance_km)
        self.assertGreater(delivery.eta_minutes, 0)
        self.rider.refresh_from_db()
        self.assertFalse(self.rider.is_available)

    def test_assign_delivery_rejects_duplicate_order_reference(self):
        self._assign()
        with self.assertRaises(ValidationError):
            self._assign()

    def test_location_requires_transit_status_and_consent(self):
        delivery = self._assign()
        with self.assertRaises(ValidationError):
            record_rider_location(delivery, self.rider_user, "5.574000", "-0.197000")

        delivery.status = DeliveryStatus.IN_TRANSIT
        delivery.save(update_fields=["status", "updated_at"])
        self.rider.location_consent = False
        self.rider.save(update_fields=["location_consent", "updated_at"])
        with self.assertRaises(ValidationError):
            record_rider_location(delivery, self.rider_user, "5.574000", "-0.197000")

        self.rider.location_consent = True
        self.rider.save(update_fields=["location_consent", "updated_at"])
        location = record_rider_location(delivery, self.rider_user, "5.574000", "-0.197000")
        self.assertEqual(location.rider_id, self.rider.pk)
        self.assertEqual(RiderLocation.objects.filter(delivery=delivery).count(), 1)

    def test_other_rider_cannot_share_location(self):
        delivery = self._assign()
        delivery.status = DeliveryStatus.IN_TRANSIT
        delivery.save(update_fields=["status", "updated_at"])
        with self.assertRaises(PermissionDenied):
            record_rider_location(delivery, self.other_rider_user, "5.574000", "-0.197000")

    def test_status_transition_releases_rider_and_clears_location(self):
        delivery = self._assign()
        update_delivery_status(delivery, DeliveryStatus.IN_TRANSIT, actor=self.rider_user)
        self.assertIsNotNone(delivery.picked_up_at)

        update_delivery_status(delivery, DeliveryStatus.DELIVERED, actor=self.rider_user)
        self.assertIsNotNone(delivery.delivered_at)
        self.rider.refresh_from_db()
        self.assertTrue(self.rider.is_available)
        self.assertIsNone(self.rider.current_lat)
        self.assertIsNone(self.rider.current_lng)

    def test_invalid_transition_is_rejected(self):
        delivery = self._assign()
        with self.assertRaises(ValidationError):
            update_delivery_status(delivery, DeliveryStatus.DELIVERED, actor=self.rider_user)


class DeliveryAPITests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff-api",
            email="staff-api@example.com",
            password="Password123!",
            role=UserRole.STAFF,
        )
        self.customer = User.objects.create_user(
            username="customer-api",
            email="customer-api@example.com",
            password="Password123!",
            role=UserRole.CUSTOMER,
        )
        self.other_customer = User.objects.create_user(
            username="other-api",
            email="other-api@example.com",
            password="Password123!",
            role=UserRole.CUSTOMER,
        )
        self.rider_user = User.objects.create_user(
            username="rider-api",
            email="rider-api@example.com",
            password="Password123!",
            role=UserRole.RIDER,
        )
        self.rider = RiderProfile.objects.get(user=self.rider_user)
        self.rider.is_verified = True
        self.rider.location_consent = True
        self.rider.save()

    def _assign_via_api(self):
        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("delivery-api:delivery-list-create"),
            {
                "order_reference": "ORD-API-001",
                "customer_id": self.customer.pk,
                "destination_lat": "5.573100",
                "destination_lng": "-0.196900",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_staff_can_assign_and_rider_can_update_status_and_location(self):
        delivery = self._assign_via_api()
        self.client.force_login(self.rider_user)
        response = self.client.post(
            reverse("delivery-api:delivery-status", args=[delivery["id"]]),
            {"status": "IN_TRANSIT"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("delivery-api:delivery-location", args=[delivery["id"]]),
            {"latitude": "5.574000", "longitude": "-0.197000"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(RiderLocation.objects.count(), 1)

    def test_customer_can_track_own_delivery_only(self):
        delivery = self._assign_via_api()
        self.client.force_login(self.customer)
        response = self.client.get(
            reverse("delivery-api:delivery-track", args=[delivery["order_reference"]])
        )
        self.assertEqual(response.status_code, 200)

        self.client.force_login(self.other_customer)
        response = self.client.get(
            reverse("delivery-api:delivery-track", args=[delivery["order_reference"]])
        )
        self.assertEqual(response.status_code, 404)

    def test_rider_registration_requires_dispatch_role(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse("delivery-api:rider-list-create"),
            {
                "username": "newrider",
                "email": "newrider@example.com",
                "password": "Password123!",
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)


class DeliveryViewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff-web",
            email="staff-web@example.com",
            password="Password123!",
            role=UserRole.STAFF,
        )
        self.customer = User.objects.create_user(
            username="customer-web",
            email="customer-web@example.com",
            password="Password123!",
            role=UserRole.CUSTOMER,
        )
        self.rider_user = User.objects.create_user(
            username="rider-web",
            email="rider-web@example.com",
            password="Password123!",
            role=UserRole.RIDER,
        )
        self.rider = RiderProfile.objects.get(user=self.rider_user)
        self.rider.is_verified = True
        self.rider.save()
        self.delivery = assign_delivery(
            order_reference="ORD-WEB-001",
            customer=self.customer,
            destination_lat=Decimal("5.573100"),
            destination_lng=Decimal("-0.196900"),
            actor=self.staff,
        )

    def test_rider_dashboard_and_detail_render(self):
        self.client.force_login(self.rider_user)
        dashboard = self.client.get(reverse("delivery:rider-dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        detail = self.client.get(
            reverse("delivery:rider-delivery-detail", args=[self.delivery.pk])
        )
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, self.delivery.order_reference)

    def test_customer_tracking_page_renders(self):
        self.client.force_login(self.customer)
        response = self.client.get(
            reverse("delivery:customer-tracking", args=[self.delivery.order_reference])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Track order")


class DeliveryTaskTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff-task",
            email="staff-task@example.com",
            password="Password123!",
            role=UserRole.STAFF,
        )
        self.rider_user = User.objects.create_user(
            username="rider-task",
            email="rider-task@example.com",
            password="Password123!",
            role=UserRole.RIDER,
        )
        self.rider = RiderProfile.objects.get(user=self.rider_user)
        self.rider.is_verified = True
        self.rider.current_lat = Decimal("5.610000")
        self.rider.current_lng = Decimal("-0.182000")
        self.rider.save()
        self.delivery = assign_delivery(
            order_reference="ORD-TASK-001",
            destination_lat=Decimal("5.573100"),
            destination_lng=Decimal("-0.196900"),
            actor=self.staff,
        )

    def test_prune_rider_locations_removes_history_after_delivery(self):
        from apps.delivery.tasks import prune_rider_locations

        RiderLocation.objects.create(
            delivery=self.delivery,
            rider=self.rider,
            latitude=Decimal("5.574000"),
            longitude=Decimal("-0.197000"),
        )
        self.delivery.status = DeliveryStatus.DELIVERED
        self.delivery.delivered_at = timezone.now() - timedelta(hours=2)
        self.delivery.save(update_fields=["status", "delivered_at", "updated_at"])

        result = prune_rider_locations()
        self.assertEqual(result["deleted_locations"], 1)
        self.assertEqual(RiderLocation.objects.count(), 0)
        self.rider.refresh_from_db()
        self.assertIsNone(self.rider.current_lat)
