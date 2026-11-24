# API Contracts & Backend Interface Documentation (Developer 1 Foundation)

**Project:** Restaurant Ordering & Delivery Management System  
**Module Owner:** Developer 1 (`config/`, `apps/core/`, `apps/accounts/`, `apps/menu/`)  
**Localization Defaults:** Country = `Ghana`, Currency = `GHS` (`GH₵`)

---

## 1. Overview & Authentication

All browser pages and JSON endpoints share **Django Session Authentication** with CSRF protection on mutating requests (`POST`, `PUT`, `PATCH`, `DELETE`).

### User Roles (`accounts.User.role`)

| Role | Enum Value | Description |
|---|---|---|
| Customer | `CUSTOMER` | Browses menu, manages profile & saved delivery addresses, places orders. |
| Restaurant Staff | `STAFF` | Manages food availability, receives orders, updates preparation status. |
| Dispatch Rider | `RIDER` | Manages rider availability, GPS sharing consent, and assigned deliveries. |
| Administrator | `ADMIN` | Full access to users, roles, menu CRUD, delivery fee settings, and reports. |

---

## 2. Core & Discovery Endpoints

### `GET /api/health/`
Verifies database connectivity and returns localization defaults.

**Response (`200 OK`):**
```json
{
  "status": "ok",
  "restaurant": "Cho Restaurant",
  "country": "Ghana",
  "currency": "GHS",
  "currency_symbol": "GH₵",
  "database_connected": true
}
```

### `GET /api/`
Lists all foundational API endpoints.

---

## 3. Accounts & Authentication Endpoints (`/api/accounts/`)

### `POST /api/accounts/register/`
Registers a new `CUSTOMER` user, automatically provisions their `CustomerProfile`, and starts an authenticated session.

**Request:**
```json
{
  "username": "akua_asante",
  "email": "akua@example.com",
  "password": "StrongPassword123!",
  "password_confirm": "StrongPassword123!",
  "first_name": "Akua",
  "last_name": "Asante",
  "phone": "+233240001111"
}
```

### `POST /api/accounts/login/`
Authenticates a user by **either username or email** (`identifier`).

**Request:**
```json
{
  "identifier": "akua@example.com",
  "password": "StrongPassword123!"
}
```

### `POST /api/accounts/logout/`
Logs out the current session.

### `GET / PATCH / PUT /api/accounts/profile/`
Retrieves or updates the current user's profile and customer notification preferences (`notify_email`, `notify_sms`, `default_address_id`). Note: `notify_in_app` is always `true` per PRD §4.9.

### `GET / POST /api/accounts/addresses/`
Lists all saved delivery addresses for the current user or creates a new delivery address.
- Defaults `country` to `"Ghana"`.
- The user's first saved address is automatically marked `is_default: true` and linked to `CustomerProfile.default_address`.

**Request (`POST`):**
```json
{
  "label": "Home",
  "line1": "14 Independence Avenue",
  "line2": "Ridge",
  "city": "Accra",
  "state": "Greater Accra",
  "postal_code": "GA-050-1234",
  "country": "Ghana",
  "latitude": "5.573100",
  "longitude": "-0.196900",
  "is_default": true
}
```

### `GET / PUT / PATCH / DELETE /api/accounts/addresses/<id>/`
Retrieves, updates, or deletes a saved address belonging to the current user.

### `POST /api/accounts/addresses/<id>/set-default/`
Sets the specified address as the user's default delivery address and updates `CustomerProfile.default_address`.

### `GET / PATCH /api/accounts/rider-profile/`
*(Requires `RIDER` role)*  
Retrieves or updates the current rider's `vehicle_type`, `plate_number`, `is_available`, and `location_consent` (required before GPS sharing per PRD §4.6).

### `GET /api/accounts/riders/?available_only=true`
*(Requires `STAFF` or `ADMIN` role)*  
Lists dispatch riders (filtered to active, available, verified riders when `available_only=true` for Developer 4 & 5 delivery assignment).

### `GET /api/accounts/users/?role=CUSTOMER`
*(Requires `STAFF` or `ADMIN` role)*  
Lists users with optional role filter.

### `PATCH /api/accounts/users/<id>/role/`
*(Requires `ADMIN` role)*  
Changes a user's role (`CUSTOMER`, `STAFF`, `RIDER`, `ADMIN`) and optionally sets `is_verified` on their `RiderProfile`.

---

## 4. Food & Menu Endpoints (`/api/menu/`)

### `GET / POST /api/menu/categories/`
- `GET`: Publicly lists active categories ordered by `sort_order, name`. Staff/Admin can pass `?include_inactive=true`.
- `POST`: *(Requires `STAFF` or `ADMIN`)* Creates a new food category (auto-generates unique `slug` if omitted).

### `GET / PUT / PATCH / DELETE /api/menu/categories/<slug>/`
- `GET`: Returns category details along with its available food items.
- `PUT / PATCH / DELETE`: *(Requires `STAFF` or `ADMIN`)* Updates or deletes the category.

### `GET / POST /api/menu/items/`
- `GET`: Publicly lists available food items in active categories.
  - Query parameters:
    - `?category=<slug_or_id>`
    - `?featured=true`
    - `?search=<keyword>` (or `?q=<keyword>`)
    - `?include_unavailable=true` *(Staff/Admin only)*
- `POST`: *(Requires `STAFF` or `ADMIN`)* Creates a new food item.

### `GET / PUT / PATCH / DELETE /api/menu/items/<slug>/`
- `GET`: Returns details for a single food item (`price`, `formatted_price`, `prep_time_minutes`, `is_available`, `is_featured`).
- `PUT / PATCH / DELETE`: *(Requires `STAFF` or `ADMIN`)* Updates or removes the food item.

### `POST /api/menu/items/<slug>/toggle-availability/`
*(Requires `STAFF` or `ADMIN`)*  
Toggles `is_available` on a food item (or sets it explicitly when `{"is_available": false}` is passed).

### `GET /api/menu/featured/`
Public endpoint returning active special meals and daily offers (`is_featured=True` and `is_available=True`).

---

## 5. Shared Python Services & Permissions for Developers 2–5

### Role Permissions (`apps.core.permissions`)
- **CBV Mixins:** `RoleRequiredMixin`, `CustomerRequiredMixin`, `StaffRequiredMixin`, `RiderRequiredMixin`, `AdminRequiredMixin`, `StaffOrAdminRequiredMixin`
- **FBV Decorators:** `@role_required(*roles)`, `@customer_required`, `@staff_required`, `@rider_required`, `@admin_required`, `@staff_or_admin_required`
- **DRF Permissions:** `IsCustomer`, `IsStaff`, `IsRider`, `IsAdminRole`, `IsStaffOrAdmin`, `IsOwnerOrAdmin`, `ReadOnlyOrStaffAdmin`

### Restaurant Settings & Maps Facade (`apps.core.models` & `apps.core.maps`)
- `RestaurantSettings.get_solo()`: Returns the cached singleton containing restaurant GPS origin (`origin_latitude`, `origin_longitude`), currency (`GHS`), and delivery fee configuration (`delivery_fee_mode`, `flat_delivery_fee`, `base_delivery_fee`, `base_distance_km`, `per_km_fee`, `max_delivery_radius_km`, `free_delivery_threshold`).
- `MapsFacade.evaluate_destination(dest_lat, dest_lng)`: Computes Haversine distance from the restaurant origin, checks `within_delivery_radius`, and estimates travel time in minutes.

---

## 6. Delivery, Tracking & Notifications (Developer 4)

Delivery, rider management, GPS, WebSocket and notification contracts are documented in
[`docs/DEV4_EVENT_CONTRACT.md`](DEV4_EVENT_CONTRACT.md).

Key routes:

- `GET/POST /api/delivery/` — list/assign deliveries.
- `POST /api/delivery/<id>/status/` — rider/staff delivery status update.
- `POST /api/delivery/<id>/location/` — consent-checked GPS ping.
- `GET /api/delivery/track/<order_reference>/` — customer tracking snapshot.
- `GET /api/notifications/` and `GET /api/notifications/unread-count/`.
- `WS /ws/orders/<reference>/`, `WS /ws/delivery/<id>/`, `WS /ws/notifications/`.
