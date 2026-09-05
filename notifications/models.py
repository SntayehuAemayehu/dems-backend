from django.db import models
from django.conf import settings

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('PAYMENT_VERIFIED', 'Payment Verified'),
        ('PAYMENT_REJECTED', 'Payment Rejected'),
        ('PAYMENT_PENDING', 'Payment Pending'),
        ('PAYMENT_RESUBMIT', 'Payment Resubmission Required'),
        ('EXAM_SCHEDULED', 'Exam Scheduled'),
        ('GRADE_RELEASED', 'Grade Released'),
        ('COURSE_APPROVED', 'Course Approved'),
        ('COURSE_REJECTED', 'Course Rejected'),
        ('SYSTEM_ALERT', 'System Alert'),
        ('LIVE_CLASS_STARTED', 'Live Class Started'),
    ]
    
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES, default='SYSTEM_ALERT')
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    link = models.CharField(max_length=200, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title