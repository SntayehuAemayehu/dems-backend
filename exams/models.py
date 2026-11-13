# exams/models.py - COMPLETE
from django_ask_ai import AskMixin
from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid
from cloudinary_storage.storage import RawMediaCloudinaryStorage
class Exam(AskMixin, models.Model):
    EXAM_TYPE_CHOICES = [
        ('QUIZ', 'Quiz'),
        ('MID', 'Mid Exam'),
        ('FINAL', 'Final Exam'),
    ]
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
    

    exam_type = models.CharField(
        max_length=10,
        choices=EXAM_TYPE_CHOICES,
        default='MID',
    )
      # ✅ SEB fields
    seb_enabled = models.BooleanField(default=False)
    seb_config_file = models.FileField(upload_to='seb_configs/', null=True, blank=True, storage=RawMediaCloudinaryStorage())
    seb_config_key = models.CharField(max_length=64, blank=True)  # CK hash
    seb_browser_exam_key = models.CharField(max_length=64, blank=True)  # BEK (optional)
    seb_generated_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.title} - {self.course.course_code}"

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


class ExamAttempt(AskMixin, models.Model):
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
    # exams/models.py — inside class ExamAttempt

# ✅ Audio signal fields (with defaults so DB inserts work)
    last_audio_loudness = models.FloatField(default=0.0)
    last_audio_hz = models.FloatField(default=0.0)
    last_speech_detected = models.BooleanField(default=False)
    speech_events_10s = models.IntegerField(default=0)
    # In ExamAttempt model - ADD these fields
    heartbeat_history = models.JSONField(default=list, blank=True)
    # ✅ LOCKDOWN FIELDS
    is_locked = models.BooleanField(default=False)
    lock_reason = models.TextField(blank=True)
    unlocked_at = models.DateTimeField(null=True, blank=True)
    def __str__(self):
        return f"{self.student.user.full_name} - {self.exam.title}"


class ExaminerAssignment(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='examiner_assignments')
    attempt = models.OneToOneField(ExamAttempt, on_delete=models.CASCADE, related_name='examiner_assignment')
    examiner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='examiner_assignments')
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_examiner_assignments')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.exam_id}: {self.examiner_id} -> {self.attempt_id}"


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
class ExamRecording(models.Model):
    """Chunked video recording of exam session."""
    attempt = models.ForeignKey(
        ExamAttempt,
        on_delete=models.CASCADE,
        related_name='recordings'
    )
    chunk_index = models.IntegerField(default=0)
    chunk_file = models.FileField(upload_to='recordings/%Y/%m/%d/')
    duration_seconds = models.FloatField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    size_bytes = models.BigIntegerField(default=0)

    class Meta:
        ordering = ['attempt', 'chunk_index']
        unique_together = ('attempt', 'chunk_index')

    def __str__(self):
        return f"Recording for attempt {self.attempt_id} chunk {self.chunk_index}"       

class SEBSession(models.Model):
    """
    Server-side record created when SEB opens the entry endpoint.
    Bound to student + exam, short-lived, single-use.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey('accounts.StudentProfile', on_delete=models.CASCADE, related_name='seb_sessions')
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='seb_sessions')
    attempt = models.ForeignKey('ExamAttempt', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)
    ip_hash = models.CharField(max_length=64, blank=True)

    class Meta:
        indexes = [models.Index(fields=['expires_at', 'used'])]

    def is_valid(self):
        return not self.used and timezone.now() < self.expires_at

    def __str__(self):
        return f"SEB {self.student_id} - {self.exam_id} ({'used' if self.used else 'active'})"

    