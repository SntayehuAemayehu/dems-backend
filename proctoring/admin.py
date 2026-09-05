# proctoring/admin.py - COMPLETE FIXED VERSION

from django.contrib import admin
from .models import ProctorImage, ProctorLog, ProctorSession

@admin.register(ProctorImage)
class ProctorImageAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'capture_time', 'is_suspicious', 'face_detected')
    list_filter = ('is_suspicious', 'face_detected')
    search_fields = ('attempt__student__user__full_name',)


@admin.register(ProctorLog)
class ProctorLogAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'event_type', 'timestamp')
    list_filter = ('event_type',)
    search_fields = ('attempt__student__user__full_name',)


@admin.register(ProctorSession)
class ProctorSessionAdmin(admin.ModelAdmin):
    list_display = ('attempt', 'is_active', 'total_captures', 'suspicious_events', 'review_status')
    list_filter = ('is_active', 'review_status')
    search_fields = ('attempt__student__user__full_name',)