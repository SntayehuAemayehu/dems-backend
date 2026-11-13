# dems-backend/certificates/serializers.py
from rest_framework import serializers
from .models import Certificate


class CertificateSerializer(serializers.ModelSerializer):
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_code = serializers.CharField(source='course.course_code', read_only=True)
    student_name = serializers.SerializerMethodField()
    student_id = serializers.CharField(source='student.student_id', read_only=True)
    download_url = serializers.SerializerMethodField()
    grade = serializers.SerializerMethodField()
    percentage = serializers.SerializerMethodField()
    credit_hours = serializers.IntegerField(source='course.credit_hours', read_only=True)
    department = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()

    class Meta:
        model = Certificate
        fields = (
            'id', 'certification_id', 'course_title', 'course_code',
            'student_name', 'student_id', 'grade', 'percentage', 'credit_hours',
            'department', 'year', 'issued_at', 'download_url',
        )

    def get_grade(self, obj):
        return obj.enrollment.grade_letter or 'NON'

    def get_percentage(self, obj):
        return float(obj.enrollment.percentage_score or 0)

    def get_department(self, obj):
        department = obj.course.department
        return department.name if department else ''

    def get_year(self, obj):
        student = obj.student
        return student.year or (
            (student.current_semester + 1) // 2 if student.current_semester else 0
        )

    def get_student_name(self, obj):
        user = obj.student.user
        return getattr(user, 'full_name', None) or user.get_full_name() or user.username

    def get_download_url(self, obj):
        request = self.context.get('request')
        path = f"/api/certificates/{obj.certification_id}/download/"
        return request.build_absolute_uri(path) if request else path