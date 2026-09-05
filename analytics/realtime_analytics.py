# backend/analytics/realtime_analytics.py
# COMPLETE REAL-TIME ANALYTICS ENGINE

from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta
from accounts.models import StudentProfile, TeacherProfile
from courses.models import Course, Enrollment
from exams.models import Exam, ExamAttempt
from payments.models import PaymentProof
from analytics.models import SystemLog
import pandas as pd
import numpy as np
from collections import defaultdict
import json

class RealtimeAnalyticsEngine:
    """Real-time analytics engine with predictive insights"""
    
    def __init__(self):
        self.cache = {}
        self.cache_expiry = 300  # 5 minutes
    
    def get_dashboard_data(self, role='ADMIN'):
        """Get comprehensive dashboard data"""
        
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)
        
        data = {
            'overview': self._get_overview_stats(),
            'user_analytics': self._get_user_analytics(),
            'course_analytics': self._get_course_analytics(),
            'exam_analytics': self._get_exam_analytics(),
            'payment_analytics': self._get_payment_analytics(),
            'trends': self._get_trends(week_ago),
            'predictions': self._get_predictions(),
            'recent_activity': self._get_recent_activity()
        }
        
        return data
    
    def _get_overview_stats(self):
        """Get overview statistics"""
        return {
            'total_users': StudentProfile.objects.count() + TeacherProfile.objects.count(),
            'total_students': StudentProfile.objects.count(),
            'total_teachers': TeacherProfile.objects.count(),
            'total_courses': Course.objects.filter(is_active=True).count(),
            'active_enrollments': Enrollment.objects.filter(status='ACTIVE').count(),
            'total_exams': Exam.objects.count(),
            'submitted_exams': ExamAttempt.objects.filter(status__in=['SUBMITTED', 'GRADED']).count(),
            'pending_payments': PaymentProof.objects.filter(status='PENDING').count(),
            'verified_payments': PaymentProof.objects.filter(status='VERIFIED').count(),
        }
    
    def _get_user_analytics(self):
        """Get user analytics with growth trends"""
        
        # Students by department
        students_by_department = StudentProfile.objects.values(
            'department'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Students by year
        students_by_year = {}
        for sem in range(1, 9):
            count = StudentProfile.objects.filter(current_semester=sem).count()
            if count > 0:
                students_by_year[f"Year {(sem + 1) // 2}"] = count
        
        # Teacher distribution
        teachers_by_department = TeacherProfile.objects.values(
            'department'
        ).annotate(
            count=Count('id')
        ).order_by('-count')
        
        return {
            'students_by_department': list(students_by_department),
            'students_by_year': students_by_year,
            'teachers_by_department': list(teachers_by_department),
            'total_students': StudentProfile.objects.count(),
            'total_teachers': TeacherProfile.objects.count(),
            'active_today': StudentProfile.objects.filter(
                user__last_login__date=timezone.now().date()
            ).count()
        }
    
    def _get_course_analytics(self):
        """Get course analytics"""
        
        # Most enrolled courses
        top_courses = Enrollment.objects.filter(
            status='ACTIVE'
        ).values(
            'course__course_code',
            'course__title'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Course completion rates
        completion_by_department = {}
        departments = Course.objects.values_list('department__name', flat=True).distinct()
        
        for dept in departments:
            if not dept:
                continue
            total_enrollments = Enrollment.objects.filter(
                course__department__name=dept
            ).count()
            completed = Enrollment.objects.filter(
                course__department__name=dept,
                status='COMPLETED'
            ).count()
            
            completion_rate = (completed / total_enrollments * 100) if total_enrollments > 0 else 0
            completion_by_department[dept] = round(completion_rate, 1)
        
        # Course popularity trends
        course_popularity = {
            'top_courses': list(top_courses),
            'completion_by_department': completion_by_department,
            'avg_enrollment_per_course': round(
                Enrollment.objects.filter(status='ACTIVE').count() / max(Course.objects.filter(is_active=True).count(), 1),
                2
            ),
            'total_active_courses': Course.objects.filter(is_active=True).count(),
        }
        
        return course_popularity
    
    def _get_exam_analytics(self):
        """Get exam analytics"""
        
        # Score distribution
        score_ranges = {
            '0-20': 0,
            '21-40': 0,
            '41-60': 0,
            '61-80': 0,
            '81-100': 0
        }
        
        attempts = ExamAttempt.objects.filter(status__in=['SUBMITTED', 'GRADED'])
        for attempt in attempts:
            if attempt.percentage:
                percentage = float(attempt.percentage)
                if percentage <= 20:
                    score_ranges['0-20'] += 1
                elif percentage <= 40:
                    score_ranges['21-40'] += 1
                elif percentage <= 60:
                    score_ranges['41-60'] += 1
                elif percentage <= 80:
                    score_ranges['61-80'] += 1
                else:
                    score_ranges['81-100'] += 1
        
        # Exam attendance rate
        exams = Exam.objects.filter(is_published=True)
        total_slots = exams.count() * StudentProfile.objects.count()
        completed_attempts = attempts.count()
        attendance_rate = (completed_attempts / total_slots * 100) if total_slots > 0 else 0
        
        # Passing rate
        passed = attempts.filter(passed=True).count()
        pass_rate = (passed / attempts.count() * 100) if attempts.count() > 0 else 0
        
        return {
            'score_distribution': score_ranges,
            'attendance_rate': round(attendance_rate, 2),
            'pass_rate': round(pass_rate, 2),
            'average_score': round(
                attempts.aggregate(avg=Avg('percentage'))['avg'] or 0,
                2
            ),
            'total_attempts': attempts.count(),
            'flagged_count': attempts.filter(status='FLAGGED').count()
        }
    
    def _get_payment_analytics(self):
        """Get payment analytics"""
        
        # Payments by month
        monthly_payments = {}
        current_year = timezone.now().year
        
        for month in range(1, 13):
            payments = PaymentProof.objects.filter(
                verified_at__year=current_year,
                verified_at__month=month
            )
            monthly_payments[f"Month {month}"] = {
                'count': payments.count(),
                'total': float(payments.aggregate(total=Sum('amount'))['total'] or 0)
            }
        
        # Payment status breakdown
        status_breakdown = {
            'pending': PaymentProof.objects.filter(status='PENDING').count(),
            'verified': PaymentProof.objects.filter(status='VERIFIED').count(),
            'rejected': PaymentProof.objects.filter(status='REJECTED').count()
        }
        
        # Revenue trends
        week_ago = timezone.now() - timedelta(days=7)
        revenue_week = PaymentProof.objects.filter(
            verified_at__gte=week_ago,
            status='VERIFIED'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        month_ago = timezone.now() - timedelta(days=30)
        revenue_month = PaymentProof.objects.filter(
            verified_at__gte=month_ago,
            status='VERIFIED'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return {
            'monthly_payments': monthly_payments,
            'status_breakdown': status_breakdown,
            'revenue_this_week': float(revenue_week),
            'revenue_this_month': float(revenue_month),
            'total_revenue': float(
                PaymentProof.objects.filter(status='VERIFIED').aggregate(total=Sum('amount'))['total'] or 0
            )
        }
    
    def _get_trends(self, since):
        """Get growth trends"""
        
        # New registrations
        new_students = StudentProfile.objects.filter(
            enrollment_date__gte=since
        ).count()
        
        # New enrollments
        new_enrollments = Enrollment.objects.filter(
            enrollment_date__gte=since
        ).count()
        
        # Exam attempts
        new_attempts = ExamAttempt.objects.filter(
            start_time__gte=since
        ).count()
        
        return {
            'new_students': new_students,
            'new_enrollments': new_enrollments,
            'new_exam_attempts': new_attempts,
            'weekly_growth_rate': self._calculate_growth_rate()
        }
    
    def _calculate_growth_rate(self):
        """Calculate weekly growth rate"""
        last_week = StudentProfile.objects.filter(
            enrollment_date__gte=timezone.now() - timedelta(weeks=2),
            enrollment_date__lt=timezone.now() - timedelta(weeks=1)
        ).count()
        
        this_week = StudentProfile.objects.filter(
            enrollment_date__gte=timezone.now() - timedelta(weeks=1)
        ).count()
        
        if last_week > 0:
            growth = ((this_week - last_week) / last_week) * 100
        else:
            growth = 100 if this_week > 0 else 0
        
        return round(growth, 2)
    
    def _get_predictions(self):
        """Generate predictions based on historical data"""
        
        # Predict enrollment growth
        recent_enrollments = Enrollment.objects.filter(
            enrollment_date__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        # Predict revenue
        recent_revenue = PaymentProof.objects.filter(
            verified_at__gte=timezone.now() - timedelta(days=30),
            status='VERIFIED'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        # Predict exam completion
        recent_attempts = ExamAttempt.objects.filter(
            start_time__gte=timezone.now() - timedelta(days=30)
        ).count()
        
        return {
            'predicted_monthly_enrollments': int(recent_enrollments * 4),
            'predicted_monthly_revenue': round(float(recent_revenue) * 4, 2),
            'predicted_weekly_attempts': int(recent_attempts / 4),
            'at_risk_students': self._find_at_risk_students()
        }
    
    def _find_at_risk_students(self):
        """Find students at risk of dropping out"""
        at_risk = []
        
        students = StudentProfile.objects.filter(is_enrolled=True)
        
        for student in students:
            risk_score = 0
            
            # Check if student has low attendance
            attempts = ExamAttempt.objects.filter(student=student)
            if attempts.count() > 0:
                avg_score = attempts.aggregate(avg=Avg('percentage'))['avg'] or 0
                if avg_score < 50:
                    risk_score += 20
            
            # Check if student has no recent activity
            recent_enrollments = Enrollment.objects.filter(
                student=student,
                enrollment_date__gte=timezone.now() - timedelta(days=30)
            ).count()
            if recent_enrollments == 0:
                risk_score += 15
            
            # Check payment status
            if student.payment_status != 'VERIFIED':
                risk_score += 10
            
            if risk_score >= 30:
                at_risk.append({
                    'student_id': student.id,
                    'name': student.user.full_name,
                    'email': student.user.email,
                    'risk_score': risk_score,
                    'risk_level': 'HIGH' if risk_score >= 50 else 'MEDIUM'
                })
        
        # Sort by risk score
        at_risk.sort(key=lambda x: x['risk_score'], reverse=True)
        return at_risk[:10]
    
    def _get_recent_activity(self):
        """Get recent system activity"""
        recent_logs = SystemLog.objects.all().order_by('-created_at')[:20]
        
        return [
            {
                'action': log.action,
                'user': log.user.full_name if log.user else 'System',
                'timestamp': log.created_at.isoformat(),
                'level': log.log_level
            }
            for log in recent_logs
        ]

# Singleton instance
analytics_engine = RealtimeAnalyticsEngine()