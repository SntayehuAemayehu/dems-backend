# chat/serializers.py - COMPLETE

from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import ChatRoom, Message, MessageAttachment, UserStatus

User = get_user_model()


class UserStatusSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source='user.full_name', read_only=True)
    email = serializers.CharField(source='user.email', read_only=True)
    profile_picture = serializers.ImageField(source='user.profile_picture', read_only=True)
    role = serializers.CharField(source='user.role', read_only=True)
    
    class Meta:
        model = UserStatus
        fields = ['id', 'user', 'full_name', 'email', 'profile_picture', 'role', 'status', 'last_seen', 'is_typing']


class MessageAttachmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageAttachment
        fields = ['id', 'file', 'file_name', 'file_size', 'mime_type', 'created_at']


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.full_name', read_only=True)
    sender_email = serializers.CharField(source='sender.email', read_only=True)
    sender_role = serializers.CharField(source='sender.role', read_only=True)
    sender_profile_picture = serializers.ImageField(source='sender.profile_picture', read_only=True)
    attachments = MessageAttachmentSerializer(many=True, read_only=True)
    time_ago = serializers.SerializerMethodField()
    
    class Meta:
        model = Message
        fields = [
            'id', 'room', 'sender', 'sender_name', 'sender_email', 'sender_role',
            'sender_profile_picture', 'message_type', 'content', 'file',
            'attachments', 'is_read', 'is_deleted', 'read_at', 'created_at',
            'updated_at', 'time_ago'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_time_ago(self, obj):
        from django.utils import timezone
        now = timezone.now()
        diff = now - obj.created_at
        if diff.days > 0:
            return f"{diff.days}d ago"
        elif diff.seconds > 3600:
            return f"{diff.seconds // 3600}h ago"
        elif diff.seconds > 60:
            return f"{diff.seconds // 60}m ago"
        return "Just now"


class ChatRoomSerializer(serializers.ModelSerializer):
    participants_info = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        model = ChatRoom
        fields = [
            'id', 'name', 'room_type', 'participants', 'participants_info',
            'created_by', 'created_by_name', 'created_at', 'updated_at',
            'is_active', 'course_id', 'department_id', 'last_message',
            'unread_count'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_participants_info(self, obj):
        from accounts.serializers import UserSerializer
        return UserSerializer(obj.participants.all(), many=True).data
    
    def get_last_message(self, obj):
        last_msg = obj.messages.filter(is_deleted=False).first()
        if last_msg:
            return MessageSerializer(last_msg).data
        return None
    
    def get_unread_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.unread_count(request.user)
        return 0


class ChatRoomCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatRoom
        fields = ['name', 'room_type', 'participants', 'course_id', 'department_id']
    
    def create(self, validated_data):
        participants = validated_data.pop('participants', [])
        room = ChatRoom.objects.create(
            created_by=self.context['request'].user,
            **validated_data
        )
        room.participants.add(self.context['request'].user)
        for user in participants:
            room.participants.add(user)
        return room