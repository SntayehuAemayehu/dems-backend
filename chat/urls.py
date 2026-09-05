# chat/urls.py - COMPLETE FIXED

from django.urls import path
from . import views

urlpatterns = [
    # Chat Rooms
    path('rooms/', views.ChatRoomListView.as_view(), name='chat-rooms'),
    path('rooms/<int:pk>/', views.ChatRoomDetailView.as_view(), name='chat-room-detail'),
    
    # Messages
    path('rooms/<int:room_id>/messages/', views.MessageListView.as_view(), name='chat-messages'),
    path('messages/<int:pk>/', views.MessageDetailView.as_view(), name='message-detail'),
    
    # Mark messages as read
    path('rooms/<int:room_id>/read/', views.MarkMessagesReadView.as_view(), name='mark-read'),
    
    # User Status
    path('status/', views.UserStatusView.as_view(), name='user-status'),
    path('status/all/', views.AllUsersStatusView.as_view(), name='all-user-status'),  # ✅ Fixed: AllUsersStatusView
    
    # Typing Indicator
    path('rooms/<int:room_id>/typing/', views.TypingIndicatorView.as_view(), name='typing-indicator'),
    
    # Get or create private room
    path('private-room/', views.GetOrCreatePrivateRoomView.as_view(), name='private-room'),
]