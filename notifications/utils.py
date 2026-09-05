# notifications/utils.py - COMPLETE FIXED VERSION

from django.contrib.auth import get_user_model
from .models import Notification
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
from django.core.mail import send_mass_mail
from twilio.rest import Client
User = get_user_model()
# notifications/utils.py - ADD:
def send_bulk_email(subject, message, recipients):
    """Send email to multiple recipients"""
    messages = [
        (subject, message, settings.DEFAULT_FROM_EMAIL, [recipient])
        for recipient in recipients
    ]
    return send_mass_mail(messages)

def send_sms(phone_number, message):
    """Send SMS using Twilio"""
    client = Client(settings.TWILIO_SID, settings.TWILIO_AUTH_TOKEN)
    return client.messages.create(
        body=message,
        from_=settings.TWILIO_PHONE_NUMBER,
        to=phone_number
    )
def send_notification(recipient_user=None, recipient_roles=None, title='', message='', 
                     notification_type='SYSTEM_ALERT', link=''):
    """
    Send a notification to a user or a group of users by role.
    
    Args:
        recipient_user: Single user instance
        recipient_roles: List of roles (e.g., ['ADMIN', 'FINANCE'])
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        link: Optional link for the notification
    """
    users = []
    
    if recipient_user:
        users = [recipient_user]
    elif recipient_roles:
        users = User.objects.filter(role__in=recipient_roles, is_active=True)
    
    if not users:
        return 0
    
    notifications_created = 0
    channel_layer = get_channel_layer()
    
    for user in users:
        # Create notification in database
        notification = Notification.objects.create(
            recipient=user,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link
        )
        notifications_created += 1
        
        # Send real-time notification via WebSocket
        try:
            async_to_sync(channel_layer.group_send)(
                f'notifications_{user.id}',
                {
                    'type': 'send_notification',
                    'notification': {
                        'id': notification.id,
                        'title': title,
                        'message': message,
                        'notification_type': notification_type,
                        'link': link,
                        'created_at': notification.created_at.isoformat(),
                        'is_read': False
                    }
                }
            )
        except Exception as e:
            # WebSocket may not be connected, but notification is saved
            print(f"WebSocket notification failed for user {user.id}: {e}")
    
    return notifications_created


def send_notification_to_all(title='', message='', notification_type='SYSTEM_ALERT', link=''):
    """Send notification to all active users"""
    users = User.objects.filter(is_active=True)
    notifications_created = 0
    channel_layer = get_channel_layer()
    
    for user in users:
        notification = Notification.objects.create(
            recipient=user,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link
        )
        notifications_created += 1
        
        try:
            async_to_sync(channel_layer.group_send)(
                f'notifications_{user.id}',
                {
                    'type': 'send_notification',
                    'notification': {
                        'id': notification.id,
                        'title': title,
                        'message': message,
                        'notification_type': notification_type,
                        'link': link,
                        'created_at': notification.created_at.isoformat(),
                        'is_read': False
                    }
                }
            )
        except Exception as e:
            print(f"WebSocket notification failed for user {user.id}: {e}")
    
    return notifications_created