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
    
    class Meta:
        model = Exam
        fields = '__all__'
        read_only_fields = ['created_at']
    
    def get_course_title(self, obj):
        return obj.course.title
    
    def get_course_code(self, obj):
        return obj.course.course_code
    
    def get_attempt_count(self, obj):
        return obj.attempts.count()

class ExamAttemptSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    exam_title = serializers.SerializerMethodField()
    course_title = serializers.SerializerMethodField()
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

# exams/serializers.py - ADD THIS SERIALIZER

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