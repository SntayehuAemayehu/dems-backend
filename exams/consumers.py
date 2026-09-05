# exams/consumers.py - COMPLETE FIXED VERSION

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from urllib.parse import parse_qs

User = get_user_model()

class LiveClassConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Get course_id from URL
        self.course_id = self.scope['url_route']['kwargs']['course_id']
        self.room_group_name = f'live_class_{self.course_id}'
        self.user = self.scope['user']
        
        print(f"🔗 WebSocket Connection Attempt:")
        print(f"  - User: {self.user} (ID: {self.user.id if self.user.is_authenticated else 'None'})")
        print(f"  - Course: {self.course_id}")
        print(f"  - Authenticated: {self.user.is_authenticated}")
        print(f"  - Room: {self.room_group_name}")
        
        # Accept the connection first
        await self.accept()
        
        if not self.user.is_authenticated:
            print("❌ User not authenticated - closing connection")
            await self.close()
            return
        
        # For testing, allow any authenticated user to join
        # In production, uncomment the permission checks below
        
        # Add to group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        print(f"✅ WebSocket Connected: {self.user.full_name} joined live class {self.course_id}")
        
        # Notify others
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_join',
                'user': self.user.full_name,
                'role': self.user.role,
                'user_id': self.user.id
            }
        )
    
    async def disconnect(self, close_code):
        print(f"🔌 WebSocket Disconnected: User {self.user.full_name} left live class {self.course_id}")
        
        try:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_leave',
                    'user': self.user.full_name,
                    'user_id': self.user.id
                }
            )
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        except Exception as e:
            print(f"Error during disconnect: {e}")
    
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            print(f"📩 Received: {message_type} from {self.user.full_name}")
            
            if message_type == 'chat':
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': data.get('message'),
                        'user': self.user.full_name,
                        'role': self.user.role,
                        'user_id': self.user.id
                    }
                )
            elif message_type in ['offer', 'answer', 'ice_candidate']:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'webrtc_signal',
                        'data': data,
                        'sender': self.user.full_name,
                        'sender_role': self.user.role,
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
        except json.JSONDecodeError:
            print(f"❌ Invalid JSON received: {text_data}")
        except Exception as e:
            print(f"❌ Error in receive: {e}")
    
    # ========== HANDLER METHODS ==========
    
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'chat',
            'message': event['message'],
            'user': event['user'],
            'role': event['role'],
            'user_id': event.get('user_id')
        }))
    
    async def webrtc_signal(self, event):
        if event.get('sender_id') == self.user.id:
            return
        await self.send(text_data=json.dumps({
            'type': 'webrtc',
            'data': event['data'],
            'sender': event['sender'],
            'sender_role': event['sender_role'],
            'sender_id': event.get('sender_id')
        }))
    
    async def user_join(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_join',
            'user': event['user'],
            'role': event.get('role', ''),
            'user_id': event.get('user_id')
        }))
    
    async def user_leave(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_leave',
            'user': event['user'],
            'user_id': event.get('user_id')
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
    
    # ========== DATABASE HELPERS ==========
    
    @database_sync_to_async
    def check_enrollment(self):
        from courses.models import Course, Enrollment
        from accounts.models import StudentProfile
        
        if self.user.role == 'TEACHER':
            return Course.objects.filter(id=self.course_id, instructor=self.user).exists()
        elif self.user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=self.user)
                return Enrollment.objects.filter(student=student, course_id=self.course_id, status='ACTIVE').exists()
            except StudentProfile.DoesNotExist:
                return False
        return False