"""
ASGI config for Restaurant Ordering & Delivery Management System.
Note: Developer 4 owns real-time WebSocket routing in config/asgi.py.
This baseline initializes Django ASGI and hooks in Channels ProtocolTypeRouter when available.
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

django_asgi_app = get_asgi_application()

try:
    from channels.auth import AuthMiddlewareStack
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.security.websocket import AllowedHostsOriginValidator

    from apps.delivery.routing import websocket_urlpatterns

    application = ProtocolTypeRouter(
        {
            "http": django_asgi_app,
            "websocket": AllowedHostsOriginValidator(
                AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
            ),
        }
    )
except ImportError:
    application = django_asgi_app
