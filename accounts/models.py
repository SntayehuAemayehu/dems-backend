# accounts/models.py - COMPLETE FIXED VERSION

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'ADMIN')
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [
        ('STUDENT', 'Student'),
        ('TEACHER', 'Teacher'),
        ('ADMIN', 'Administrator'),
        ('FINANCE', 'Finance Officer'),
        ('REGISTRAR', 'Registrar'),
        ('DEPT_HEAD', 'Department Head'),
    ]
    
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='STUDENT')
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)
    # Add these fields for password reset
    password_reset_token = models.CharField(max_length=100, null=True, blank=True)
    password_reset_token_created = models.DateTimeField(null=True, blank=True)
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']
    
    def __str__(self):
        return f"{self.full_name} ({self.email})"



# accounts/models.py - COMPLETE STUDENT PROFILE WITH CGPA


class StudentProfile(models.Model):
    GENDER_CHOICES = [
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
        ('OTHER', 'Other'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
        ('OVERDUE_LOCKED', 'Overdue - Locked'),
    ]
    
    REGISTRATION_TYPE_CHOICES = [
        ('FRESH', 'Fresh Student'),
        ('SENIOR', 'Senior Student'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, null=True, blank=True)
    address = models.TextField(blank=True)
    enrollment_date = models.DateField(default=timezone.now)
    current_semester = models.IntegerField(default=1)
    department = models.CharField(max_length=100, blank=True)
    program = models.CharField(max_length=100, blank=True)
    
    # ============ ACADEMIC FIELDS ============
    cgpa = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    total_credits = models.IntegerField(default=0)
    
    payment_status = models.CharField(max_length=20, default='PENDING', choices=PAYMENT_STATUS_CHOICES)
    documents_verified = models.BooleanField(default=False)
    is_enrolled = models.BooleanField(default=False)
    registration_type = models.CharField(max_length=10, choices=REGISTRATION_TYPE_CHOICES, default='FRESH')
    
    # Document fields
    grade_8_certificate = models.FileField(upload_to='student_documents/grade8/', null=True, blank=True)
    grade_12_certificate = models.FileField(upload_to='student_documents/grade12/', null=True, blank=True)
    transcript = models.FileField(upload_to='student_documents/transcripts/', null=True, blank=True)
    other_documents = models.FileField(upload_to='student_documents/other/', null=True, blank=True)
    documents_submitted = models.BooleanField(default=False)
    documents_verified_at = models.DateTimeField(null=True, blank=True)
    registration_complete = models.BooleanField(default=False)
    
    # Payment schedule tracking
    current_payment_schedule_id = models.IntegerField(null=True, blank=True)
    notification_sent = models.BooleanField(default=False)
    
    # Registration period fields
    registration_year = models.IntegerField(null=True, blank=True)
    registration_semester = models.CharField(max_length=10, null=True, blank=True)
    registration_deadline = models.DateField(null=True, blank=True)
    
    # Activation tracking
    activated_at = models.DateTimeField(null=True, blank=True)
    activated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='activated_students')
    
    class Meta:
        ordering = ['-enrollment_date']
    
    def __str__(self):
        return f"Student: {self.user.full_name} - {self.student_id}"
    
    def get_current_year(self):
        """Get current year based on semester (1-2 = Year 1, 3-4 = Year 2, etc.)"""
        if self.current_semester:
            return (self.current_semester + 1) // 2
        return 0
    
    def update_cgpa(self):
        """Calculate and update CGPA based on all completed courses"""
        from courses.models import Enrollment
        
        enrollments = Enrollment.objects.filter(
            student=self,
            status='COMPLETED'
        )
        
        total_grade_points = 0
        total_credits = 0
        
        for enrollment in enrollments:
            if enrollment.grade_points and enrollment.course.credit_hours:
                gpa = float(enrollment.grade_points)
                credits = enrollment.course.credit_hours
                total_grade_points += gpa * credits
                total_credits += credits
        
        if total_credits > 0:
            self.cgpa = Decimal(str(total_grade_points / total_credits))
        else:
            self.cgpa = Decimal('0.00')
        
        self.save()
        return self.cgpa
    
    def get_overall_grade_summary(self):
        """Get overall grade summary for all courses"""
        from courses.models import Enrollment
        
        enrollments = Enrollment.objects.filter(student=self)
        results = []
        total_marks_obtained = 0
        total_marks_possible = 0
        
        for enrollment in enrollments:
            enrollment.update_course_grade()
            summary = enrollment.get_grade_summary()
            results.append(summary)
            
            if enrollment.total_marks_obtained:
                total_marks_obtained += float(enrollment.total_marks_obtained)
            if enrollment.total_marks_possible:
                total_marks_possible += float(enrollment.total_marks_possible)
        
        overall_percentage = 0
        if total_marks_possible > 0:
            overall_percentage = (total_marks_obtained / total_marks_possible) * 100
        
        from utils.grading import calculate_grade
        overall_grade = calculate_grade(overall_percentage)
        
        return {
            'student_name': self.user.full_name,
            'student_id': self.student_id,
            'department': self.department,
            'cgpa': float(self.cgpa),
            'total_credits': self.total_credits,
            'total_marks_obtained': round(total_marks_obtained, 2),
            'total_marks_possible': round(total_marks_possible, 2),
            'overall_percentage': round(overall_percentage, 2),
            'overall_grade': overall_grade,
            'courses': results,
            'completed_courses': len([r for r in results if r['status'] == 'COMPLETED']),
            'active_courses': len([r for r in results if r['status'] == 'ACTIVE']),
        }
class TeacherProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    employee_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    department = models.CharField(max_length=100, blank=True)
    qualification = models.TextField(blank=True)
    specialization = models.CharField(max_length=200, blank=True)
    joining_date = models.DateField(default=timezone.now)
    is_verified = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Teacher: {self.user.full_name}"


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)
    head = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='headed_department')
    description = models.TextField(blank=True)
    established_year = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    
    def __str__(self):
        return self.name


class RegistrationConfig(models.Model):
    """Configuration for registration periods and document requirements"""
    SEMESTER_CHOICES = [
        ('1', 'Semester 1'),
        ('2', 'Semester 2'),
        ('3', 'Summer'),
    ]
    
    registration_start_date = models.DateField()
    registration_end_date = models.DateField()
    semester = models.CharField(max_length=2, choices=SEMESTER_CHOICES, default='1')
    academic_year = models.CharField(max_length=10)
    
    require_grade_8 = models.BooleanField(default=True)
    require_grade_12 = models.BooleanField(default=True)
    require_transcript = models.BooleanField(default=True)
    require_other_documents = models.BooleanField(default=False)
    
    is_active = models.BooleanField(default=True)
    max_students_per_department = models.IntegerField(default=100)
    allow_senior_registration = models.BooleanField(default=True)
    allow_fresh_registration = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.academic_year} - Semester {self.semester}"

# Add to your models.py
# accounts/models.py - UPDATE PasswordResetOTP

class PasswordResetOTP(models.Model):
    """Model for storing password reset OTPs"""
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='reset_otps')
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    verification_token = models.CharField(max_length=100)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # ADD THIS
    expires_at = models.DateTimeField()
    
    def is_valid(self):
        from django.utils import timezone
        return not self.is_used and timezone.now() <= self.expires_at
    
    def __str__(self):
        return f"{self.email} - {self.otp} - {self.created_at}"