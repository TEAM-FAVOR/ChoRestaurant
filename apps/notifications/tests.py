from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from apps.accounts.models import CustomerProfile, UserRole
from apps.notifications.events import notify_order_event
from apps.notifications.models import Notification, NotificationChannel
from apps.notifications.services import (
    allowed_channels,
    enqueue_notification,
    mark_all_read,
    unread_count,
)
from apps.notifications.tasks import send_user_notification

User = get_user_model()


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
)
class NotificationServiceTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="notif-customer",
            email="notif-customer@example.com",
            password="Password123!",
            role=UserRole.CUSTOMER,
        )
        self.staff = User.objects.create_user(
            username="notif-staff",
            email="notif-staff@example.com",
            password="Password123!",
            role=UserRole.STAFF,
        )

    @patch("apps.notifications.events.publish_order_status")
    @patch("apps.notifications.tasks.publish_user_notification")
    def test_order_event_creates_in_app_and_email_notifications(self, publish, publish_status):
        notify_order_event(
            user=self.customer,
            order_reference="ORD-NOTIF-001",
            status="OUT_FOR_DELIVERY",
        )
        notifications = Notification.objects.for_user(self.customer)
        self.assertEqual(notifications.count(), 2)
        self.assertTrue(notifications.filter(channel=NotificationChannel.IN_APP).exists())
        self.assertTrue(notifications.filter(channel=NotificationChannel.EMAIL).exists())
        self.assertTrue(all(item.status == "SENT" for item in notifications))
        self.assertEqual(len(mail.outbox), 1)
        publish.assert_called_once()

    @patch("apps.notifications.tasks.publish_user_notification")
    def test_email_opt_out_is_respected_but_in_app_is_forced(self, publish):
        profile = CustomerProfile.objects.get(user=self.customer)
        profile.notify_email = False
        profile.save()
        self.assertEqual(
            allowed_channels(self.customer, ["IN_APP", "EMAIL"]),
            [NotificationChannel.IN_APP],
        )
        enqueue_notification(
            user=self.customer,
            title="Update",
            message="Your order moved.",
            channel=NotificationChannel.EMAIL,
        )
        self.assertFalse(Notification.objects.filter(channel=NotificationChannel.EMAIL).exists())
        self.assertEqual(publish.call_count, 0)

    @patch("apps.notifications.tasks.publish_user_notification")
    def test_send_order_notification_fans_out_to_requested_channels(self, publish):
        from apps.notifications.tasks import send_order_notification

        result = send_order_notification.apply(
            kwargs={
                "user_id": self.customer.pk,
                "order_reference": "ORD-FANOUT-001",
                "title": "Order update",
                "message": "Your order is ready.",
                "channels": [NotificationChannel.IN_APP],
                "event": "order.ready_for_pickup",
            },
            throw=False,
        )
        self.assertEqual(len(result.get()), 1)
        self.assertEqual(Notification.objects.count(), 1)

    @patch("apps.notifications.tasks.publish_user_notification")
    def test_retry_does_not_create_duplicate_notification(self, publish):
        result = send_user_notification.apply(
            kwargs={
                "user_id": self.customer.pk,
                "channel": NotificationChannel.IN_APP,
                "title": "Update",
                "message": "Your order moved.",
            },
            throw=False,
        )
        self.assertIsNotNone(result.get())
        self.assertEqual(Notification.objects.count(), 1)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class NotificationAPITests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username="api-customer",
            email="api-customer@example.com",
            password="Password123!",
            role=UserRole.CUSTOMER,
        )
        self.staff = User.objects.create_user(
            username="api-staff",
            email="api-staff@example.com",
            password="Password123!",
            role=UserRole.STAFF,
        )
        self.notification = Notification.objects.create(
            user=self.customer,
            title="Update",
            message="Order placed.",
            channel=NotificationChannel.IN_APP,
        )

    def test_unread_count_and_mark_read(self):
        from django.urls import reverse

        self.client.force_login(self.customer)
        response = self.client.get(reverse("notifications-api:notification-unread-count"))
        self.assertEqual(response.json()["unread_count"], 1)

        response = self.client.post(
            reverse("notifications-api:notification-read", args=[self.notification.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)
        self.assertEqual(unread_count(self.customer), 0)

    @patch("apps.notifications.tasks.publish_user_notification")
    def test_staff_can_broadcast(self, publish):
        from django.urls import reverse

        self.client.force_login(self.staff)
        response = self.client.post(
            reverse("notifications-api:notification-broadcast"),
            {
                "user_ids": [self.customer.pk],
                "title": "Promotion",
                "message": "20% off your next order.",
                "channels": ["IN_APP"],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 202)
        self.assertTrue(
            Notification.objects.filter(
                user=self.customer,
                title="Promotion",
            ).exists()
        )

    def test_mark_all_read(self):
        updated = mark_all_read(self.customer)
        self.assertEqual(updated, 1)
        self.assertEqual(unread_count(self.customer), 0)
