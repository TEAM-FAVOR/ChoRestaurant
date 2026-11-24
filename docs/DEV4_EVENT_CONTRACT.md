# Developer 4 Integration Contract

This document defines the delivery, real-time and notification interfaces owned by Developer 4.

## REST endpoints

### Delivery (`/api/delivery/`)

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/riders/` | Staff/Admin | List riders; `?available_only=true` filters to verified, available riders. |
| `POST` | `/riders/` | Staff/Admin | Register a rider and provision `RiderProfile`. |
| `GET` | `/riders/available/` | Staff/Admin | Shortcut for available riders. |
| `GET/PATCH` | `/riders/me/` | Rider | Rider availability summary and `{"is_available": true|false}`. |
| `PATCH` | `/riders/me/consent/` | Rider | `{"location_consent": true|false}`. Disabling consent clears stored coordinates. |
| `GET` | `/` | Authenticated | List deliveries visible to the caller. Filters: `status`, `rider_id`, `rider=me`, `customer_id`, `order_reference`. |
| `POST` | `/` | Staff/Admin | Assign a delivery. |
| `GET` | `/<id>/` | Authenticated | Delivery detail. |
| `POST` | `/<id>/status/` | Assigned rider / Staff / Admin | `{"status": "IN_TRANSIT"|"DELIVERED"|"FAILED"|"CANCELLED"}`. |
| `POST` | `/<id>/location/` | Assigned rider | `{"latitude": 5.574, "longitude": -0.197}`. |
| `GET` | `/track/<order_reference>/` | Authenticated | Customer/staff/rider tracking snapshot. |

Assignment payload:

```json
{
  "order_reference": "ORD-20261123-A1B2C3",
  "order_id": 123,
  "customer_id": 45,
  "rider_id": 8,
  "destination_lat": "5.573100",
  "destination_lng": "-0.196900",
  "destination_address": "Osu, Accra",
  "notes": "Call on arrival"
}
```

`rider_id` is optional; the service selects the closest available verified rider. `customer_id`,
coordinates and address are optional when Developer 3's `Order` model is available because
`apps.delivery.integrations` reads them from the order when present.

### Notifications (`/api/notifications/`)

| Method | Path | Access | Purpose |
| --- | --- | --- | --- |
| `GET` | `/` | Authenticated | Notification list; `?unread=true`, `?channel=IN_APP`. |
| `GET` | `/unread-count/` | Authenticated | `{"unread_count": n}`. |
| `POST` | `/<id>/read/` | Authenticated | Mark one notification read. |
| `POST` | `/read-all/` | Authenticated | Mark all notifications read. |
| `POST` | `/broadcast/` | Staff/Admin | Queue in-app/email/SMS notifications for user IDs. |
| `POST` | `/order-event/` | Staff/Admin | Publish order status event and notify a customer. |

## WebSocket contracts

Connect using session authentication and an allowed `Origin` header.

| Path | Group | Authorization |
| --- | --- | --- |
| `/ws/orders/<reference>/` | `order_<reference>` | Staff/Admin, assigned rider, order owner. |
| `/ws/delivery/<id>/` | `delivery_<id>` | Staff/Admin, assigned rider, delivery customer. |
| `/ws/notifications/` | `user_<id>` | Authenticated user only. |

Payloads sent by the server:

```json
{"type": "status", "order_reference": "ORD-...", "status": "OUT_FOR_DELIVERY", "eta_minutes": 12, "delivery_id": 7, "updated_at": "..."}
{"type": "location", "delivery_id": 7, "lat": "5.574000", "lng": "-0.197000", "eta_minutes": 9, "ts": "..."}
{"type": "eta", "delivery_id": 7, "order_reference": "ORD-...", "eta_minutes": 9, "updated_at": "..."}
{"type": "status", "delivery_id": 7, "order_reference": "ORD-...", "status": "IN_TRANSIT", "previous_status": "ASSIGNED", "updated_at": "..."}
{"type": "notification", "notification": {"id": 1, "title": "...", "message": "...", "event": "...", "created_at": "..."}}
```

Clients may send `{"action": "ping"}` and receive `{"type": "pong"}`. Status changes are not
accepted from WebSocket clients; use the REST endpoints.

## Developer 3 event integration

Call these Python services after order/payment state changes:

```python
from apps.notifications.events import notify_order_event, notify_payment_event

notify_order_event(
    user=order.customer,
    order_reference=order.reference,
    status="READY_FOR_PICKUP",
    notify_staff=True,
)
notify_order_event(
    user=order.customer,
    order_reference=order.reference,
    status="OUT_FOR_DELIVERY",
    delivery_id=delivery.pk,
)
notify_payment_event(
    user=order.customer,
    order_reference=order.reference,
    status="success",
)
```

`notify_order_event` both broadcasts on `order_<reference>` and queues in-app/email notifications
through Celery. Do not call `publish_order_status` and `notify_order_event` separately for the
same status change; that would duplicate WebSocket messages.

Delivery status to order status mapping used by Developer 4:

| Delivery status | Broadcast order status |
| --- | --- |
| `IN_TRANSIT` | `OUT_FOR_DELIVERY` |
| `DELIVERED` | `DELIVERED` |
| `FAILED` | `CANCELLED` |
| `CANCELLED` | `CANCELLED` |

Assignment broadcasts `READY_FOR_PICKUP` plus a delivery-group `ASSIGNED` event.

## Celery tasks

| Task | Purpose |
| --- | --- |
| `notifications.send_user_notification` | Creates one notification row, delivers in-app push or email, retries with exponential backoff and logs permanent failures. |
| `notifications.send_order_notification` | Fan-out task for multiple channels. |
| `delivery.recompute_eta` | Recomputes ETA from latest GPS point to destination and broadcasts `eta`. |
| `delivery.prune_rider_locations` | Deletes ping history for completed deliveries and clears stale rider coordinates. |
| `delivery.release_stale_rider_locations` | Clears coordinates for riders whose GPS signal went stale. |

`delivery.prune_rider_locations` is registered in `CELERY_BEAT_SCHEDULE` to run hourly.

Run the real-time stack with:

```bash
redis-server
celery -A config worker -l info
celery -A config beat -l info
daphne -b 0.0.0.0 -p 8000 config.asgi:application
```

For isolated local work without Redis: `USE_IN_MEMORY_CHANNEL_LAYER=True` and
`CELERY_TASK_ALWAYS_EAGER=True`.

## Privacy and coordination notes

- GPS pings are accepted only for the assigned rider, only in `IN_TRANSIT`, and only when
  `RiderProfile.location_consent=True`.
- Location history is pruned after delivery completion; clearing consent also clears coordinates.
- `apps.delivery.integrations` discovers Developer 3's `Order` model at runtime, so no hard
  migration dependency is required. Once Developer 3's migration exists, the nullable
  `delivery_delivery.order_id` can be converted to a real FK in a coordinated migration.
- Developer 1's `feature/dev1-infrastructure` branch already makes `current_lat`/`current_lng`
  read-only; keep those fields server-managed so all GPS writes go through the consent-checked
  Developer 4 endpoint.
