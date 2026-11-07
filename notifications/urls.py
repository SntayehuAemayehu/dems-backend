from django.urls import path
from . import views
# ✅ ADDED: Import the new view so Django can find it
from .views import SendBulkSMSView

urlpatterns = [
    path('', views.NotificationListView.as_view(), name='notifications'),
    path('<int:pk>/read/', views.NotificationMarkReadView.as_view(), name='mark-read'),
    path('mark-all-read/', views.NotificationMarkAllReadView.as_view(), name='mark-all-read'),
    path('unread-count/', views.UnreadCountView.as_view(), name='unread-count'),
    
    # ✅ ADDED: The bulk SMS endpoint
    path('send-bulk-sms/', SendBulkSMSView.as_view(), name='send-bulk-sms'),
]