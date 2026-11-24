"""
Root URL configuration for Restaurant Ordering & Delivery Management System.
Developer 1 mounts accounts, menu, core healthcheck, and media serving in dev.
Other developers register their app URLs in their respective modules.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from apps.core.views import api_root_view, health_check_view

admin.site.site_header = f"{settings.RESTAURANT_NAME} Administration"
admin.site.site_title = f"{settings.RESTAURANT_NAME} Admin Portal"
admin.site.index_title = "Restaurant Ordering & Delivery Management"

urlpatterns = [
    path("admin/", admin.site.urls),
    # Core health & foundation discovery endpoints
    path("api/", api_root_view, name="api-root"),
    path("api/health/", health_check_view, name="health-check"),
    # Developer 1: Accounts & Authentication (web + API)
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("api/accounts/", include("apps.accounts.api_urls", namespace="accounts-api")),
    # Developer 1: Menu & Categories (web admin/catalog + API)
    path("menu/", include("apps.menu.urls", namespace="menu")),
    path("api/menu/", include("apps.menu.api_urls", namespace="menu-api")),
    # Developer 4: Delivery pages and APIs (rider dashboard, live tracking)
    path("delivery/", include("apps.delivery.urls", namespace="delivery")),
    path("api/delivery/", include("apps.delivery.api_urls", namespace="delivery-api")),
    path(
        "api/notifications/",
        include("apps.notifications.api_urls", namespace="notifications-api"),
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
