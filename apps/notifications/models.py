from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class NotificationChannel(models.TextChoices):
    IN_APP = "IN_APP", "In App"
    EMAIL = "EMAIL", "Email"
    SMS = "SMS", "SMS"


class NotificationStatus(models.TextChoices):
    PENDING = "PENDING", "Pending"
    SENT = "SENT", "Sent"
    FAILED = "FAILED", "Failed"


class NotificationQuerySet(models.QuerySet):
    def unread(self):
        return self.filter(is_read=False)

    def for_user(self, user):
        return self.filter(user=user)

    def mark_all_read(self):
        return self.update(is_read=True)


class Notification(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    order_reference = models.CharField(max_length=24, blank=True, db_index=True)
    delivery_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    event = models.CharField(max_length=80, blank=True, db_index=True)
    title = models.CharField(max_length=150)
    message = models.TextField()
    channel = models.CharField(
        max_length=10,
        choices=NotificationChannel.choices,
        default=NotificationChannel.IN_APP,
        db_index=True,
    )
    status = models.CharField(
        max_length=10,
        choices=NotificationStatus.choices,
        default=NotificationStatus.PENDING,
        db_index=True,
    )
    is_read = models.BooleanField(default=False, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    context = models.JSONField(default=dict, blank=True)

    objects = NotificationQuerySet.as_manager()

    class Meta:
        db_table = "notifications_notification"
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_read", "-created_at"], name="idx_notification_user"),
            models.Index(fields=["event"], name="idx_notification_event"),
        ]

    def __str__(self) -> str:
        return f"Notification({self.user_id}, {self.channel}, {self.title})"

    def mark_read(self) -> None:
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=["is_read", "updated_at"])

    def mark_sent(self) -> None:
        self.status = NotificationStatus.SENT
        self.sent_at = timezone.now()
        self.last_error = ""
        self.save(update_fields=["status", "sent_at", "last_error", "updated_at"])

    def mark_failed(self, error: str) -> None:
        self.status = NotificationStatus.FAILED
        self.last_error = str(error)[:2000]
        self.save(update_fields=["status", "last_error", "updated_at"])
