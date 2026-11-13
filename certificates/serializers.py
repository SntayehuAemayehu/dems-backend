from rest_framework import serializers
from .models import Certificate
from utils.grading import calculate_grade, calculate_grade_from_mark


class CertificateSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_code = serializers.CharField(source='course.course_code', read_only=True)
    student_name = serializers.SerializerMethodField()
    student_id = serializers.CharField(source='student.student_id', read_only=True)
    department = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()
    semester = serializers.SerializerMethodField()
    gpa = serializers.SerializerMethodField()
    cgpa = serializers.SerializerMethodField()
    courses = serializers.SerializerMethodField()
    grade = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = (
            'id', 'certification_id', 'course_title', 'course_code',
            'student_name', 'student_id', 'department', 'year', 'semester', 'grade',
            'gpa', 'cgpa', 'courses', 'issued_at', 'download_url',
        )

    def _grade_calculation(self, enrollment):
        if enrollment.total_marks_obtained is not None and enrollment.total_marks_possible:
            return calculate_grade_from_mark(
                float(enrollment.total_marks_obtained),
                float(enrollment.total_marks_possible),
            )
        return calculate_grade(enrollment.percentage_score)

    def _student_enrollments(self, obj):
        enrollments = self.context.get('student_enrollments')
        if enrollments is None:
            enrollments = obj.student.enrollments.select_related('course').order_by(
                'course__year',
                'course__semester',
                'course__course_code',
            )
        return enrollments

    def _published_enrollment_ids(self, obj):
        enrollment_ids = self.context.get('published_enrollment_ids')
        if enrollment_ids is None:
            enrollment_ids = Certificate.objects.filter(
                student=obj.student,
                is_published=True,
            ).values_list('enrollment_id', flat=True)
        return set(enrollment_ids)

    def _released_completed_enrollments(self, obj):
        published_ids = self._published_enrollment_ids(obj)
        return [
            enrollment
            for enrollment in self._student_enrollments(obj)
            if enrollment.id in published_ids
            and enrollment.status == 'COMPLETED'
            and enrollment.result_sent_to_registrar
        ]

    def _weighted_gpa(self, enrollments):
        total_points = 0.0
        total_credits = 0
        for enrollment in enrollments:
            credit_hours = enrollment.course.credit_hours or 0
            if credit_hours <= 0:
                continue
            grade_points = self._grade_calculation(enrollment)['gpa']
            total_points += grade_points * credit_hours
            total_credits += credit_hours
        return round(total_points / total_credits, 2) if total_credits else None

    def _student_semester(self, obj):
        return obj.student.current_semester

    def get_year(self, obj):
        return obj.student.year or (
            (obj.student.current_semester + 1) // 2
            if obj.student.current_semester else 0
        )

    def get_department(self, obj):
        return obj.student.department or (
            obj.course.department.name if obj.course.department else ''
        )

    def get_semester(self, obj):
        return self._student_semester(obj)

    def get_grade(self, obj):
        return self._grade_calculation(obj.enrollment)['letter']

    def get_gpa(self, obj):
        current_semester = str(self._student_semester(obj))
        current_semester_enrollments = [
            enrollment
            for enrollment in self._released_completed_enrollments(obj)
            if str(enrollment.course.semester).strip() == current_semester
        ]
        return self._weighted_gpa(current_semester_enrollments)

    def get_cgpa(self, obj):
        return self._weighted_gpa(self._released_completed_enrollments(obj))

    def get_courses(self, obj):
        published_ids = self._published_enrollment_ids(obj)
        records = []
        for enrollment in self._student_enrollments(obj):
            is_released = (
                enrollment.id in published_ids
                and enrollment.status == 'COMPLETED'
                and enrollment.result_sent_to_registrar
            )
            calculation = self._grade_calculation(enrollment) if is_released else None
            records.append({
                'course_id': enrollment.course_id,
                'course_code': enrollment.course.course_code,
                'course_name': enrollment.course.title,
                'year': enrollment.course.year,
                'semester': enrollment.course.semester,
                'score': (
                    float(enrollment.total_marks_obtained)
                    if is_released and enrollment.total_marks_obtained is not None
                    else None
                ),
                'score_possible': (
                    float(enrollment.total_marks_possible)
                    if is_released and enrollment.total_marks_possible is not None
                    else None
                ),
                'grade': calculation['letter'] if calculation else 'Not issued',
                'gpa': calculation['gpa'] if calculation else None,
                'status': enrollment.status,
            })
        return records

    def get_student_name(self, obj):
        user = obj.student.user
        return getattr(user, 'full_name', None) or user.get_full_name() or user.username

    def get_download_url(self, obj):
        request = self.context.get('request')
        path = f"/api/certificates/{obj.certification_id}/download/"
        return request.build_absolute_uri(path) if request else path
