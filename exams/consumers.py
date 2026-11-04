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
        
        # ✅ NEW: Set course live if user is teacher
        if self.user.role == 'TEACHER':
            await self.set_course_live(True)

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
        
        # ✅ NEW: Set course offline if user is teacher
        if self.user.is_authenticated and self.user.role == 'TEACHER':
            await self.set_course_live(False)

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
            elif message_type in ['hand_raise', 'hand_lower']:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': message_type,
                        'user': self.user.full_name,
                        'user_id': self.user.id
                    }
                )
            elif message_type == 'remove_student':
                if self.user.role != 'TEACHER':
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'Only the teacher can remove students.'
                    }))
                    return

                target_id = data.get('target_id')
                if target_id is None:
                    await self.send(text_data=json.dumps({
                        'type': 'error',
                        'message': 'A student must be selected.'
                    }))
                    return
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'student_removed',
                        'target_id': str(target_id),
                        'removed_by': self.user.full_name
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
            'sender_id': event.get('sender_id'),
            'target_id': event['data'].get('target_id')
        }))

    async def hand_raise(self, event):
        await self.send(text_data=json.dumps({
            'type': 'hand_raise',
            'user': event['user'],
            'user_id': event['user_id']
        }))

    async def hand_lower(self, event):
        await self.send(text_data=json.dumps({
            'type': 'hand_lower',
            'user': event['user'],
            'user_id': event['user_id']
        }))

    async def student_removed(self, event):
        if str(event['target_id']) == str(self.user.id):
            await self.send(text_data=json.dumps({
                'type': 'student_removed',
                'target_id': event['target_id'],
                'removed_by': event['removed_by']
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
    def set_course_live(self, is_live):
        from courses.models import Course
        try:
            Course.objects.filter(id=self.course_id).update(is_live=is_live)
        except Exception as e:
            print(f"Error updating course live status: {e}")

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


# ============================================================
# EXAM PROCTOR CONSUMER
# ============================================================
class ExamProctorConsumer(AsyncWebsocketConsumer):
    """
    WebSocket for live exam proctoring.
    Student sends camera → Teacher receives live video.
    Also handles: warning, force_submit, pause, resume, add_time, chat
    """

    async def connect(self):
        self.exam_id = self.scope['url_route']['kwargs']['exam_id']
        self.room_group_name = f'exam_proctor_{self.exam_id}'
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close(code=4401)
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        print(f"✅ ExamProctor: {self.user.full_name} ({self.user.role}) joined exam {self.exam_id}")

        # Notify others
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_join',
                'user': self.user.full_name,
                'role': self.user.role,
                'user_id': self.user.id,
            }
        )

    async def disconnect(self, close_code):
        if self.user.is_authenticated:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_leave',
                    'user': self.user.full_name,
                    'user_id': self.user.id,
                }
            )
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            print(f"🔌 ExamProctor: {self.user.full_name} left exam {self.exam_id}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get('type')

            # ========== WebRTC signaling ==========
            if message_type in ['offer', 'answer', 'ice_candidate']:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'webrtc_signal',
                        'data': data,
                        'sender': self.user.full_name,
                        'sender_role': self.user.role,
                        'sender_id': self.user.id,
                    }
                )

            # ========== Teacher control messages ==========
            elif message_type in ['warning', 'force_submit', 'pause_exam', 'resume_exam', 'add_time', 'chat']:
                # Only teacher can send these
                if self.user.role != 'TEACHER':
                    return

                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'control_message',
                        'message_type': message_type,
                        'data': data,
                        'sender': self.user.full_name,
                        'sender_id': self.user.id,
                    }
                )

            elif message_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))

        except Exception as e:
            print(f"ExamProctor receive error: {e}")

    # ========== Handlers ==========

    async def webrtc_signal(self, event):
        # Don't send back to the sender
        if event.get('sender_id') == self.user.id:
            return
        await self.send(text_data=json.dumps({
            'type': event['data']['type'],
            'offer': event['data'].get('offer'),
            'answer': event['data'].get('answer'),
            'candidate': event['data'].get('candidate'),
            'sender': event['sender'],
            'sender_role': event['sender_role'],
            'sender_id': event['sender_id'],
        }))

    async def control_message(self, event):
        # Send control messages to everyone in the room (mainly students)
        await self.send(text_data=json.dumps({
            'type': event['message_type'],
            'message': event['data'].get('message'),
            'minutes': event['data'].get('minutes'),          # for add_time
            'target_user_id': event['data'].get('target_user_id'),  # optional: send to specific student
            'sender': event['sender'],
            'sender_id': event['sender_id'],
        }))

    async def user_join(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_join',
            'user': event['user'],
            'role': event.get('role'),
            'user_id': event.get('user_id'),
        }))

    async def user_leave(self, event):
        await self.send(text_data=json.dumps({
            'type': 'user_leave',
            'user': event['user'],
            'user_id': event.get('user_id'),
        }))