# chat/views.py - COMPLETE FIXED VERSION

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from django.utils import timezone
from .models import ChatRoom, Message, UserStatus
from .serializers import ChatRoomSerializer, MessageSerializer, UserStatusSerializer, ChatRoomCreateSerializer
from accounts.models import User, StudentProfile, TeacherProfile
from accounts.serializers import UserSerializer
from notifications.utils import send_notification


class ChatRoomListView(generics.ListCreateAPIView):
    serializer_class = ChatRoomSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return ChatRoom.objects.filter(
            participants=self.request.user,
            is_active=True
        ).order_by('-updated_at')
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def create(self, request, *args, **kwargs):
        serializer = ChatRoomCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            room = serializer.save()
            return Response(ChatRoomSerializer(room, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChatRoomDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ChatRoomSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return ChatRoom.objects.filter(participants=self.request.user)
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def delete(self, request, *args, **kwargs):
        room = self.get_object()
        room.is_active = False
        room.save()
        return Response({'message': 'Chat room archived'})

# chat/views.py - REPLACE MessageListView

class MessageListView(generics.ListCreateAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        room_id = self.kwargs.get('room_id')
        # ✅ Only return messages if user is a participant
        if not ChatRoom.objects.filter(
            id=room_id, participants=self.request.user, is_active=True
        ).exists():
            return Message.objects.none()
        return Message.objects.filter(
            room_id=room_id, is_deleted=False
        ).select_related('sender').order_by('-created_at')

    def create(self, request, *args, **kwargs):
        room_id = self.kwargs.get('room_id')
        try:
            room = ChatRoom.objects.get(id=room_id, is_active=True)
        except ChatRoom.DoesNotExist:
            return Response({'error': 'Chat room not found'}, status=status.HTTP_404_NOT_FOUND)

        if not room.participants.filter(id=request.user.id).exists():
            return Response({'error': 'Not a participant'}, status=status.HTTP_403_FORBIDDEN)

        content = request.data.get('content', '').strip()
        if not content:
            return Response({'error': 'Message content required'}, status=status.HTTP_400_BAD_REQUEST)

        message = Message.objects.create(
            room=room,
            sender=request.user,
            content=content,
            message_type=request.data.get('message_type', 'TEXT')
        )
        room.save()  # bumps updated_at

        # Notify other participants
        for participant in room.participants.exclude(id=request.user.id):
            try:
                send_notification(
                    recipient_user=participant,
                    title=f'💬 New message from {request.user.full_name}',
                    message=content[:100],
                    notification_type='CHAT_MESSAGE',
                    link=f'/chat/{room_id}'
                )
            except Exception:
                pass

        return Response(self.get_serializer(message).data, status=status.HTTP_201_CREATED)

# chat/views.py - REPLACE MessageDetailView

class MessageDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = MessageSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Message.objects.filter(is_deleted=False)

    def delete(self, request, *args, **kwargs):
        message = self.get_object()

        # ✅ Only sender can delete
        if message.sender != request.user:
            return Response(
                {'error': 'You can only delete your own messages'},
                status=status.HTTP_403_FORBIDDEN
            )

        # ✅ Only participants can act on this room
        if not message.room.participants.filter(id=request.user.id).exists():
            return Response({'error': 'Not a participant'}, status=status.HTTP_403_FORBIDDEN)

        message.soft_delete(request.user)

        # ✅ Notify other participants so they see the deletion live
        for participant in message.room.participants.exclude(id=request.user.id):
            try:
                send_notification(
                    recipient_user=participant,
                    title='🗑️ Message deleted',
                    message=f'{request.user.full_name} deleted a message.',
                    notification_type='CHAT_MESSAGE',
                    link=f'/chat/{message.room_id}'
                )
            except Exception:
                pass

        return Response({'message': 'Message deleted', 'id': message.id})




class MarkMessagesReadView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, room_id):
        try:
            room = ChatRoom.objects.get(id=room_id, is_active=True)
        except ChatRoom.DoesNotExist:
            return Response({'error': 'Chat room not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if request.user not in room.participants.all():
            return Response({'error': 'You are not a participant in this chat'}, status=status.HTTP_403_FORBIDDEN)
        
        messages = Message.objects.filter(room=room, is_read=False).exclude(sender=request.user)
        for message in messages:
            message.mark_as_read()
        
        return Response({'message': f'Marked {messages.count()} messages as read'})


class UserStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        status, _ = UserStatus.objects.get_or_create(user=request.user)
        return Response(UserStatusSerializer(status).data)
    
    def post(self, request):
        status, _ = UserStatus.objects.get_or_create(user=request.user)
        status.status = request.data.get('status', 'ONLINE')
        status.save()
        return Response(UserStatusSerializer(status).data)


class AllUsersStatusView(APIView):
    """
    Get ALL users with their status for chat
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # ✅ Get ALL users except current user
        all_users = User.objects.exclude(id=user.id).order_by('full_name')
        
        result = []
        for u in all_users:
            # Get or create user status
            try:
                status_obj = UserStatus.objects.get(user=u)
                status = status_obj.status
                last_seen = status_obj.last_seen
            except UserStatus.DoesNotExist:
                status_obj = UserStatus.objects.create(user=u, status='OFFLINE')
                status = 'OFFLINE'
                last_seen = None
            
            result.append({
                'id': u.id,
                'user': u.id,
                'full_name': u.full_name,
                'email': u.email,
                'role': u.role,
                'profile_picture': u.profile_picture.url if u.profile_picture else None,
                'status': status,
                'last_seen': last_seen,
            })
        
        return Response(result)


class TypingIndicatorView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, room_id):
        try:
            room = ChatRoom.objects.get(id=room_id, is_active=True)
        except ChatRoom.DoesNotExist:
            return Response({'error': 'Chat room not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if request.user not in room.participants.all():
            return Response({'error': 'You are not a participant in this chat'}, status=status.HTTP_403_FORBIDDEN)
        
        status, _ = UserStatus.objects.get_or_create(user=request.user)
        status.is_typing = request.data.get('is_typing', False)
        status.typing_room = room if status.is_typing else None
        status.save()
        
        return Response({'is_typing': status.is_typing})

# chat/views.py - REPLACE GetOrCreatePrivateRoomView

class GetOrCreatePrivateRoomView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        other_user_id = request.data.get('user_id')
        if not other_user_id:
            return Response({'error': 'user_id is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            other_user = User.objects.get(id=other_user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        if other_user == request.user:
            return Response({'error': 'Cannot create chat with yourself'}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ Find EXISTING private room with EXACTLY these 2 participants
        from django.db.models import Count
        rooms = ChatRoom.objects.filter(
            room_type='PRIVATE',
            is_active=True,
            participants=request.user,
        ).filter(participants=other_user).annotate(
            num_participants=Count('participants')
        ).filter(num_participants=2)

        if rooms.exists():
            room = rooms.first()
            # Ensure both participants still in room
            room.participants.add(request.user, other_user)
        else:
            # Create new room
            room = ChatRoom.objects.create(
                room_type='PRIVATE',
                created_by=request.user,
            )
            room.participants.add(request.user, other_user)
            room.name = f"Chat: {request.user.full_name} & {other_user.full_name}"
            room.save(update_fields=['name'])

        return Response(
            ChatRoomSerializer(room, context={'request': request}).data,
            status=status.HTTP_200_OK
        )
