# dems_backend/routing.py - COMPLETE FIXED

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import re_path

# Import consumers
from exams.consumers import LiveClassConsumer
from notifications.consumers import NotificationConsumer

websocket_urlpatterns = [
    re_path(r'ws/live-class/(?P<course_id>\d+)/$', LiveClassConsumer.as_asgi()),
    re_path(r'ws/notifications/$', NotificationConsumer.as_asgi()),
]

application = ProtocolTypeRouter({
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})