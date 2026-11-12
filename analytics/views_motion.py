# backend/analytics/views_motion.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count, Avg, Sum, Q
from django.utils import timezone
from datetime import timedelta
from accounts.models import StudentProfile, User
from courses.models import Course, Enrollment
from exams.models import Exam, ExamAttempt
from payments.models import PaymentProof


class LivePulseView(APIView):
    """
    GET /api/analytics/live-pulse/
    Tiny payload polled every 5–10s to power live counters on dashboards.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        last_24h = now - timedelta(hours=24)

        data = {
            'timestamp': now.isoformat(),
            'students_online': User.objects.filter(
                last_login__gte=now - timedelta(minutes=15),
                role='STUDENT',
            ).count(),
            'active_exams': ExamAttempt.objects.filter(
                status='IN_PROGRESS',
            ).count(),
            'submissions_today': ExamAttempt.objects.filter(
              end_time__gte=now - timedelta(hours=24),  # <--- Change submitted_at to end_time
            ).count(),
            'payments_last_hour': PaymentProof.objects.filter(
                uploaded_at__gte=now - timedelta(hours=1),
            ).count(),
        }

        # Role-specific add-ons
        if request.user.role == 'STUDENT':
            try:
                student = request.user.student_profile
                data['my_cgpa'] = float(student.cgpa or 0)
                data['my_active_courses'] = Enrollment.objects.filter(
                    student=student, status='ACTIVE',
                ).count()
                data['my_pending_assignments'] = Exam.objects.filter(
                    course__enrollments__student=student,
                    is_published=True,
                    end_time__gte=now,
                ).count()
            except StudentProfile.DoesNotExist:
                pass

        if request.user.role in ('TEACHER', 'ADMIN'):
            data['system_load'] = min(
                100,
                ExamAttempt.objects.filter(status='IN_PROGRESS').count() * 5,
            )

        return Response(data)


class SparklineDataView(APIView):
    """
    GET /api/analytics/sparkline/?metric=enrollments&days=14
    Returns time-series for animated line/spark charts.
    """
    permission_classes = [IsAuthenticated]

    METRICS = {
        'enrollments': lambda d: Enrollment.objects.filter(
            enrollment_date__gte=d,
        ).extra(select={'day': 'date(enrollment_date)'})
            .values('day').annotate(count=Count('id')).order_by('day'),
        'exams': lambda d: ExamAttempt.objects.filter(
            start_time__gte=d,
        ).extra(select={'day': 'date(start_time)'})
            .values('day').annotate(count=Count('id')).order_by('day'),
        'payments': lambda d: PaymentProof.objects.filter(
            uploaded_at__gte=d,
        ).extra(select={'day': 'date(uploaded_at)'})
            .values('day').annotate(count=Count('id')).order_by('day'),
    }

    def get(self, request):
        metric = request.query_params.get('metric', 'enrollments')
        days = int(request.query_params.get('days', 14))
        since = timezone.now() - timedelta(days=days)

        fn = self.METRICS.get(metric)
        if not fn:
            return Response({'error': 'unknown metric'}, status=400)

        rows = list(fn(since))
        # Build dense series (fill gaps with 0)
        from collections import defaultdict
        by_day = defaultdict(int, {str(r['day']): r['count'] for r in rows})
        series = []
        for i in range(days):
            day = (since + timedelta(days=i + 1)).date()
            series.append({'day': day.isoformat(), 'value': by_day[day.isoformat()]})

        return Response({'metric': metric, 'series': series})


class ActivityFeedView(APIView):
    """
    GET /api/analytics/activity-feed/
    Last 15 activities across the system — powers the ticker.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = []

        # recent exam submissions
        for a in ExamAttempt.objects.select_related(
            'student__user', 'exam'
        ).filter(submitted_at__gte=timezone.now() - timedelta(hours=6)
        ).order_by('-submitted_at')[:5]:
            items.append({
                'type': 'exam_submitted',
                'text': f"{a.student.user.full_name} submitted “{a.exam.title}”",
                'time': a.submitted_at.isoformat(),
                'icon': '📝',
            })
   
        # recent enrollments

        for e in Enrollment.objects.select_related(
            'student__user', 'course'
        ).filter(enrollment_date__gte=timezone.now() - timedelta(days=2)
        ).order_by('-enrollment_date')[:5]:
            items.append({
                'type': 'enrollment',
                'text': f"{e.student.user.full_name} enrolled in “{e.course.title}”",
                'time': e.enrollment_date.isoformat(),
                'icon': '🎓',
            })

        # recent payments
        for p in PaymentProof.objects.select_related(
            'student__user'
        ).filter(uploaded_at__gte=timezone.now() - timedelta(days=2)
        ).order_by('-uploaded_at')[:5]:
            items.append({
                'type': 'payment',
                'text': f"{p.student.user.full_name} uploaded a payment proof",
                'time': p.uploaded_at.isoformat(),
                'icon': '💳',
            })

        # Sort all items by time (newest first) and limit to 15
        items.sort(key=lambda x: x['time'], reverse=True)
        return Response({'items': items[:15]})