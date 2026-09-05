# backend/services/video_service.py
# COMPLETE VIDEO CONFERENCING SYSTEM

import asyncio
import json
import logging
from django.utils import timezone
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

logger = logging.getLogger(__name__)

class LiveClassRoomConsumer(AsyncWebsocketConsumer):
    """Advanced Live Class Room with WebRTC signaling"""
    
    async def connect(self):
        self.course_id = self.scope['url_route']['kwargs']['course_id']
        self.room_group_name = f'live_class_{self.course_id}'
        self.user = self.scope['user']
        
        await self.accept()
        
        if not self.user.is_authenticated:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        # Send join notification
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_join',
                'user': self.user.full_name,
                'role': self.user.role,
                'user_id': self.user.id,
                'connection_time': timezone.now().isoformat()
            }
        )
        
        # Track presence
        await self.update_user_status('ONLINE')
    
    async def disconnect(self, close_code):
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
        
        # Send leave notification
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_leave',
                'user': self.user.full_name,
                'user_id': self.user.id,
                'disconnect_time': timezone.now().isoformat()
            }
        )
        
        # Update presence
        await self.update_user_status('OFFLINE')
    
    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type')
        
        # Handle different message types
        
        if message_type == 'chat':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': data.get('message'),
                    'user': self.user.full_name,
                    'role': self.user.role,
                    'user_id': self.user.id,
                    'timestamp': timezone.now().isoformat()
                }
            )
        
        elif message_type == 'offer':
            # WebRTC offer (teacher sends to student)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'webrtc_offer',
                    'offer': data.get('sdp'),
                    'sender': self.user.full_name,
                    'sender_role': self.user.role,
                    'sender_id': self.user.id
                }
            )
        
        elif message_type == 'answer':
            # WebRTC answer (student sends to teacher)
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'webrtc_answer',
                    'answer': data.get('sdp'),
                    'sender': self.user.full_name,
                    'sender_role': self.user.role,
                    'sender_id': self.user.id
                }
            )
        
        elif message_type == 'ice_candidate':
            # ICE candidate exchange
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'ice_candidate',
                    'candidate': data.get('candidate'),
                    'sender_id': self.user.id
                }
            )
        
        elif message_type == 'toggle_video':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'toggle_video',
                    'user': self.user.full_name,
                    'video_enabled': data.get('enabled', True)
                }
            )
        
        elif message_type == 'toggle_audio':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'toggle_audio',
                    'user': self.user.full_name,
                    'audio_enabled': data.get('enabled', True)
                }
            )
        
        elif message_type == 'screen_share':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'screen_share',
                    'user': self.user.full_name,
                    'sharing': data.get('sharing', True)
                }
            )
        
        elif message_type == 'raise_hand':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'raise_hand',
                    'user': self.user.full_name,
                    'raised': data.get('raised', True)
                }
            )
        
        elif message_type == 'reaction':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'reaction',
                    'user': self.user.full_name,
                    'reaction': data.get('reaction', '👍')
                }
            )
        
        elif message_type == 'whiteboard':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'whiteboard',
                    'user': self.user.full_name,
                    'action': data.get('action'),
                    'data': data.get('data', {})
                }
            )
        
        elif message_type == 'recording_status':
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'recording_status',
                    'user': self.user.full_name,
                    'recording': data.get('recording', False)
                }
            )
    
    # Handler methods
    
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat',
            'message': event['message'],
            'user': event['user'],
            'role': event['role'],
            'user_id': event.get('user_id'),
            'timestamp': event.get('timestamp')
        }))
    
    async def webrtc_offer(self, event):
        if event.get('sender_id') != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'offer',
                'sdp': event['offer'],
                'sender': event['sender'],
                'sender_role': event['sender_role'],
                'sender_id': event.get('sender_id')
            }))
    
    async def webrtc_answer(self, event):
        if event.get('sender_id') != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'answer',
                'sdp': event['answer'],
                'sender': event['sender'],
                'sender_role': event['sender_role'],
                'sender_id': event.get('sender_id')
            }))
    
    async def ice_candidate(self, event):
        if event.get('sender_id') != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'ice_candidate',
                'candidate': event['candidate'],
                'sender_id': event.get('sender_id')
            }))
    
    async def toggle_video(self, event):
        await self.send(text_data=json.dumps({
            'type': 'toggle_video',
            'user': event['user'],
            'video_enabled': event['video_enabled']
        }))
    
    async def toggle_audio(self, event):
        await self.send(text_data=json.dumps({
            'type': 'toggle_audio',
            'user': event['user'],
            'audio_enabled': event['audio_enabled']
        }))
    
    async def screen_share(self, event):
        await self.send(text_data=json.dumps({
            'type': 'screen_share',
            'user': event['user'],
            'sharing': event['sharing']
        }))
    
    async def raise_hand(self, event):
        await self.send(text_data=json.dumps({
            'type': 'raise_hand',
            'user': event['user'],
            'raised': event['raised']
        }))
    
    async def reaction(self, event):
        await self.send(text_data=json.dumps({
            'type': 'reaction',
            'user': event['user'],
            'reaction': event['reaction']
        }))
    
    async def whiteboard(self, event):
        await self.send(text_data=json.dumps({
            'type': 'whiteboard',
            'user': event['user'],
            'action': event['action'],
            'data': event['data']
        }))
    
    async def recording_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'recording_status',
            'user': event['user'],
            'recording': event['recording']
        }))
    
    async def user_join(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_join',
            'user': event['user'],
            'role': event.get('role', ''),
            'user_id': event.get('user_id'),
            'connection_time': event.get('connection_time')
        }))
    
    async def user_leave(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_leave',
            'user': event['user'],
            'user_id': event.get('user_id'),
            'disconnect_time': event.get('disconnect_time')
        }))
    
    # Database helpers
    
    @database_sync_to_async
    def update_user_status(self, status):
        from chat.models import UserStatus
        UserStatus.objects.update_or_create(
            user=self.user,
            defaults={'status': status}
        )
    
    @database_sync_to_async
    def log_event(self, event_type, details):
        from proctoring.models import ProctorLog
        return ProctorLog.objects.create(
            event_type=event_type,
            details=details
        )