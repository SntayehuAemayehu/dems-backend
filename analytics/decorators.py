# analytics/decorators.py - NEW FILE

from functools import wraps
from django.http import JsonResponse
from django.shortcuts import redirect
from accounts.models import StudentProfile

def require_payment_access(view_func):
    """
    Decorator to require payment access for views
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Skip for non-students
        if not request.user or request.user.role != 'STUDENT':
            return view_func(request, *args, **kwargs)
        
        # Get student profile
        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return view_func(request, *args, **kwargs)
        
        # If student is fully enrolled and paid, allow
        if student.is_enrolled and student.payment_status == 'VERIFIED':
            return view_func(request, *args, **kwargs)
        
        # Check payment access
        has_access, reason = check_student_access(student)
        
        if not has_access:
            # Log denied access
            try:
                from analytics.models import StudentAccessLog
                StudentAccessLog.objects.create(
                    student=student,
                    access_type='LOGIN',
                    allowed=False,
                    reason=reason
                )
            except:
                pass
            
            # Return appropriate response
            if request.path.startswith('/api/'):
                return JsonResponse({
                    'error': 'Access Denied',
                    'message': reason,
                    'payment_required': True,
                    'redirect': '/payments'
                }, status=403)
            
            return redirect('/payments?locked=true')
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def check_student_access(student):
    """Check if student has payment access"""
    from analytics.models import StudentPaymentSchedule
    
    # Check if student has paid for current period
    paid_schedules = StudentPaymentSchedule.objects.filter(
        student=student,
        status__in=['PAID', 'PENALTY_PAID']
    ).order_by('-created_at')
    
    if paid_schedules.exists():
        latest = paid_schedules.first()
        if latest.end_date and latest.end_date >= timezone.now().date():
            return True, "Active payment"
    
    # Check for overdue
    overdue = StudentPaymentSchedule.objects.filter(
        student=student,
        status__in=['PENDING', 'OVERDUE']
    )
    
    for schedule in overdue:
        if schedule.is_overdue():
            days = schedule.days_overdue()
            return False, f"Payment overdue. Penalty: ETB {schedule.calculate_penalty()}"
    
    return True, "Payment pending"