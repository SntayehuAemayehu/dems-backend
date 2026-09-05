# exams/models.py - COMPLETE

from django.db import models
from django.conf import settings
from django.utils import timezone

class Exam(models.Model):
    course = models.ForeignKey('courses.Course', on_delete=models.CASCADE, related_name='exams')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    duration_minutes = models.IntegerField(default=60)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    total_marks = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    passing_mark = models.DecimalField(max_digits=5, decimal_places=2, default=40)
    is_published = models.BooleanField(default=False)
    proctoring_enabled = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.title} - {self.course.course_code}"
    
    @property
    def course_title(self):
        return self.course.title
    
    @property
    def course_code(self):
        return self.course.course_code


class Question(models.Model):
    QUESTION_TYPES = [
        ('MCQ', 'Multiple Choice'),
        ('TF', 'True/False'),
        ('SHORT', 'Short Answer'),
    ]
    
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    type = models.CharField(max_length=10, choices=QUESTION_TYPES, default='MCQ')
    options = models.JSONField(default=list, blank=True)
    correct_answer = models.CharField(max_length=200, blank=True)
    marks = models.DecimalField(max_digits=5, decimal_places=2, default=1)
    order = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.text[:50]}..."


class ExamAttempt(models.Model):
    STATUS_CHOICES = [
        ('NOT_STARTED', 'Not Started'),
        ('IN_PROGRESS', 'In Progress'),
        ('SUBMITTED', 'Submitted'),
        ('GRADED', 'Graded'),
        ('FLAGGED', 'Flagged for Review'),
        ('TERMINATED', 'Terminated'),
    ]
    
    student = models.ForeignKey('accounts.StudentProfile', on_delete=models.CASCADE, related_name='exam_attempts')
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='attempts')
    start_time = models.DateTimeField(default=timezone.now)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='NOT_STARTED')
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    total_marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    passed = models.BooleanField(default=False)
    answers = models.JSONField(default=dict)
    last_heartbeat = models.DateTimeField(null=True, blank=True)
    # exams/models.py - ADD TO ExamAttempt Model

    # ✅ SECURITY FIELDS
    trust_score = models.FloatField(default=100.0)
    tab_switch_count = models.IntegerField(default=0)
    fullscreen_exit_count = models.IntegerField(default=0)
    face_match_confidence = models.FloatField(default=0.0)
    face_verified = models.BooleanField(default=False)
    suspicious_events_count = models.IntegerField(default=0)
    
    # ✅ AI PROCTOR FIELDS
    gaze_analysis = models.JSONField(default=dict, blank=True)
    object_detection = models.JSONField(default=dict, blank=True)
    head_analysis = models.JSONField(default=dict, blank=True)
    eye_analysis = models.JSONField(default=dict, blank=True)
    
    # ✅ BEHAVIORAL BIOMETRICS
    mouse_movements = models.JSONField(default=list, blank=True)
    keystroke_patterns = models.JSONField(default=list, blank=True)
    network_latency_history = models.JSONField(default=list, blank=True)
    
    # ✅ AI FLAGGING
    ai_flagged = models.BooleanField(default=False)
    ai_flag_reason = models.TextField(blank=True)
    ai_risk_score = models.FloatField(default=0.0)
    ai_risk_level = models.CharField(max_length=20, default='LOW', choices=[
        ('LOW', 'Low Risk'),
        ('MEDIUM', 'Medium Risk'),
        ('HIGH', 'High Risk'),
        ('CRITICAL', 'Critical - Immediate Action Required')
    ])
    
    # ✅ LOCKDOWN FIELDS
    is_locked = models.BooleanField(default=False)
    lock_reason = models.TextField(blank=True)
    unlocked_at = models.DateTimeField(null=True, blank=True)
    def __str__(self):
        return f"{self.student.user.full_name} - {self.exam.title}"


class Answer(models.Model):
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='answer_set')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer_text = models.TextField(blank=True)
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_correct = models.BooleanField(default=False)
    graded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    feedback = models.TextField(blank=True)  # ✅ For teacher feedback on essays
    
    def __str__(self):
        return f"Answer for Q{self.question.id}"