# analytics/permissions.py - COMPLETE
# Permission classes for service access control

from rest_framework.permissions import BasePermission
from rest_framework.exceptions import PermissionDenied
from accounts.models import StudentProfile


class HasServiceAccessPermission(BasePermission):
    """Check if student has access to specific services"""
    
    def __init__(self, service_type):
        self.service_type = service_type
    
    def has_permission(self, request, view):
        user = request.user
        
        # Admins, Teachers, Finance, Registrar always have access
        if user.role in ['ADMIN', 'TEACHER', 'FINANCE', 'REGISTRAR', 'DEPT_HEAD']:
            return True
        
        # Check if user is a student
        if user.role != 'STUDENT':
            return False
        
        try:
            student = StudentProfile.objects.get(user=user)
        except StudentProfile.DoesNotExist:
            return False
        
        # Check if student is activated
        if not student.is_enrolled:
            return False
        
        # Get current payment schedule
        from analytics.models import StudentPaymentSchedule
        schedule = StudentPaymentSchedule.objects.filter(
            student=student,
            status__in=['PENDING', 'OVERDUE']
        ).order_by('due_date').first()
        
        if schedule:
            # Check if within grace period or paid
            return schedule.is_access_allowed()
        
        # No pending schedule - check if all paid
        all_paid = StudentPaymentSchedule.objects.filter(
            student=student,
            status='PAID'
        ).count() == StudentPaymentSchedule.objects.filter(student=student).count()
        
        return all_paid


# Service-specific permission classes
class CanEnrollCoursePermission(HasServiceAccessPermission):
    def __init__(self):
        super().__init__('COURSE_ENROLLMENT')


class CanTakeExamPermission(HasServiceAccessPermission):
    def __init__(self):
        super().__init__('EXAM_TAKING')


class CanJoinLiveClassPermission(HasServiceAccessPermission):
    def __init__(self):
        super().__init__('LIVE_CLASS')


class CanViewMaterialsPermission(HasServiceAccessPermission):
    def __init__(self):
        super().__init__('COURSE_MATERIALS')


class CanSubmitAssignmentPermission(HasServiceAccessPermission):
    def __init__(self):
        super().__init__('ASSIGNMENT_SUBMISSION')


class CanViewResultsPermission(HasServiceAccessPermission):
    def __init__(self):
        super().__init__('RESULTS_VIEWING')


def check_service_access(user, service_type):
    """Helper function to check service access"""
    if user.role in ['ADMIN', 'TEACHER', 'FINANCE', 'REGISTRAR', 'DEPT_HEAD']:
        return True, None
    
    if user.role != 'STUDENT':
        return False, 'Access denied. Student role required.'
    
    try:
        student = StudentProfile.objects.get(user=user)
    except StudentProfile.DoesNotExist:
        return False, 'Student profile not found.'
    
    if not student.is_enrolled:
        return False, 'Account not activated. Please contact registrar.'
    
    from analytics.models import StudentPaymentSchedule
    schedule = StudentPaymentSchedule.objects.filter(
        student=student,
        status__in=['PENDING', 'OVERDUE']
    ).order_by('due_date').first()
    
    if schedule:
        if schedule.is_access_allowed():
            return True, None
        else:
            return False, f'Payment is overdue by {schedule.days_overdue()} days. Amount due: ETB {schedule.total_amount}'
    
    all_paid = StudentPaymentSchedule.objects.filter(
        student=student,
        status='PAID'
    ).count() == StudentPaymentSchedule.objects.filter(student=student).count()
    
    if all_paid:
        return True, None
    
    return False, 'Payment required to access services. Please contact finance.'
 # analytics/permissions.py - ADD THIS CLASS

class IsAdminUser(permissions.BasePermission):
    """Check if user has ADMIN role"""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'ADMIN'   