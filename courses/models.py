# courses/models.py - COMPLETE FIXED VERSION WITH VIDEO SUPPORT

from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
class Course(models.Model):
    course_code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    credit_hours = models.IntegerField(default=3)
    semester = models.CharField(max_length=10, default='1')
    academic_year = models.CharField(max_length=10, blank=True)
    capacity = models.IntegerField(default=30)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='courses_teaching'
    )
    department = models.ForeignKey(
        'accounts.Department', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    is_active = models.BooleanField(default=True)
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='approved_courses'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.course_code}: {self.title}"
    
    @property
    def enrolled_count(self):
        return self.enrollments.filter(status='ACTIVE').count()
    
    @property
    def instructor_name(self):
        return self.instructor.full_name if self.instructor else None


class CourseMaterial(models.Model):
    MATERIAL_TYPES = [
        ('PDF', 'PDF Document'),
        ('VIDEO', 'Video'),
        ('SLIDE', 'Presentation'),
        ('DOC', 'Document'),
        ('IMAGE', 'Image'),
        ('AUDIO', 'Audio'),
        ('OTHER', 'Other'),
    ]
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='materials')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    material_type = models.CharField(max_length=20, choices=MATERIAL_TYPES, default='PDF')
    file = models.FileField(upload_to='course_materials/')
    video_duration = models.IntegerField(blank=True, null=True, help_text="Duration in seconds")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.title} - {self.course.course_code}"
    
    def get_file_extension(self):
        if self.file:
            return self.file.name.split('.')[-1].lower()
        return ''
    
    def is_video(self):
        return self.material_type == 'VIDEO'
    
    def get_video_embed_url(self):
        if self.is_video() and self.file:
            return self.file.url
        return None


class Enrollment(models.Model):
    """Student enrollment with full grade tracking"""
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ACTIVE', 'Active'),
        ('DROPPED', 'Dropped'),
        ('COMPLETED', 'Completed'),
    ]
    
    student = models.ForeignKey('accounts.StudentProfile', on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrollment_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    
    # ============ GRADE FIELDS ============
    grade = models.CharField(max_length=2, blank=True, null=True)  # Legacy grade field
    grade_letter = models.CharField(max_length=3, blank=True, null=True)  # A+, A, B+, etc.
    grade_points = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    percentage_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    total_marks_obtained = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_marks_possible = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # ============ RESULT SENT TO REGISTRAR ============
    result_sent_to_registrar = models.BooleanField(default=False)
    result_sent_at = models.DateTimeField(null=True, blank=True)
    result_sent_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='sent_results'
    )
    
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-enrollment_date']
        unique_together = ['student', 'course']
    
    def __str__(self):
        return f"{self.student.user.full_name} - {self.course.course_code}"
    
    def calculate_grade(self):
        """Calculate letter grade based on percentage_score"""
        from utils.grading import calculate_grade
        
        if self.percentage_score is None or self.percentage_score == 0:
            self.grade_letter = 'NON'
            self.grade_points = 0
            self.save()
            return {'letter': 'NON', 'gpa': 0.0}
        
        percentage = float(self.percentage_score)
        grade_info = calculate_grade(percentage)
        self.grade_letter = grade_info['letter']
        self.grade_points = grade_info['gpa']
        self.save()
        return grade_info
    
    # backend/courses/models.py
# REPLACE the existing update_course_grade method with this:

    def update_course_grade(self):
        """Update grade for this enrollment based on ALL exams and assignments.
           The final grade is only calculated when ALL items are graded."""
        from exams.models import ExamAttempt
        from courses.models import AssignmentSubmission
        
        # 1. Get all exam attempts for this course (must be GRADED)
        exam_attempts = ExamAttempt.objects.filter(
            student=self.student,
            exam__course=self.course,
            status='GRADED'  # Only count fully graded exams
        )
        
        # 2. Get all assignment submissions for this course (must be graded)
        assignment_submissions = AssignmentSubmission.objects.filter(
            student=self.student,
            assignment__course=self.course,
            marks_obtained__isnull=False
        )
        
        # 3. Get ALL exams and assignments for this course (to check if any are missing)
        all_exams = self.course.exams.all()
        all_assignments = self.course.assignments.all()
        
        total_obtained = Decimal('0')
        total_possible = Decimal('0')
        has_graded_items = False
        
        # Check if all exams are graded
        graded_exam_ids = set(attempt.exam_id for attempt in exam_attempts)
        all_exam_ids = set(exam.id for exam in all_exams)
        
        all_exams_graded = len(graded_exam_ids) == len(all_exam_ids) if all_exams else True
        
        # Check if all assignments are graded
        graded_assignment_ids = set(sub.assignment_id for sub in assignment_submissions)
        all_assignment_ids = set(ass.id for ass in all_assignments)
        
        all_assignments_graded = len(graded_assignment_ids) == len(all_assignment_ids) if all_assignments else True
        
        # 4. Calculate totals ONLY from graded items
        for attempt in exam_attempts:
            if attempt.score is not None:
                total_obtained += Decimal(str(attempt.score))
                total_possible += Decimal(str(attempt.total_marks or 0))
                has_graded_items = True
        
        for submission in assignment_submissions:
            if submission.marks_obtained is not None:
                total_obtained += Decimal(str(submission.marks_obtained))
                total_possible += Decimal(str(submission.assignment.total_marks or 0))
                has_graded_items = True
        
        # 5. Update the marks totals
        self.total_marks_obtained = total_obtained if has_graded_items else None
        self.total_marks_possible = total_possible if has_graded_items else None
        
        # 6. CRITICAL: Only calculate the FINAL GRADE if ALL items are graded
        if all_exams_graded and all_assignments_graded and total_possible > 0:
            percentage = (total_obtained / total_possible) * Decimal('100')
            self.percentage_score = percentage
            
            from utils.grading import calculate_grade
            grade_info = calculate_grade(float(percentage))
            self.grade_letter = grade_info['letter']
            self.grade_points = grade_info['gpa']
            
            # Mark as COMPLETED
            if self.status != 'COMPLETED':
                self.status = 'COMPLETED'
        else:
            # If not all items are graded, keep it as ACTIVE and clear the letter grade
            self.percentage_score = None
            self.grade_letter = 'NON'
            self.grade_points = Decimal('0.00')
            if self.status == 'COMPLETED':
                self.status = 'ACTIVE'
        
        self.save()
        return self
    def get_grade_summary(self):
        """Get complete grade summary for this enrollment"""
        return {
            'course_id': self.course.id,
            'course_code': self.course.course_code,
            'course_title': self.course.title,
            'credit_hours': self.course.credit_hours,
            'status': self.status,
            'marks_obtained': float(self.total_marks_obtained) if self.total_marks_obtained else 0,
            'marks_possible': float(self.total_marks_possible) if self.total_marks_possible else 0,
            'percentage': float(self.percentage_score) if self.percentage_score else 0,
            'grade_letter': self.grade_letter or 'NON',
            'grade_points': float(self.grade_points) if self.grade_points else 0,
            'sent_to_registrar': self.result_sent_to_registrar,
            'sent_at': self.result_sent_at.isoformat() if self.result_sent_at else None,
            'sent_by': self.result_sent_by.full_name if self.result_sent_by else None,
        }




class Assignment(models.Model):
    """Course assignment model with video attachment support"""
    ASSIGNMENT_TYPES = [
        ('DOCUMENT', 'Document'),
        ('VIDEO', 'Video'),
        ('LINK', 'Link'),
        ('OTHER', 'Other'),
    ]
    
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assignment_type = models.CharField(max_length=20, choices=ASSIGNMENT_TYPES, default='DOCUMENT')
    due_date = models.DateTimeField()
    total_marks = models.DecimalField(max_digits=5, decimal_places=2, default=100)
    attachment = models.FileField(upload_to='assignments/', null=True, blank=True)
    video_attachment = models.FileField(upload_to='assignments/videos/', null=True, blank=True)
    video_duration = models.IntegerField(blank=True, null=True)
    link_url = models.URLField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} - {self.course.course_code}"
    
    def has_video(self):
        return bool(self.video_attachment)


class AssignmentSubmission(models.Model):
    """Student assignment submission with video support"""
    SUBMISSION_TYPES = [
        ('FILE', 'File Upload'),
        ('VIDEO', 'Video Upload'),
        ('LINK', 'Link Submission'),
        ('TEXT', 'Text Submission'),
    ]
    
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey('accounts.StudentProfile', on_delete=models.CASCADE, related_name='assignment_submissions')
    submission_type = models.CharField(max_length=10, choices=SUBMISSION_TYPES, default='FILE')
    submission_file = models.FileField(upload_to='submissions/', null=True, blank=True)
    submission_video = models.FileField(upload_to='submissions/videos/', null=True, blank=True)
    submission_text = models.TextField(blank=True)
    submission_link = models.URLField(blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    marks_obtained = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-submitted_at']
        unique_together = ['assignment', 'student']
    
    def __str__(self):
        return f"{self.student.user.full_name} - {self.assignment.title}"
    
    def has_video(self):
        return bool(self.submission_video)