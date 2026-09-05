# accounts/serializers.py - COMPLETE FIXED VERSION WITH DEPARTMENT HEAD SERIALIZERS

from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, StudentProfile, TeacherProfile, Department, RegistrationConfig


# ============= USER SERIALIZER =============

class UserSerializer(serializers.ModelSerializer):
    student_profile = serializers.SerializerMethodField()
    teacher_profile = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'phone', 'role', 'profile_picture', 'is_active', 'date_joined', 'student_profile', 'teacher_profile']
        read_only_fields = ['id', 'email', 'role', 'date_joined', 'is_active']
    
    def get_student_profile(self, obj):
        try:
            return StudentProfileSerializer(obj.student_profile).data
        except:
            return None
    
    def get_teacher_profile(self, obj):
        try:
            return TeacherProfileSerializer(obj.teacher_profile).data
        except:
            return None


# ============= REGISTER SERIALIZER =============

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    confirm_password = serializers.CharField(write_only=True, required=True)
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES, default='STUDENT')
    department = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    registration_type = serializers.ChoiceField(choices=StudentProfile.REGISTRATION_TYPE_CHOICES, default='FRESH')
    
    class Meta:
        model = User
        fields = ['email', 'full_name', 'phone', 'password', 'confirm_password', 'role', 'department', 'registration_type']
    
    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({"password": "Password fields didn't match."})
        
        if attrs.get('role') == 'STUDENT':
            department_value = attrs.get('department', '')
            
            if not department_value:
                raise serializers.ValidationError({"department": "Department is required for students."})
            
            department = None
            
            try:
                dept_id = int(department_value)
                department = Department.objects.filter(id=dept_id).first()
                if department:
                    attrs['department'] = department.name
            except (ValueError, TypeError):
                pass
            
            if not department:
                department = Department.objects.filter(name__iexact=department_value).first()
                if department:
                    attrs['department'] = department.name
            
            if not department:
                available = Department.objects.values_list('name', flat=True)
                available_list = ', '.join(list(available))
                raise serializers.ValidationError({
                    "department": f"Department '{department_value}' does not exist. Available departments: {available_list}"
                })
        
        return attrs
    
    def create(self, validated_data):
        validated_data.pop('confirm_password')
        department_name = validated_data.pop('department', '')
        registration_type = validated_data.pop('registration_type', 'FRESH')
        role = validated_data.get('role', 'STUDENT')
        
        user = User.objects.create_user(**validated_data)
        
        if role == 'STUDENT':
            student = StudentProfile.objects.create(
                user=user,
                department=department_name,
                registration_type=registration_type,
                payment_status='PENDING'
            )
        
        elif role == 'TEACHER':
            TeacherProfile.objects.create(
                user=user,
                department=department_name,
                employee_id=f"TCH{user.id:06d}"
            )
        
        elif role == 'DEPT_HEAD':
            TeacherProfile.objects.create(
                user=user,
                department=department_name,
                employee_id=f"HOD{user.id:06d}"
            )
            if department_name:
                department = Department.objects.filter(name=department_name).first()
                if department:
                    department.head = user
                    department.save()
        
        elif role == 'FINANCE':
            TeacherProfile.objects.create(
                user=user,
                department='Finance Department',
                employee_id=f"FIN{user.id:06d}"
            )
        
        elif role == 'REGISTRAR':
            TeacherProfile.objects.create(
                user=user,
                department='Registrar Office',
                employee_id=f"REG{user.id:06d}"
            )
        
        elif role == 'ADMIN':
            TeacherProfile.objects.create(
                user=user,
                department='Administration',
                employee_id=f"ADM{user.id:06d}"
            )
        
        return user


# ============= LOGIN SERIALIZER =============

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    
    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')
        
        user = authenticate(request=self.context.get('request'), username=email, password=password)
        
        if not user:
            raise serializers.ValidationError("Invalid email or password")
        
        if not user.is_active:
            raise serializers.ValidationError("Account is disabled")
        
        attrs['user'] = user
        return attrs


# ============= STUDENT PROFILE SERIALIZER =============

class StudentProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    can_access_services = serializers.SerializerMethodField()
    can_upload_documents = serializers.SerializerMethodField()
    registration_period_open = serializers.SerializerMethodField()
    required_documents = serializers.SerializerMethodField()
    
    class Meta:
        model = StudentProfile
        fields = [
            'id', 'user', 'student_id', 'date_of_birth', 'gender', 'address',
            'enrollment_date', 'current_semester', 'department', 'program',
            'cgpa', 'total_credits', 'payment_status', 'documents_verified',
            'is_enrolled', 'grade_8_certificate', 'grade_12_certificate',
            'transcript', 'other_documents', 'documents_submitted',
            'documents_verified_at', 'registration_complete', 'registration_type',
            'registration_year', 'registration_semester', 'registration_deadline',
            'activated_at', 'activated_by', 'can_access_services', 
            'can_upload_documents', 'registration_period_open', 'required_documents'
        ]
    
    def get_can_access_services(self, obj):
        return obj.payment_status == 'VERIFIED' and obj.is_enrolled
    
    def get_can_upload_documents(self, obj):
        return obj.payment_status == 'VERIFIED' and not obj.is_enrolled
    
    def get_registration_period_open(self, obj):
        from django.utils import timezone
        try:
            config = RegistrationConfig.objects.filter(is_active=True).latest('created_at')
            today = timezone.now().date()
            return config.registration_start_date <= today <= config.registration_end_date
        except RegistrationConfig.DoesNotExist:
            return False
    
    def get_required_documents(self, obj):
        try:
            config = RegistrationConfig.objects.filter(is_active=True).latest('created_at')
            required = []
            if config.require_grade_8:
                required.append('grade_8_certificate')
            if config.require_grade_12:
                required.append('grade_12_certificate')
            if config.require_transcript:
                required.append('transcript')
            if config.require_other_documents:
                required.append('other_documents')
            return required
        except RegistrationConfig.DoesNotExist:
            return ['grade_8_certificate', 'grade_12_certificate', 'transcript']


# ============= TEACHER PROFILE SERIALIZER =============

class TeacherProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = TeacherProfile
        fields = ['id', 'user', 'employee_id', 'department', 'qualification', 'specialization', 'joining_date', 'is_verified']


# ============= DEPARTMENT SERIALIZER =============

class DepartmentSerializer(serializers.ModelSerializer):
    head_name = serializers.SerializerMethodField()
    student_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Department
        fields = ['id', 'name', 'code', 'description', 'head', 'head_name', 'established_year', 'student_count']
        extra_kwargs = {
            'head': {'required': False, 'allow_null': True},
            'description': {'required': False, 'allow_blank': True},
            'established_year': {'required': False, 'allow_null': True},
        }
    
    def get_head_name(self, obj):
        return obj.head.full_name if obj.head else None
    
    def get_student_count(self, obj):
        return StudentProfile.objects.filter(department=obj.name).count()


# ============= REGISTRATION CONFIG SERIALIZER =============

class RegistrationConfigSerializer(serializers.ModelSerializer):
    updated_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = RegistrationConfig
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
    
    def get_updated_by_name(self, obj):
        return obj.updated_by.full_name if obj.updated_by else None


# ============= DEPARTMENT HEAD SERIALIZERS =============

# accounts/serializers.py - REPLACE Lines 265-290 with:

class DeptHeadCourseSerializer(serializers.ModelSerializer):
    """Serializer for Department Head course list"""
    instructor_name = serializers.CharField(source='instructor.full_name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    enrolled_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        from courses.models import Course
        model = Course
        fields = ['id', 'course_code', 'title', 'description', 'credit_hours', 
                  'semester', 'capacity', 'instructor', 'instructor_name',
                  'department', 'department_name', 'is_active', 'is_approved',
                  'enrolled_count', 'created_at']
# accounts/serializers.py - UPDATE DeptHeadTeacherListSerializer

class DeptHeadTeacherListSerializer(serializers.ModelSerializer):
    """Serializer for Department Head teacher list"""
    full_name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    
    class Meta:
        model = TeacherProfile
        fields = ['id', 'full_name', 'email', 'department', 'employee_id', 'qualification', 'specialization', 'is_verified']
    
    def get_full_name(self, obj):
        return obj.user.full_name if obj.user else None
    
    def get_email(self, obj):
        return obj.user.email if obj.user else None

class DeptHeadStudentListSerializer(serializers.ModelSerializer):
    """Serializer for Department Head student list"""
    full_name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    
    class Meta:
        model = StudentProfile
        fields = ['id', 'full_name', 'email', 'student_id', 'department', 'payment_status', 
                  'documents_verified', 'is_enrolled', 'cgpa', 'enrollment_date']
    
    def get_full_name(self, obj):
        return obj.user.full_name if obj.user else None
    
    def get_email(self, obj):
        return obj.user.email if obj.user else None


# accounts/serializers.py - REPLACE Lines 293-316 with:

class DeptHeadFinalExamSerializer(serializers.ModelSerializer):
    """Serializer for Department Head final exam list"""
    course_title = serializers.CharField(source='course.title', read_only=True)
    course_code = serializers.CharField(source='course.course_code', read_only=True)
    department_name = serializers.CharField(source='course.department.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    
    class Meta:
        from exams.models import Exam
        model = Exam
        fields = ['id', 'title', 'description', 'course', 'course_title', 'course_code',
                  'department_name', 'duration_minutes', 'start_time', 'end_time',
                  'total_marks', 'passing_mark', 'is_published', 'proctoring_enabled',
                  'created_by', 'created_by_name', 'created_at']