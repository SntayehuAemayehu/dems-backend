# payments/models.py - COMPLETE FIXED VERSION

from django.db import models
from django.conf import settings
from django.utils import timezone

class PaymentProof(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Verification'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
        ('NEED_RESUBMISSION', 'Need Resubmission'),
        ('ROLLED_BACK', 'Rolled Back'),
    ]
    
    PAYMENT_TYPE_CHOICES = [
        ('REGISTRATION', 'Registration Fee'),
        ('SEMESTER', 'Semester Fee'),
        ('EXAM', 'Exam Fee'),
        ('LATE', 'Late Registration Fee'),
        ('ROLLBACK', 'Rollback - Refund'),
    ]
    
    student = models.ForeignKey('accounts.StudentProfile', on_delete=models.CASCADE, related_name='payment_proofs')
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, default='SEMESTER')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    bank_name = models.CharField(max_length=100, blank=True, default='')
    transaction_id = models.CharField(max_length=100, unique=True)
    transaction_date = models.DateField()
    receipt_image = models.ImageField(upload_to='payment_receipts/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    semester = models.CharField(max_length=10, null=True, blank=True)
    academic_year = models.CharField(max_length=10, null=True, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Rollback fields
    rolled_back_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='rolled_back_payments')
    rolled_back_at = models.DateTimeField(null=True, blank=True)
    rollback_reason = models.TextField(blank=True)
    original_status = models.CharField(max_length=20, blank=True)
    original_payment_status = models.CharField(max_length=20, blank=True)
    is_rolled_back = models.BooleanField(default=False)
    rollback_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.student.user.full_name} - {self.transaction_id}"
    
    def rollback(self, user, reason='Payment rolled back', notes=''):
        """Rollback this payment"""
        if self.is_rolled_back:
            raise ValueError('Payment already rolled back')
        
        if self.status == 'ROLLED_BACK':
            raise ValueError('Payment already rolled back')
        
        # Store original status
        self.original_status = self.status
        self.original_payment_status = self.student.payment_status
        
        # Update payment
        self.status = 'ROLLED_BACK'
        self.is_rolled_back = True
        self.rolled_back_by = user
        self.rolled_back_at = timezone.now()
        self.rollback_reason = reason
        self.rollback_notes = notes
        
        # Update student payment status
        if self.student.payment_status == 'VERIFIED':
            self.student.payment_status = 'PENDING'
            self.student.save()
        
        self.save()
        
        # Create rollback record
        PaymentRollback.objects.create(
            payment=self,
            student=self.student,
            rolled_by=user,
            reason=reason,
            amount=self.amount,
            original_status=self.original_status,
            rollback_type='FULL',
            notes=notes
        )
        
        return True

    def reverse_rollback(self, user, reason='Rollback reversed'):
        """Reverse a rollback"""
        if not self.is_rolled_back:
            raise ValueError('Payment is not rolled back')
        
        # Restore original status
        self.status = self.original_status if self.original_status else 'PENDING'
        self.is_rolled_back = False
        self.rolled_back_by = None
        self.rolled_back_at = None
        self.rollback_reason = ''
        self.rollback_notes = ''
        
        # Restore student payment status
        if self.original_payment_status:
            self.student.payment_status = self.original_payment_status
            self.student.save()
        
        self.save()
        
        return True


class PaymentRollback(models.Model):
    """Track payment rollbacks"""
    ROLLBACK_TYPES = [
        ('FULL', 'Full Rollback'),
        ('PARTIAL', 'Partial Rollback'),
        ('DEPARTMENT_CHANGE', 'Department Change'),
        ('ADMIN', 'Admin Rollback'),
        ('ERROR', 'Error Correction'),
    ]
    
    payment = models.ForeignKey(PaymentProof, on_delete=models.CASCADE, related_name='rollbacks')
    student = models.ForeignKey('accounts.StudentProfile', on_delete=models.CASCADE, related_name='payment_rollbacks')
    rolled_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='initiated_rollbacks')
    reason = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    original_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20, default='ROLLED_BACK')
    rollback_type = models.CharField(max_length=20, choices=ROLLBACK_TYPES, default='FULL')
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Rollback of {self.payment.transaction_id} - {self.created_at}"


class PaymentTransaction(models.Model):
    """Track payment transactions"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PAID', 'Paid'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
        ('REFUNDED', 'Refunded'),
    ]
    
    student = models.ForeignKey('accounts.StudentProfile', on_delete=models.CASCADE, related_name='payment_transactions')
    tx_ref = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    response_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.tx_ref} - {self.status}"


class Invoice(models.Model):
    invoice_number = models.CharField(max_length=50, unique=True)
    student = models.ForeignKey('accounts.StudentProfile', on_delete=models.CASCADE, related_name='invoices')
    semester = models.CharField(max_length=10)
    academic_year = models.CharField(max_length=10)
    issue_date = models.DateField(default=timezone.now)
    due_date = models.DateField()
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    balance_due = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Invoice {self.invoice_number}"