# dems_backend/routing.py

from django.urls import re_path

# Import consumers
from exams.consumers import LiveClassConsumer
from notifications.consumers import NotificationConsumer

# FIXED: Combined all websocket patterns in one list
websocket_urlpatterns = [
    re_path(r'ws/live-class/(?P<course_id>\d+)/$', LiveClassConsumer.as_asgi()),
    re_path(r'ws/notifications/(?P<user_id>\d+)/$', NotificationConsumer.as_asgi()),
]