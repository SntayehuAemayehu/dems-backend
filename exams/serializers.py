# exams/serializers.py
from rest_framework import serializers
from .models import Exam, Question, ExamAttempt, Answer


class QuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Question
        fields = '__all__'
        read_only_fields = ['exam']  # exam is read-only, set via URL


class ExamSerializer(serializers.ModelSerializer):
    questions = QuestionSerializer(many=True, read_only=True)
    course_title = serializers.SerializerMethodField()
    course_code = serializers.SerializerMethodField()
    attempt_count = serializers.SerializerMethodField()
    is_taken = serializers.SerializerMethodField()
    seb_available = serializers.SerializerMethodField()
    seb_file_url = serializers.SerializerMethodField()  # ✅ NEW

    class Meta:
        model = Exam
        fields = '__all__'
        read_only_fields = [
            'created_at',
            'seb_config_key',
            'seb_browser_exam_key',
            'seb_generated_at',
        ]
        extra_kwargs = {
            'seb_config_file': {'write_only': True, 'required': False},
        }

    def get_course_title(self, obj):
        return obj.course.title if obj.course else None

    def get_course_code(self, obj):
        return obj.course.course_code if obj.course else None

    def get_attempt_count(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and getattr(request.user, 'role', None) == 'STUDENT':
            try:
                student = request.user.student_profile
                return obj.attempts.filter(student=student).count()
            except Exception:
                return 0
        return obj.attempts.count()

    def get_is_taken(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and getattr(request.user, 'role', None) == 'STUDENT':
            try:
                student = request.user.student_profile
                return obj.attempts.filter(
                    student=student,
                    status__in=['IN_PROGRESS', 'SUBMITTED', 'GRADED']
                ).exists()
            except Exception:
                return False
        return False

    def get_seb_available(self, obj):
        try:
            return bool(obj.seb_enabled and obj.seb_config_file and obj.seb_config_file.name)
        except Exception:
            return False

    # ✅ NEW METHOD
    def get_seb_file_url(self, obj):
        try:
            if obj.seb_config_file and obj.seb_config_file.name:
                request = self.context.get('request')
                url = obj.seb_config_file.url
                if request is not None:
                    return request.build_absolute_uri(url)
                return url
        except Exception:
            pass
        return None


class ExamAttemptSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    exam_title = serializers.SerializerMethodField()
    course_title = serializers.SerializerMethodField()
    exam_type = serializers.CharField(source='exam.exam_type', read_only=True)
    course_id = serializers.IntegerField(source='exam.course_id', read_only=True)
    course_code = serializers.CharField(source='exam.course.course_code', read_only=True)
    student_id = serializers.SerializerMethodField()
    
    class Meta:
        model = ExamAttempt
        fields = '__all__'
        read_only_fields = ['start_time']
    
    def get_student_name(self, obj):
        return obj.student.user.full_name
    
    def get_student_id(self, obj):
        return obj.student.student_id
    
    def get_exam_title(self, obj):
        return obj.exam.title
    
    def get_course_title(self, obj):
        return obj.exam.course.title


class FinalExamSerializer(serializers.ModelSerializer):
    course_title = serializers.SerializerMethodField()
    course_code = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Exam
        fields = ['id', 'title', 'description', 'course', 'course_title', 'course_code',
                  'department_name', 'duration_minutes', 'start_time', 'end_time',
                  'total_marks', 'passing_mark', 'is_published', 'proctoring_enabled',
                  'created_by', 'created_by_name', 'created_at']
        read_only_fields = ['created_at']
    
    def get_course_title(self, obj):
        return obj.course.title if obj.course else None
    
    def get_course_code(self, obj):
        return obj.course.course_code if obj.course else None
    
    def get_department_name(self, obj):
        return obj.course.department.name if obj.course and obj.course.department else None
    
    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else None