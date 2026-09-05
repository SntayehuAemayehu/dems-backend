# analytics/middleware.py - COMPLETE FIXED VERSION

from django.http import JsonResponse
from django.utils import timezone
from django.shortcuts import redirect
from .models import SystemConfig
from accounts.models import StudentProfile
from analytics.models import StudentPaymentSchedule
import logging

# analytics/middleware.py - COMPLETE FINAL VERSION
logger = logging.getLogger(__name__)

class StudentAccessMiddleware:
    """
    GLOBAL MIDDLEWARE - Denies ALL student services when payment is locked.
    This blocks EVERYTHING: courses, exams, live classes, results, etc.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # ✅ ONLY ALLOWED URLs for locked students
        self.allowed_urls = [
            '/api/auth/login',
            '/api/auth/register',
            '/api/auth/logout',
            '/api/auth/forgot-password',
            '/api/auth/send-reset-otp',
            '/api/auth/verify-otp',
            '/api/payments/',
            '/api/analytics/payment-status/',
            '/api/analytics/check-access/',
            '/api/analytics/payment-config/',
            '/api/analytics/payment-schedules/',
            '/static/',
            '/media/',
            '/admin/',
            '/api/notifications/',
            '/api/chat/',
        ]

    def __call__(self, request):
        response = self.get_response(request)
        return response

   # backend/analytics/middleware.py
# REPLACE THE ENTIRE process_view method (around line 30-80)

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Check access - ONLY block if student is ENROLLED and schedule is LOCKED"""

        # Skip for non-authenticated users
        if not request.user or not request.user.is_authenticated:
            return None

        # Skip for non-student roles
        if request.user.role != 'STUDENT':
            return None

        # Skip for ALLOWED URLs (payments, login, etc.)
        for url in self.allowed_urls:
            if request.path.startswith(url):
                return None

        # Get student profile
        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return None

        # ✅ ============================================================
        # ✅ CRITICAL FIX: NEW STUDENTS (NOT ENROLLED) - ALWAYS ALLOW
        # ✅ ============================================================
        
        # ✅ If student is NOT enrolled, they are NEW. Allow access.
        if not student.is_enrolled:
            logger.info(f"✅ NEW STUDENT (not enrolled): {student.user.email} - Access allowed")
            return None

        # ✅ ============================================================
        # ✅ CHECK PAYMENT SCHEDULES - ONLY FOR ENROLLED STUDENTS
        # ✅ ============================================================
        
        # ✅ Check if student has ANY payment schedule
        schedules = StudentPaymentSchedule.objects.filter(student=student)
        
        # ✅ NO SCHEDULE - ALLOW ACCESS
        if not schedules.exists():
            logger.info(f"✅ ENROLLED STUDENT (no schedule): {student.user.email} - Access allowed")
            return None

        # ✅ CHECK EACH SCHEDULE - ONLY BLOCK IF LOCKED
        for schedule in schedules:
            # ✅ Force update status
            schedule.update_status()
            schedule.save()
            schedule.refresh_from_db()

            # ✅ ONLY BLOCK IF STATUS IS LOCKED
            if schedule.status == 'LOCKED':
                message = f'🔒 Account locked. Amount due: ETB {float(schedule.total_amount):.2f}'
                
                logger.warning(f"🚫 DENIED ACCESS: {student.user.email} - LOCKED")

                # Return JSON response for API requests
                if request.path.startswith('/api/'):
                    return JsonResponse({
                        'error': 'Access Denied',
                        'message': message,
                        'payment_required': True,
                        'action_required': 'Make payment to restore access',
                        'redirect': '/payments',
                        'status': 'LOCKED',
                        'amount_due': float(schedule.total_amount),
                        'is_locked': True,
                    }, status=403)

                # For non-API, redirect to payments page
                from urllib.parse import quote
                return redirect(f'/payments?locked=true&reason={quote(message)}')

            # ✅ OVERDUE but NOT LOCKED - ALLOW ACCESS during grace period
            if schedule.is_overdue():
                days = schedule.days_overdue()
                grace = schedule.fee_structure.grace_period_days if schedule.fee_structure else 0
                
                # ✅ Only block if days overdue > grace period AND status is LOCKED
                if days > grace and schedule.status == 'LOCKED':
                    message = f'🔒 Payment overdue by {days:.1f} days. Amount: ETB {float(schedule.total_amount):.2f}'
                    
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'error': 'Access Denied',
                            'message': message,
                            'payment_required': True,
                            'redirect': '/payments',
                            'status': 'OVERDUE',
                            'amount_due': float(schedule.total_amount),
                            'days_overdue': days,
                            'is_locked': True,
                        }, status=403)
                    
                    from urllib.parse import quote
                    return redirect(f'/payments?locked=true&reason={quote(message)}')

        # ✅ ACCESS ALLOWED
        return None

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR')

# ================================================================
# SYSTEM LOCK MIDDLEWARE
# ================================================================

class SystemLockMiddleware:
    """
    Middleware to lock the entire system for maintenance
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        self.public_urls = [
            '/api/auth/login',
            '/api/auth/register',
            '/api/auth/logout',
            '/api/auth/forgot-password',
            '/api/auth/reset-password',
            '/api/auth/send-reset-otp',
            '/api/auth/verify-otp',
            '/admin/',
            '/static/',
            '/media/',
            '/api/analytics/system-lock/',
        ]
    
    def __call__(self, request):
        is_locked = SystemConfig.get_value('system_locked', 'false') == 'true'
        
        if is_locked and request.path.startswith('/api/'):
            for url in self.public_urls:
                if request.path.startswith(url):
                    return self.get_response(request)
            
            if request.user and request.user.is_authenticated and request.user.role == 'ADMIN':
                return self.get_response(request)
            
            lock_message = SystemConfig.get_value('system_lock_message', 'System is locked for maintenance.')
            return JsonResponse({
                'error': 'System Locked',
                'message': lock_message,
                'status': 'LOCKED'
            }, status=503)
        
        return self.get_response(request)