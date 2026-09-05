# backend/proctoring/models.py
# COMPLETE PROCTORING MODELS WITH ALL FIELDS

from django.db import models
from django.conf import settings
from django.utils import timezone

class ProctorImage(models.Model):
    attempt = models.ForeignKey('exams.ExamAttempt', on_delete=models.CASCADE, related_name='proctor_images')
    image = models.ImageField(upload_to='proctor_images/')
    capture_time = models.DateTimeField(auto_now_add=True)
    is_suspicious = models.BooleanField(default=False)
    face_detected = models.BooleanField(default=True)
    multiple_faces = models.BooleanField(default=False)
    mobile_detected = models.BooleanField(default=False)
    suspicious_reason = models.TextField(blank=True)
    flagged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    flagged_at = models.DateTimeField(null=True, blank=True)
    
    # ✅ GAZE TRACKING FIELDS
    gaze_direction = models.CharField(max_length=20, blank=True, default='CENTER')  # CENTER, LEFT, RIGHT, UP, DOWN, UP_LEFT, etc.
    gaze_confidence = models.FloatField(default=0.0)
    gaze_x = models.FloatField(default=0.0)  # -1 to 1
    gaze_y = models.FloatField(default=0.0)  # -1 to 1
    head_tilt_x = models.FloatField(default=0.0)
    head_tilt_y = models.FloatField(default=0.0)
    eyes_closed = models.BooleanField(default=False)
    
    # ✅ OBJECT DETECTION FIELDS
    objects_detected = models.JSONField(default=list, blank=True)  # List of detected objects
    object_confidence = models.FloatField(default=0.0)
    
    def __str__(self):
        return f"Proctor image at {self.capture_time}"

class ProctorLog(models.Model):
    EVENT_TYPES = [
        ('TAB_SWITCH', 'Tab Switch'),
        ('COPY_PASTE', 'Copy Paste'),
        ('FULLSCREEN_EXIT', 'Fullscreen Exit'),
        ('MULTIPLE_FACES', 'Multiple Faces'),
        ('FACE_LOST', 'Face Lost'),
        ('GAZE_AWAY', 'Gaze Away'),
        ('HEAD_TILTED', 'Head Tilted'),
        ('EYES_CLOSED', 'Eyes Closed'),
        ('OBJECT_DETECTED', 'Object Detected'),
        ('AUTO_FLAGGED', 'Auto Flagged'),
    ]
    
    attempt = models.ForeignKey('exams.ExamAttempt', on_delete=models.CASCADE, related_name='proctor_logs')
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    details = models.JSONField(default=dict)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.event_type} at {self.timestamp}"

class ProctorSession(models.Model):
    attempt = models.OneToOneField('exams.ExamAttempt', on_delete=models.CASCADE, related_name='proctor_session')
    is_active = models.BooleanField(default=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    total_captures = models.IntegerField(default=0)
    suspicious_events = models.IntegerField(default=0)
    review_status = models.CharField(max_length=20, default='PENDING', choices=[
        ('PENDING', 'Pending Review'),
        ('REVIEWED', 'Reviewed'),
        ('FLAGGED', 'Flagged'),
        ('CLEARED', 'Cleared'),
        ('AUTO_FLAGGED', 'Auto Flagged'),
    ])
    review_notes = models.TextField(blank=True)
    auto_flag_threshold = models.IntegerField(default=3)
    
    # ✅ ENHANCED FIELDS
    gaze_events_count = models.IntegerField(default=0)
    object_events_count = models.IntegerField(default=0)
    head_tilt_events_count = models.IntegerField(default=0)
    ml_risk_score = models.FloatField(default=0.0)
    ml_prediction = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-started_at']
    
    def __str__(self):
        return f"Session - {self.id}"
    
    def get_suspicious_summary(self):
        """Get summary of suspicious events"""
        return {
            'total': self.suspicious_events,
            'gaze_events': self.gaze_events_count,
            'object_events': self.object_events_count,
            'head_tilt_events': self.head_tilt_events_count,
            'auto_flagged': self.review_status == 'AUTO_FLAGGED'
        }