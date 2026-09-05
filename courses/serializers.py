# courses/serializers.py - COMPLETE FIXED VERSION

from rest_framework import serializers
from .models import Course, CourseMaterial, Enrollment, Assignment, AssignmentSubmission


class CourseMaterialSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()
    file_extension = serializers.SerializerMethodField()
    is_video = serializers.SerializerMethodField()
    video_embed_url = serializers.SerializerMethodField()
    
    class Meta:
        model = CourseMaterial
        fields = [
            'id', 'course', 'title', 'description', 'material_type', 
            'file', 'file_url', 'file_extension', 'is_video',
            'video_duration', 'uploaded_by', 'uploaded_by_name', 'uploaded_at',
            'video_embed_url'
        ]
        read_only_fields = ['uploaded_at']
    
    def get_uploaded_by_name(self, obj):
        return obj.uploaded_by.full_name if obj.uploaded_by else None
    
    def get_file_url(self, obj):
        if obj.file and hasattr(obj.file, 'url'):
            return obj.file.url
        return None
    
    def get_file_extension(self, obj):
        if obj.file:
            return obj.file.name.split('.')[-1].lower()
        return ''
    
    def get_is_video(self, obj):
        return obj.material_type == 'VIDEO'
    
    def get_video_embed_url(self, obj):
        if obj.is_video() and obj.file and hasattr(obj.file, 'url'):
            return obj.file.url
        return None


class CourseSerializer(serializers.ModelSerializer):
    instructor_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    enrolled_count = serializers.IntegerField(read_only=True)
    is_enrolled = serializers.SerializerMethodField()
    materials = CourseMaterialSerializer(many=True, read_only=True)
    assignments_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Course
        fields = [
            'id', 'course_code', 'title', 'description', 'credit_hours', 
            'semester', 'academic_year', 'capacity', 'instructor', 'instructor_name',
            'department', 'department_name', 'is_active', 'is_approved',
            'enrolled_count', 'is_enrolled', 'created_at', 'materials', 'assignments_count'
        ]
        read_only_fields = ['created_at', 'is_approved', 'approved_by']
    
    def get_instructor_name(self, obj):
        return obj.instructor.full_name if obj.instructor else None
    
    def get_department_name(self, obj):
        return obj.department.name if obj.department else None
    
    def get_is_enrolled(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated and request.user.role == 'STUDENT':
            try:
                student = request.user.student_profile
                return Enrollment.objects.filter(student=student, course=obj, status='ACTIVE').exists()
            except:
                return False
        return False
    
    def get_assignments_count(self, obj):
        return obj.assignments.count()


class EnrollmentSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    course_title = serializers.SerializerMethodField()
    course_code = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()
    
    class Meta:
        model = Enrollment
        fields = ['id', 'student', 'student_name', 'student_id', 'course', 'course_title', 
                  'course_code', 'enrollment_date', 'status', 'grade', 'grade_points']
    
    def get_student_name(self, obj):
        return obj.student.user.full_name
    
    def get_student_id(self, obj):
        return obj.student.student_id
    
    def get_course_title(self, obj):
        return obj.course.title
    
    def get_course_code(self, obj):
        return obj.course.course_code


class AssignmentSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField()
    course_title = serializers.SerializerMethodField()
    submission_count = serializers.SerializerMethodField()
    has_video = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Assignment
        fields = [
            'id', 'course', 'course_title', 'title', 'description', 
            'assignment_type', 'due_date', 'total_marks',
            'attachment', 'video_attachment', 'video_duration', 'link_url',
            'has_video', 'video_url', 'created_by', 'created_by_name', 
            'created_at', 'updated_at', 'submission_count'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def get_created_by_name(self, obj):
        return obj.created_by.full_name if obj.created_by else None
    
    def get_course_title(self, obj):
        return obj.course.title if obj.course else None
    
    def get_submission_count(self, obj):
        return obj.submissions.count()
    
    def get_has_video(self, obj):
        return bool(obj.video_attachment)
    
    def get_video_url(self, obj):
        if obj.video_attachment and hasattr(obj.video_attachment, 'url'):
            return obj.video_attachment.url
        return None


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    student_id = serializers.SerializerMethodField()
    assignment_title = serializers.SerializerMethodField()
    graded_by_name = serializers.SerializerMethodField()
    has_video = serializers.SerializerMethodField()
    video_url = serializers.SerializerMethodField()
    
    class Meta:
        model = AssignmentSubmission
        fields = [
            'id', 'assignment', 'assignment_title', 'student', 'student_name', 'student_id',
            'submission_type', 'submission_file', 'submission_video', 'submission_text',
            'submission_link', 'has_video', 'video_url', 'submitted_at', 
            'marks_obtained', 'feedback', 'graded_by', 'graded_by_name', 'graded_at'
        ]
        read_only_fields = ['submitted_at']
    
    def get_student_name(self, obj):
        return obj.student.user.full_name if obj.student else None
    
    def get_student_id(self, obj):
        return obj.student.student_id if obj.student else None
    
    def get_assignment_title(self, obj):
        return obj.assignment.title if obj.assignment else None
    
    def get_graded_by_name(self, obj):
        return obj.graded_by.full_name if obj.graded_by else None
    
    def get_has_video(self, obj):
        return bool(obj.submission_video)
    
    def get_video_url(self, obj):
        if obj.submission_video and hasattr(obj.submission_video, 'url'):
            return obj.submission_video.url
        return None