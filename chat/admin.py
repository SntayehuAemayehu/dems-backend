# chat/admin.py
from django.contrib import admin
from .models import ChatRoom, Message, MessageAttachment, UserStatus

@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'room_type', 'created_by', 'created_at', 'updated_at', 'is_active')
    list_filter = ('room_type', 'is_active')
    search_fields = ('name', 'participants__email', 'participants__full_name')
    filter_horizontal = ('participants',)

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'room', 'sender', 'content_preview', 'message_type', 'is_read', 'created_at')
    list_filter = ('message_type', 'is_read', 'is_deleted')
    search_fields = ('content', 'sender__email', 'sender__full_name')
    
    def content_preview(self, obj):
        return obj.content[:50] + '...' if len(obj.content) > 50 else obj.content
    content_preview.short_description = 'Content'

@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'message', 'file_name', 'file_size', 'mime_type', 'created_at')
    search_fields = ('file_name',)

@admin.register(UserStatus)
class UserStatusAdmin(admin.ModelAdmin):
    list_display = ('user', 'status', 'last_seen', 'is_typing')
    list_filter = ('status', 'is_typing')
    search_fields = ('user__email', 'user__full_name')