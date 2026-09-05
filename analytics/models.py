# analytics/models.py - COMPLETE FIXED VERSION
# All models in CORRECT ORDER

from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


# ============= SYSTEM LOG =============
class SystemLog(models.Model):
    LOG_LEVELS = [
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('DEBUG', 'Debug'),
    ]
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=100)
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    log_level = models.CharField(max_length=10, choices=LOG_LEVELS, default='INFO')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.action} - {self.created_at}"


# ============= DAILY ANALYTICS =============
class DailyAnalytics(models.Model):
    date = models.DateField(unique=True)
    
    total_students = models.IntegerField(default=0)
    new_students = models.IntegerField(default=0)
    total_teachers = models.IntegerField(default=0)
    total_admins = models.IntegerField(default=0)
    
    total_courses = models.IntegerField(default=0)
    active_courses = models.IntegerField(default=0)
    total_enrollments = models.IntegerField(default=0)
    new_enrollments = models.IntegerField(default=0)
    
    total_exams = models.IntegerField(default=0)
    exams_taken = models.IntegerField(default=0)
    exams_passed = models.IntegerField(default=0)
    average_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    
    total_payments = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    pending_payments = models.IntegerField(default=0)
    verified_payments = models.IntegerField(default=0)
    
    suspicious_events = models.IntegerField(default=0)
    flagged_exams = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Analytics for {self.date}"


# ============= SYSTEM CONFIG =============
class SystemConfig(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(default='')
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['key']
    
    def __str__(self):
        return f"{self.key} = {self.value[:50]}"
    
    @classmethod
    def get_value(cls, key, default=None):
        try:
            config = cls.objects.get(key=key)
            return config.value if config.value is not None else default
        except cls.DoesNotExist:
            return default
    
    @classmethod
    def set_value(cls, key, value, user=None, description=''):
        try:
            config, created = cls.objects.get_or_create(
                key=key,
                defaults={'value': value or '', 'description': description}
            )
            if not created:
                config.value = value or ''
                if description:
                    config.description = description
                if user:
                    config.updated_by = user
                config.save()
        except Exception as e:
            cls.objects.update_or_create(
                key=key,
                defaults={
                    'value': value or '',
                    'description': description or '',
                    'updated_by': user
                }
            )
        return config


# ============= BANK ACCOUNT =============
class BankAccount(models.Model):
    bank_name = models.CharField(max_length=100)
    account_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50)
    branch_name = models.CharField(max_length=100, blank=True)
    swift_code = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['-is_default', 'bank_name']
    
    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"


# ============= PAYMENT PERIOD =============
# ✅ MUST BE DEFINED BEFORE FeeStructure
class PaymentPeriod(models.Model):
    PERIOD_TYPES = [
        ('MINUTES', 'Minutes'),
        ('HOURS', 'Hours'),
        ('DAYS', 'Days'),
        ('WEEKS', 'Weeks'),
        ('MONTHS', 'Months'),
    ]
    
    name = models.CharField(max_length=50)
    period_type = models.CharField(max_length=20, choices=PERIOD_TYPES, default='MINUTES')
    duration_value = models.IntegerField(default=10, help_text="Number of the selected period type")
    duration_months = models.IntegerField(default=0, help_text="Equivalent months for fee calculation (optional)")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        ordering = ['duration_value']
    
    def __str__(self):
        return f"{self.name} ({self.duration_value} {self.get_period_type_display()})"
    
    def get_duration_in_minutes(self):
        """Convert period to minutes"""
        if self.period_type == 'MINUTES':
            return self.duration_value
        elif self.period_type == 'HOURS':
            return self.duration_value * 60
        elif self.period_type == 'DAYS':
            return self.duration_value * 24 * 60
        elif self.period_type == 'WEEKS':
            return self.duration_value * 7 * 24 * 60
        elif self.period_type == 'MONTHS':
            return self.duration_value * 30 * 24 * 60
        return 60
    
    def calculate_due_date(self, start_date=None):
        """Calculate the due date based on the period duration"""
        from datetime import timedelta
        
        if start_date is None:
            start_date = timezone.now()
        
        minutes = self.get_duration_in_minutes()
        return start_date + timedelta(minutes=minutes)
    
    def calculate_due_date_str(self, start_date=None):
        """Get due date as string for display"""
        due_date = self.calculate_due_date(start_date)
        return due_date.strftime("%Y-%m-%d %H:%M:%S")
    
    def get_duration_display(self):
        """Get human-readable duration"""
        if self.period_type == 'MINUTES':
            return f"{self.duration_value} minute{'s' if self.duration_value > 1 else ''}"
        elif self.period_type == 'HOURS':
            return f"{self.duration_value} hour{'s' if self.duration_value > 1 else ''}"
        elif self.period_type == 'DAYS':
            return f"{self.duration_value} day{'s' if self.duration_value > 1 else ''}"
        elif self.period_type == 'WEEKS':
            return f"{self.duration_value} week{'s' if self.duration_value > 1 else ''}"
        elif self.period_type == 'MONTHS':
            return f"{self.duration_value} month{'s' if self.duration_value > 1 else ''}"
        return f"{self.duration_value} periods"


# ============= FEE STRUCTURE =============
# ✅ MUST BE DEFINED BEFORE StudentPaymentSchedule
class FeeStructure(models.Model):
    department = models.ForeignKey('accounts.Department', on_delete=models.CASCADE, related_name='fee_structures')
    payment_period = models.ForeignKey(PaymentPeriod, on_delete=models.CASCADE, related_name='fee_structures')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    penalty_per_day = models.DecimalField(max_digits=10, decimal_places=2, default=10.00)
    grace_period_days = models.IntegerField(default=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        ordering = ['department', '-created_at']
        unique_together = ['department', 'payment_period']
    
    def __str__(self):
        dept_name = self.department.name if self.department else 'Unknown'
        period_name = self.payment_period.name if self.payment_period else 'Unknown'
        return f"{dept_name} - {period_name} (ETB {self.amount})"


# ============= STUDENT PAYMENT SCHEDULE =============
# ✅ NOW FeeStructure AND PaymentPeriod are defined!
# analytics/models.py - COMPLETE StudentPaymentSchedule Class

# analytics/models.py - COMPLETE FINAL VERSION
# INCLUDES AUTO-LOCK ON SAVE, AUTO-LOCK ON ACCESS, AND DYNAMIC DUE DATE CALCULATION



# ================================================================
# STUDENT PAYMENT SCHEDULE MODEL
# ================================================================

class StudentPaymentSchedule(models.Model):
    """
    Student Payment Schedule Model
    Tracks payment schedules for students with auto-lock functionality.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('PARTIAL', 'Partial'),
        ('LOCKED', 'Locked - Access Denied'),
        ('PENALTY_PAID', 'Penalty Paid'),
        ('PENALTY_PENDING', 'Penalty Pending'),
    ]

    student = models.ForeignKey('accounts.StudentProfile', on_delete=models.CASCADE, related_name='payment_schedules')
    fee_structure = models.ForeignKey('analytics.FeeStructure', on_delete=models.CASCADE, related_name='student_schedules')
    period_number = models.IntegerField(default=1, help_text="Which period number (1st, 2nd, 3rd...)")
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    due_date = models.DateTimeField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    penalty_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_date = models.DateTimeField(null=True, blank=True)
    locked_at = models.DateTimeField(null=True, blank=True)
    unlocked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date']
        unique_together = ['student', 'fee_structure', 'period_number']

    def __str__(self):
        student_name = self.student.user.full_name if self.student and self.student.user else 'Unknown'
        return f"{student_name} - Period {self.period_number} (Due: {self.due_date})"

    # ================================================================
    # 1. CALCULATE PENALTY
    # ================================================================
    def calculate_penalty(self):
        """Calculate penalty if payment is overdue"""
        if self.status in ['PAID', 'PARTIAL', 'PENALTY_PAID']:
            return Decimal('0.00')

        now = timezone.now()
        if now <= self.due_date:
            return Decimal('0.00')

        seconds_overdue = (now - self.due_date).total_seconds()
        days_overdue = seconds_overdue / (24 * 60 * 60)

        grace_days = self.fee_structure.grace_period_days if self.fee_structure else 0

        if days_overdue <= grace_days:
            return Decimal('0.00')

        penalty_days = days_overdue - grace_days
        penalty_per_day = float(self.fee_structure.penalty_per_day) if self.fee_structure else 10
        penalty = penalty_days * penalty_per_day
        return Decimal(str(penalty))

    # ================================================================
    # 2. OVERDUE CHECKS
    # ================================================================
    def is_overdue(self):
        """Check if payment is overdue"""
        now = timezone.now()
        return now > self.due_date and self.status not in ['PAID', 'PARTIAL', 'PENALTY_PAID']

    def days_overdue(self):
        """Get number of days overdue"""
        if not self.is_overdue():
            return 0
        now = timezone.now()
        seconds_overdue = (now - self.due_date).total_seconds()
        return round(seconds_overdue / (24 * 60 * 60), 2)

    def minutes_overdue(self):
        """Get number of minutes overdue"""
        if not self.is_overdue():
            return 0
        now = timezone.now()
        seconds_overdue = (now - self.due_date).total_seconds()
        return int(seconds_overdue / 60)

    def minutes_remaining(self):
        """Get minutes remaining until due date"""
        if self.status in ['PAID', 'PENALTY_PAID']:
            return 0
        now = timezone.now()
        if now >= self.due_date:
            return 0
        seconds_remaining = (self.due_date - now).total_seconds()
        return round(seconds_remaining / 60, 2)

    # ================================================================
    # 3. ACCESS ALLOWED CHECK
    # ================================================================
    def is_access_allowed(self):
        """
        Check if student should have access to services.
        Returns: True if access allowed, False if locked.
        """
        # If locked, always deny access
        if self.status == 'LOCKED':
            return False

        # If paid, always allow access
        if self.status in ['PAID', 'PENALTY_PAID']:
            return True

        # Check if within due date or grace period
        now = timezone.now()
        if now <= self.due_date:
            return True

        # Check grace period
        seconds_overdue = (now - self.due_date).total_seconds()
        days_overdue = seconds_overdue / (24 * 60 * 60)
        grace_days = self.fee_structure.grace_period_days if self.fee_structure else 0

        if days_overdue <= grace_days:
            return True

        # Overdue beyond grace period - deny access
        return False

    # ================================================================
    # 4. UPDATE STATUS - THE HEART OF THE AUTO-LOCK SYSTEM
    # ================================================================
   
        # ================================================================
    # 4. UPDATE STATUS - THE HEART OF THE AUTO-LOCK SYSTEM
    # ================================================================
    def update_status(self):
        """
        Update payment status and apply penalties.
        This locks students when the due date has passed.
        This method is called automatically on every save and access check.
        """
        # Don't update if already paid
        if self.status in ['PAID', 'PENALTY_PAID']:
            return False

        now = timezone.now()
        updated = False

        # ✅ CRITICAL: Check if overdue
        if now > self.due_date:
            seconds_overdue = (now - self.due_date).total_seconds()
            minutes_overdue = int(seconds_overdue / 60)
            days_overdue = seconds_overdue / (24 * 60 * 60)

            # Get grace period
            grace_days = self.fee_structure.grace_period_days if self.fee_structure else 0

            # Calculate penalty
            penalty = self.calculate_penalty()

            # Update based on status
            if days_overdue <= grace_days:
                # Within grace period - keep as PENDING
                if self.status != 'PENDING':
                    self.status = 'PENDING'
                    self.penalty_amount = Decimal('0.00')
                    self.total_amount = self.amount
                    updated = True
            else:
                # ✅ OVERDUE - LOCK THE ACCOUNT IMMEDIATELY
                if self.status == 'OVERDUE':
                    # ✅ CRITICAL: If already OVERDUE, calculate penalty and LOCK
                    self.status = 'LOCKED'
                    self.locked_at = now
                    self.penalty_amount = penalty
                    self.total_amount = self.amount + penalty
                    updated = True

                    # Update student's payment status
                    try:
                        self.student.payment_status = 'OVERDUE_LOCKED'
                        self.student.save(update_fields=['payment_status'])
                        logger.info(f"🔒 Payment status changed to OVERDUE_LOCKED for {self.student.user.email}")
                    except Exception as e:
                        logger.error(f"Failed to update student payment status: {e}")

                    # Send notification
                    try:
                        from notifications.utils import send_notification
                        send_notification(
                            recipient_user=self.student.user,
                            title='🔒 Account Locked - Payment Overdue',
                            message=f'''Your account has been locked due to overdue payment.

Payment Period: Period {self.period_number}
Due Date: {self.due_date.strftime("%Y-%m-%d %H:%M:%S")}
Amount Due: ETB {self.amount}
Penalty: ETB {self.penalty_amount}
Total Due: ETB {self.total_amount}
Minutes Overdue: {minutes_overdue}

Please make the payment to restore access to all services.
''',
                            notification_type='SYSTEM_ALERT',
                            link='/payments'
                        )
                    except Exception as e:
                        logger.error(f"Failed to send lock notification: {e}")

                    logger.info(f"🔒 Account LOCKED for {self.student.user.email} - {minutes_overdue} minutes overdue")

                elif self.status != 'LOCKED':
                    # First time becoming overdue
                    self.status = 'OVERDUE'
                    self.penalty_amount = penalty
                    self.total_amount = self.amount + penalty
                    updated = True

        # ✅ Save if updated
        if updated:
            self.save(update_fields=['status', 'penalty_amount', 'total_amount', 'locked_at'])
            self.refresh_from_db()

        return updated   
    # ================================================================
    # 5. SAVE METHOD - AUTO-UPDATE STATUS ON EVERY SAVE
    # ================================================================
    def save(self, *args, **kwargs):
        """
        Override save to auto-update status before saving.
        This ensures the lock is applied on every save, regardless of how the save was triggered.
        """
        # ✅ CRITICAL: Always call update_status before saving
        self.update_status()
        super().save(*args, **kwargs)
        self.refresh_from_db()

    # ================================================================
    # 6. UNLOCK METHOD (FOR FINANCE/ADMIN)
    # ================================================================
    def unlock(self):
        """Manually unlock the student account"""
        if self.status == 'LOCKED':
            self.status = 'PENDING'
            self.unlocked_at = timezone.now()
            self.penalty_amount = Decimal('0.00')
            self.total_amount = self.amount
            self.save()

            # Update student payment status
            try:
                self.student.payment_status = 'PENDING'
                self.student.save()
            except:
                pass

            # Send notification
            try:
                from notifications.utils import send_notification
                send_notification(
                    recipient_user=self.student.user,
                    title='🔓 Account Unlocked',
                    message='Your account has been unlocked. Please complete your payment to keep it active.',
                    notification_type='SYSTEM_ALERT',
                    link='/payments'
                )
            except:
                pass

            logger.info(f"🔓 Account UNLOCKED for {self.student.user.email}")
            return True
        return False

    # ================================================================
    # 7. MARK AS PAID (FOR FINANCE/ADMIN)
    # ================================================================
    def mark_paid(self):
        """Mark this schedule as paid and update student status"""
        if self.status in ['PENDING', 'OVERDUE', 'LOCKED', 'PENALTY_PENDING']:
            self.status = 'PAID'
            self.payment_date = timezone.now()
            self.penalty_amount = Decimal('0.00')
            self.total_amount = self.amount
            self.save()

            # Update student payment status
            try:
                self.student.payment_status = 'VERIFIED'
                self.student.save()
            except:
                pass

            # Send notification
            try:
                from notifications.utils import send_notification
                send_notification(
                    recipient_user=self.student.user,
                    title='✅ Payment Confirmed!',
                    message=f'Your payment of ETB {self.amount} has been confirmed for Period {self.period_number}.',
                    notification_type='PAYMENT_VERIFIED',
                    link='/dashboard'
                )
            except:
                pass

            logger.info(f"✅ Payment marked as PAID for {self.student.user.email} - Period {self.period_number}")
            return True
        return False

    # ================================================================
    # 8. FORCE LOCK (FOR EMERGENCY USE BY ADMIN)
    # ================================================================
    def force_lock(self):
        """Force lock this payment schedule immediately"""
        if self.status != 'LOCKED':
            self.status = 'LOCKED'
            self.locked_at = timezone.now()
            self.penalty_amount = self.calculate_penalty()
            self.total_amount = self.amount + self.penalty_amount
            self.save()
            logger.info(f"🔒 Force locked schedule {self.id} for {self.student.user.email}")
            return True
        return False
# ============= STUDENT SERVICE ACCESS =============
class StudentServiceAccess(models.Model):
    SERVICE_TYPES = [
        ('COURSE_ENROLLMENT', 'Course Enrollment'),
        ('EXAM_TAKING', 'Exam Taking'),
        ('LIVE_CLASS', 'Live Class'),
        ('COURSE_MATERIALS', 'Course Materials'),
        ('ASSIGNMENT_SUBMISSION', 'Assignment Submission'),
        ('RESULTS_VIEWING', 'Results Viewing'),
        ('CERTIFICATE_DOWNLOAD', 'Certificate Download'),
    ]
    
    student = models.ForeignKey('accounts.StudentProfile', on_delete=models.CASCADE, related_name='service_access')
    service_type = models.CharField(max_length=30, choices=SERVICE_TYPES)
    is_allowed = models.BooleanField(default=True)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['student', 'service_type']
    
    def __str__(self):
        return f"{self.student.user.full_name} - {self.service_type}: {self.is_allowed}"


# ============= STUDENT ACCESS LOG =============
class StudentAccessLog(models.Model):
    ACCESS_TYPES = [
        ('LOGIN', 'Login Attempt'),
        ('EXAM', 'Exam Access'),
        ('COURSE', 'Course Enrollment'),
        ('ASSIGNMENT', 'Assignment Access'),
        ('LIVE_CLASS', 'Live Class Access'),
    ]
    
    student = models.ForeignKey('accounts.StudentProfile', on_delete=models.CASCADE, related_name='access_logs')
    access_type = models.CharField(max_length=20, choices=ACCESS_TYPES)
    resource_id = models.IntegerField(null=True, blank=True)
    allowed = models.BooleanField(default=False)
    reason = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.student.user.full_name} - {self.access_type} - {'✅' if self.allowed else '❌'}"


# ============= ID SEQUENCE =============
class IDSequence(models.Model):
    """Track auto-increment sequence for student IDs"""
    prefix = models.CharField(max_length=20, default='MAU')
    year = models.IntegerField()
    last_number = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['prefix', 'year']
        ordering = ['-year']
    
    def __str__(self):
        return f"{self.prefix}{self.year}-{self.last_number}"
    
    @classmethod
    def get_next_number(cls, prefix='MAU', year=None):
        """Get next sequence number with atomic increment"""
        from django.db import transaction
        
        if year is None:
            year = timezone.now().year
        
        with transaction.atomic():
            sequence, created = cls.objects.select_for_update().get_or_create(
                prefix=prefix,
                year=year,
                defaults={'last_number': 0}
            )
            sequence.last_number += 1
            sequence.save()
            return sequence.last_number
    
    @classmethod
    def get_current_number(cls, prefix='MAU', year=None):
        """Get current sequence number without incrementing"""
        if year is None:
            year = timezone.now().year
        
        try:
            sequence = cls.objects.get(prefix=prefix, year=year)
            return sequence.last_number
        except cls.DoesNotExist:
            return 0
    
    @classmethod
    def reset_sequence(cls, prefix='MAU', year=None):
        """Reset sequence to 0"""
        if year is None:
            year = timezone.now().year
        
        try:
            sequence = cls.objects.get(prefix=prefix, year=year)
            sequence.last_number = 0
            sequence.save()
            return True
        except cls.DoesNotExist:
            return False