# dems_backend/asgi.py
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dems_backend.settings')

import django
django.setup()

from django.core.asgi import get_asgi_application
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.urls import re_path
from urllib.parse import parse_qs

from exams.consumers import LiveClassConsumer
from notifications.consumers import NotificationConsumer


# ============================================================
# JWT WebSocket Auth Middleware
# ============================================================
@database_sync_to_async
def get_user_from_token(token):
    from django.contrib.auth import get_user_model
    from rest_framework_simplejwt.tokens import AccessToken
    User = get_user_model()
    try:
        access = AccessToken(token)
        return User.objects.get(id=access['user_id'])
    except Exception:
        return AnonymousUser()


class JWTAuthMiddleware(BaseMiddleware):
    """Reads ?token=JWT from query string, sets scope['user']."""

    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get('query_string', b'').decode())
        token = query.get('token', [None])[0]

        if token:
            scope['user'] = await get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()

        return await super().__call__(scope, receive, send)


# ============================================================
# WebSocket URL patterns
# ============================================================
websocket_urlpatterns = [
    re_path(r'^ws/live-class/(?P<course_id>\d+)/$', LiveClassConsumer.as_asgi()),
    re_path(r'^ws/notifications/$', NotificationConsumer.as_asgi()),
]


# ============================================================
# Application
# ============================================================
application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': JWTAuthMiddleware(
        URLRouter(websocket_urlpatterns)
    ),
})