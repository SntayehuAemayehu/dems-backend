# chat/models.py - COMPLETE FIXED VERSION

from django.db import models
from django.conf import settings
from django.utils import timezone


class ChatRoom(models.Model):
    """
    Chat Room - can be private (1-on-1) or group
    """
    ROOM_TYPES = [
        ('PRIVATE', 'Private'),
        ('GROUP', 'Group'),
        ('DEPARTMENT', 'Department'),
        ('COURSE', 'Course'),
    ]
    
    name = models.CharField(max_length=100, blank=True, null=True)
    room_type = models.CharField(max_length=20, choices=ROOM_TYPES, default='PRIVATE')
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='chat_rooms')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_rooms')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # For course/department specific rooms
    course_id = models.IntegerField(null=True, blank=True)
    department_id = models.IntegerField(null=True, blank=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        if self.name:
            return self.name
        participants = self.participants.all()
        if participants.count() <= 2:
            names = [p.full_name for p in participants]
            return f"Chat: {', '.join(names)}"
        return f"Group Chat ({participants.count()} participants)"
    
    @property
    def last_message(self):
        return self.messages.filter(is_deleted=False).first()
    
    def unread_count(self, user):
        return self.messages.filter(
            is_read=False,
            is_deleted=False
        ).exclude(sender=user).count()
    
    # ✅ UPDATED: Save method with proper updated_at handling
    def save(self, *args, **kwargs):
        """Override save to ensure updated_at is updated"""
        # If update_fields is specified and doesn't include updated_at, add it
        if kwargs.get('update_fields'):
            if 'updated_at' not in kwargs['update_fields']:
                kwargs['update_fields'] = list(kwargs['update_fields']) + ['updated_at']
        
        # Always update updated_at when saving
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)


class Message(models.Model):
    """
    Individual message in a chat room
    """
    MESSAGE_TYPES = [
        ('TEXT', 'Text'),
        ('IMAGE', 'Image'),
        ('FILE', 'File'),
        ('VIDEO', 'Video'),
        ('SYSTEM', 'System'),
    ]
    
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES, default='TEXT')
    content = models.TextField()
    file = models.FileField(upload_to='chat_files/', null=True, blank=True)
    is_read = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_messages')
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.sender.full_name}: {self.content[:50]}"
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def soft_delete(self, user):
        self.is_deleted = True
        self.deleted_by = user
        self.save(update_fields=['is_deleted', 'deleted_by'])
    
    def save(self, *args, **kwargs):
        """Override save to set updated_at"""
        if kwargs.get('update_fields'):
            if 'updated_at' not in kwargs['update_fields']:
                kwargs['update_fields'] = list(kwargs['update_fields']) + ['updated_at']
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)


class MessageAttachment(models.Model):
    """
    Attachments for messages
    """
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='chat_attachments/')
    file_name = models.CharField(max_length=255)
    file_size = models.IntegerField(help_text="File size in bytes")
    mime_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.file_name


class UserStatus(models.Model):
    """
    Track user online/offline status
    """
    STATUS_CHOICES = [
        ('ONLINE', 'Online'),
        ('OFFLINE', 'Offline'),
        ('AWAY', 'Away'),
        ('BUSY', 'Busy'),
    ]
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_status')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OFFLINE')
    last_seen = models.DateTimeField(auto_now=True)
    is_typing = models.BooleanField(default=False)
    typing_room = models.ForeignKey(ChatRoom, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.full_name} - {self.status}"
    
    @classmethod
    def set_online(cls, user):
        status, _ = cls.objects.get_or_create(user=user)
        status.status = 'ONLINE'
        status.last_seen = timezone.now()
        status.save(update_fields=['status', 'last_seen'])
        return status
    
    @classmethod
    def set_offline(cls, user):
        try:
            status = cls.objects.get(user=user)
            status.status = 'OFFLINE'
            status.last_seen = timezone.now()
            status.save(update_fields=['status', 'last_seen'])
            return status
        except cls.DoesNotExist:
            return None
    
    def save(self, *args, **kwargs):
        """Override save to update last_seen"""
        if not kwargs.get('update_fields') or 'last_seen' in kwargs.get('update_fields', []):
            self.last_seen = timezone.now()
        super().save(*args, **kwargs)