# backend/services/notification_service.py
# COMPLETE MULTI-CHANNEL NOTIFICATION SERVICE

from django.core.mail import send_mail
from django.conf import settings
import requests
import logging
from .models import Notification
from twilio.rest import Client
import json

logger = logging.getLogger(__name__)

class MultiChannelNotificationService:
    """Send notifications through multiple channels: Email, SMS, WhatsApp, In-app"""
    
    def __init__(self):
        # Initialize Twilio for SMS
        self.twilio_client = Client(
            settings.TWILIO_SID if hasattr(settings, 'TWILIO_SID') else '',
            settings.TWILIO_AUTH_TOKEN if hasattr(settings, 'TWILIO_AUTH_TOKEN') else ''
        ) if hasattr(settings, 'TWILIO_SID') and settings.TWILIO_SID else None
        
        # WhatsApp API (would use Twilio or WhatsApp Business API)
        self.whatsapp_enabled = settings.WHATSAPP_ENABLED if hasattr(settings, 'WHATSAPP_ENABLED') else False
        self.whatsapp_token = settings.WHATSAPP_TOKEN if hasattr(settings, 'WHATSAPP_TOKEN') else ''
        self.whatsapp_phone = settings.WHATSAPP_PHONE if hasattr(settings, 'WHATSAPP_PHONE') else ''
    
    def send_notification(self, user, title, message, notification_type='SYSTEM_ALERT', link=''):
        """Send notification through all channels"""
        
        # 1. In-app notification
        notification = self._send_in_app(user, title, message, notification_type, link)
        
        # 2. Email notification (async)
        try:
            self._send_email(user, title, message)
        except Exception as e:
            logger.error(f"Email sending failed: {e}")
        
        # 3. SMS notification
        try:
            self._send_sms(user, message)
        except Exception as e:
            logger.error(f"SMS sending failed: {e}")
        
        # 4. WhatsApp notification
        try:
            self._send_whatsapp(user, message)
        except Exception as e:
            logger.error(f"WhatsApp sending failed: {e}")
        
        return notification
    
    def _send_in_app(self, user, title, message, notification_type, link):
        """Send in-app notification"""
        from notifications.models import Notification
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        notification = Notification.objects.create(
            recipient=user,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link
        )
        
        # Send WebSocket update
        try:
            channel_layer = get_channel_layer()
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
                        'is_read': False
                    }
                }
            )
        except Exception as e:
            logger.error(f"WebSocket notification failed: {e}")
        
        return notification
    
    def _send_email(self, user, title, message):
        """Send email notification"""
        
        if not user.email:
            return
        
        try:
            send_mail(
                subject=f"DEMS: {title}",
                message=f"""
Dear {user.full_name},

{message}

Best regards,
DEMS Team
Mekdela Amba University
                """,
                from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@dems.com',
                recipient_list=[user.email],
                fail_silently=True
            )
        except Exception as e:
            logger.error(f"Email error: {e}")
    
    def _send_sms(self, user, message):
        """Send SMS notification using Twilio"""
        if not self.twilio_client or not user.phone:
            return
        
        try:
            # Format phone number (must be in E.164 format)
            phone = user.phone
            if not phone.startswith('+'):
                # Assume Ethiopian format
                if phone.startswith('0'):
                    phone = '+251' + phone[1:]
                else:
                    phone = '+' + phone
            
            self.twilio_client.messages.create(
                body=f"DEMS: {message}",
                from_=settings.TWILIO_PHONE_NUMBER if hasattr(settings, 'TWILIO_PHONE_NUMBER') else '',
                to=phone
            )
        except Exception as e:
            logger.error(f"SMS error: {e}")
    
    def _send_whatsapp(self, user, message):
        """Send WhatsApp notification"""
        if not self.whatsapp_enabled or not user.phone:
            return
        
        try:
            # Format phone
            phone = user.phone
            if not phone.startswith('+'):
                if phone.startswith('0'):
                    phone = '+251' + phone[1:]
                else:
                    phone = '+' + phone
            
            # WhatsApp Business API
            url = f"https://graph.facebook.com/v17.0/{self.whatsapp_phone}/messages"
            headers = {
                'Authorization': f"Bearer {self.whatsapp_token}",
                'Content-Type': 'application/json'
            }
            data = {
                'messaging_product': 'whatsapp',
                'to': phone.replace('+', ''),
                'type': 'text',
                'text': {'body': f"DEMS: {message}"}
            }
            
            response = requests.post(url, headers=headers, json=data)
            if response.status_code != 200:
                logger.warning(f"WhatsApp API error: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"WhatsApp error: {e}")

# Singleton
notification_service = MultiChannelNotificationService()