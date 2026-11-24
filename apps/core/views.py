"""
Core health check and API discovery views.
"""
from django.conf import settings
from django.db import connection
from django.urls import reverse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check_view(request):
    """Health check endpoint verifying database connectivity and localization settings."""
    db_ok = False
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            db_ok = True
    except Exception:
        db_ok = False

    return Response(
        {
            "status": "ok" if db_ok else "degraded",
            "restaurant": settings.RESTAURANT_NAME,
            "country": settings.DEFAULT_COUNTRY,
            "currency": settings.DEFAULT_CURRENCY,
            "currency_symbol": settings.CURRENCY_SYMBOL,
            "database_connected": db_ok,
        },
        status=200 if db_ok else 503,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def api_root_view(request):
    """Root API index exposing Developer 1's foundation endpoints."""
    return Response(
        {
            "project": "Restaurant Ordering & Delivery Management System",
            "country": settings.DEFAULT_COUNTRY,
            "currency": settings.DEFAULT_CURRENCY,
            "endpoints": {
                "health": request.build_absolute_uri(reverse("health-check")),
                "auth_register": request.build_absolute_uri(reverse("accounts-api:register")),
                "auth_login": request.build_absolute_uri(reverse("accounts-api:login")),
                "auth_logout": request.build_absolute_uri(reverse("accounts-api:logout")),
                "profile": request.build_absolute_uri(reverse("accounts-api:profile")),
                "addresses": request.build_absolute_uri(reverse("accounts-api:address-list")),
                "rider_profile": request.build_absolute_uri(reverse("accounts-api:rider-profile")),
                "riders": request.build_absolute_uri(reverse("accounts-api:rider-list")),
                "menu_categories": request.build_absolute_uri(reverse("menu-api:category-list")),
                "menu_items": request.build_absolute_uri(reverse("menu-api:fooditem-list")),
                "menu_featured": request.build_absolute_uri(reverse("menu-api:featured-items")),
                "deliveries": request.build_absolute_uri(reverse("delivery-api:delivery-list-create")),
                "available_riders": request.build_absolute_uri(reverse("delivery-api:riders-available")),
                "notifications": request.build_absolute_uri(reverse("notifications-api:notification-list")),
            },
        }
    )
