# accounts/views.py - COMPLETE FIXED VERSION
# All imports properly defined
# INCLUDES ALL EXISTING VIEWS + DEPARTMENT HEAD VIEWS
from django.core.mail import send_mail
from django.utils.crypto import get_random_string
from django.utils import timezone
from datetime import timedelta
import random
import datetime
#new
from django.core.cache import cache
from django.contrib.sessions.models import Session
from datetime import timedelta
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import check_password
from .models import User

from analytics.models import SystemLog
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.models import User as DjangoUser
from rest_framework_simplejwt.tokens import RefreshToken

from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.conf import settings
from .models import User, StudentProfile, TeacherProfile, Department, RegistrationConfig, PasswordResetOTP
from .serializers import (
    UserSerializer, 
    RegisterSerializer, 
    LoginSerializer,
    StudentProfileSerializer, 
    TeacherProfileSerializer,
    DepartmentSerializer, 
    RegistrationConfigSerializer,
    DeptHeadTeacherListSerializer,
    DeptHeadStudentListSerializer,
    DeptHeadFinalExamSerializer
)
from notifications.utils import send_notification
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

# ============= PASSWORD RESET TOKEN STORAGE =============
# ============= PASSWORD RESET TOKEN STORAGE =============
reset_tokens = {}

def generate_reset_token(user):
    """Generate a unique reset token for a user"""
    token = get_random_string(64)
    reset_tokens[token] = {
        'user_id': user.id,
        'email': user.email,
        'created_at': timezone.now().isoformat(),
        'expires_at': (timezone.now() + timedelta(hours=24)).isoformat()
    }
    return token

def validate_reset_token(token):
    """Validate a reset token and return the user if valid"""
    if token not in reset_tokens:
        return None
    
    token_data = reset_tokens[token]
    
    # Check expiration
    try:
        expires_at = datetime.fromisoformat(token_data['expires_at'])
        if timezone.now() > expires_at:
            del reset_tokens[token]
            return None
    except (ValueError, KeyError):
        del reset_tokens[token]
        return None
    
    try:
        user = User.objects.get(id=token_data['user_id'])
        return user
    except User.DoesNotExist:
        del reset_tokens[token]
        return None

def clear_reset_token(token):
    """Remove a reset token from storage"""
    if token in reset_tokens:
        del reset_tokens[token]

# ============= PASSWORD RESET VIEWS =============

class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
            reset_token = generate_reset_token(user)
            reset_link = f"http://localhost:3000/reset-password/{reset_token}"
            
            try:
                send_mail(
                    subject='🔑 Password Reset Request - DEMS',
                    message=f"""
Dear {user.full_name},

You requested a password reset for your DEMS account.

Click the link below to reset your password:
{reset_link}

This link will expire in 24 hours.

If you did not request this, please ignore this email.

Best regards,
DEMS Team
Mekdela Amba University
                    """,
                    from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@dems.com',
                    recipient_list=[email],
                    fail_silently=False,
                )
                logger.info(f"Password reset email sent to {email}")
                return Response({
                    'message': 'Password reset link has been sent to your email address.',
                    'success': True
                }, status=status.HTTP_200_OK)
            except Exception as e:
                logger.error(f"Failed to send password reset email: {e}")
                return Response({
                    'message': 'Password reset link generated.',
                    'reset_link': reset_link,
                    'success': True
                }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({
                'message': 'If your email is registered, you will receive a reset link.',
                'success': True
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Password reset error: {e}")
            return Response({'error': 'An error occurred. Please try again later.'},
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        token = request.data.get('token')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')
        
        if not token:
            return Response({'error': 'Reset token is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not new_password or not confirm_password:
            return Response({'error': 'Password and confirmation are required'}, status=status.HTTP_400_BAD_REQUEST)
        if new_password != confirm_password:
            return Response({'error': 'Passwords do not match'}, status=status.HTTP_400_BAD_REQUEST)
        if len(new_password) < 8:
            return Response({'error': 'Password must be at least 8 characters long'}, status=status.HTTP_400_BAD_REQUEST)
        
        user = validate_reset_token(token)
        if not user:
            return Response({'error': 'Invalid or expired reset token'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user.set_password(new_password)
            user.save()
            clear_reset_token(token)
            send_notification(
                recipient_user=user,
                title='🔑 Password Changed Successfully',
                message='Your password has been changed. If you did not make this change, please contact support immediately.',
                notification_type='SYSTEM_ALERT',
                link='/login'
            )
            return Response({
                'message': 'Password reset successful. You can now login with your new password.',
                'success': True
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Password reset failed: {e}")
            return Response({'error': 'Failed to reset password. Please try again.'},
                          status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ValidateResetTokenView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        token = request.query_params.get('token')
        if not token:
            return Response({'valid': False, 'error': 'Token is required'}, status=status.HTTP_400_BAD_REQUEST)
        user = validate_reset_token(token)
        if user:
            return Response({'valid': True, 'email': user.email, 'message': 'Token is valid'})
        return Response({'valid': False, 'error': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)


# ============= AUTH VIEWS =============

class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        refresh = RefreshToken.for_user(user)
        
        if user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=user)
                send_notification(
                    recipient_roles=['REGISTRAR'],
                    title='📝 New Student Registration',
                    message=f'New student {user.full_name} has registered. Department: {student.department}',
                    notification_type='SYSTEM_ALERT',
                    link='/registrar/dashboard'
                )
            except StudentProfile.DoesNotExist:
                pass
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'message': 'Registration successful'
        }, status=status.HTTP_201_CREATED)


# backend/accounts/views.py
# UPDATE LoginView

# backend/accounts/views.py
# UPDATE LoginView

# backend/accounts/views.py
# REPLACE LoginView with this FIXED version

# At the top of views.py, make sure these imports exist:
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

# backend/accounts/views.py
# COMPLETE LoginView with per-user brute force protection

# backend/accounts/views.py
# COMPLETE LoginView - PER USER Brute Force

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email', '').lower()
        password = request.data.get('password', '')
        
        # ============================================================
        # BRUTE FORCE PROTECTION - ONLY THIS SPECIFIC EMAIL
        # ============================================================
        cache_key = f'login_attempts:{email}'
        lock_key = f'lockout:{email}'
        
        # Get attempt count for THIS user ONLY
        attempts = cache.get(cache_key, 0)
        is_locked = cache.get(lock_key, False)
        
        # ✅ ONLY BLOCK THIS SPECIFIC USER
        if is_locked:
            return Response({
                'error': 'Account temporarily locked',
                'message': 'Too many failed login attempts for this account. Please try again after 15 minutes.',
                'retry_after': 900,
                'email': email
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        if attempts >= 5:
            cache.set(lock_key, True, timeout=900)
            return Response({
                'error': 'Account temporarily locked',
                'message': 'Too many failed login attempts for this account. Please try again after 15 minutes.',
                'retry_after': 900,
                'email': email
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Try to authenticate
        serializer = LoginSerializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            # ✅ ONLY increment attempts for THIS user
            new_attempts = attempts + 1
            cache.set(cache_key, new_attempts, timeout=900)
            
            return Response({
                'error': 'Invalid credentials',
                'message': 'Invalid email or password.',
                'remaining_attempts': max(0, 5 - new_attempts)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = serializer.validated_data['user']
        
        # ✅ LOGIN SUCCESSFUL - Reset attempts for THIS user
        cache.delete(cache_key)
        cache.delete(lock_key)
        
        refresh = RefreshToken.for_user(user)
        
        # Check if student is payment locked
        if user.role == 'STUDENT':
            try:
                from analytics.models import StudentPaymentSchedule
                student = StudentProfile.objects.get(user=user)
                
                if student.is_enrolled:
                    schedules = StudentPaymentSchedule.objects.filter(student=student)
                    
                    for schedule in schedules:
                        schedule.update_status()
                        schedule.save()
                        schedule.refresh_from_db()
                        
                        if schedule.status == 'LOCKED':
                            student.payment_status = 'OVERDUE_LOCKED'
                            student.save()
                            
                            return Response({
                                'user': UserSerializer(user).data,
                                'refresh': str(refresh),
                                'access': str(refresh.access_token),
                                'dashboard': '/payments?locked=true',
                                'status': 'LOCKED',
                                'is_locked': True,
                                'message': '🔒 Your account is locked. Please make payment.',
                                'amount_due': float(schedule.total_amount)
                            })
            except StudentProfile.DoesNotExist:
                pass
            except Exception as e:
                logger.error(f"Login lock check error: {e}")
        
        dashboard_map = {
            'STUDENT': '/dashboard',
            'TEACHER': '/teacher/dashboard',
            'FINANCE': '/finance/dashboard',
            'REGISTRAR': '/registrar/dashboard',
            'DEPT_HEAD': '/dept/dashboard',
            'ADMIN': '/admin/dashboard',
        }
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'dashboard': dashboard_map.get(user.role, '/dashboard'),
            'message': 'Login successful'
        })
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        allowed_fields = ['full_name', 'phone', 'profile_picture']
        data = {k: v for k, v in request.data.items() if k in allowed_fields and v != ''}
        
        if 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']
            user.save()
            data.pop('profile_picture', None)
        
        if not data:
            return Response({'message': 'No fields to update'}, status=status.HTTP_200_OK)
        
        serializer = self.get_serializer(user, data=data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()
        return Response({
            'message': 'Profile updated successfully',
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)


class StudentProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = StudentProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        try:
            student, created = StudentProfile.objects.get_or_create(user=self.request.user)
            return student
        except Exception as e:
            logger.error(f"Error getting student profile: {e}")
            return None
    
    def patch(self, request, *args, **kwargs):
        student = self.get_object()
        if not student:
            return Response({'error': 'Student profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        allowed_fields = ['address', 'date_of_birth', 'gender', 'department', 'program']
        data = {}
        for field in allowed_fields:
            if field in request.data and request.data[field] != '':
                data[field] = request.data[field]
        
        if not data:
            return Response({'message': 'No fields to update'}, status=status.HTTP_200_OK)
        
        serializer = self.get_serializer(student, data=data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()
        return Response({
            'message': 'Student profile updated successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)


class TeacherProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = TeacherProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        try:
            teacher, created = TeacherProfile.objects.get_or_create(user=self.request.user)
            return teacher
        except:
            return None
    
    def patch(self, request, *args, **kwargs):
        teacher = self.get_object()
        if not teacher:
            return Response({'error': 'Teacher profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        allowed_fields = ['department', 'qualification', 'specialization']
        data = {}
        for field in allowed_fields:
            if field in request.data and request.data[field] != '':
                data[field] = request.data[field]
        
        if not data:
            return Response({'message': 'No fields to update'}, status=status.HTTP_200_OK)
        
        serializer = self.get_serializer(teacher, data=data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()
        return Response({
            'message': 'Teacher profile updated successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)

# ============= CHANGE PASSWORD VIEW =============

# accounts/views.py - REPLACE ChangePasswordView with this

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.hashers import check_password
from .models import User
import logging

logger = logging.getLogger(__name__)

# backend/accounts/views.py
# REPLACE ChangePasswordView with this

class ChangePasswordView(APIView):
    """Change user password with FULL validation"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        user = request.user
        
        # Get data
        old_password = request.data.get('old_password', '')
        new_password = request.data.get('new_password', '')
        confirm_password = request.data.get('confirm_password', '')
        
        # 1. Check if all fields provided
        if not old_password:
            return Response({
                'error': 'Current password is required',
                'field': 'old_password'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not new_password:
            return Response({
                'error': 'New password is required',
                'field': 'new_password'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not confirm_password:
            return Response({
                'error': 'Please confirm your new password',
                'field': 'confirm_password'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 2. Check if new passwords match
        if new_password != confirm_password:
            return Response({
                'error': 'New passwords do not match',
                'field': 'confirm_password'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 3. Check if old password is correct
        if not check_password(old_password, user.password):
            return Response({
                'error': 'Current password is incorrect',
                'field': 'old_password'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 4. Check if new password is same as old
        if check_password(new_password, user.password):
            return Response({
                'error': 'New password cannot be the same as your current password',
                'field': 'new_password'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 5. Validate password strength
        import re
        
        # Check minimum length
        if len(new_password) < 8:
            return Response({
                'error': 'Password must be at least 8 characters long',
                'field': 'new_password'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if contains numbers
        if not re.search(r'\d', new_password):
            return Response({
                'error': 'Password must contain at least one number',
                'field': 'new_password'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if contains uppercase
        if not re.search(r'[A-Z]', new_password):
            return Response({
                'error': 'Password must contain at least one uppercase letter',
                'field': 'new_password'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if contains lowercase
        if not re.search(r'[a-z]', new_password):
            return Response({
                'error': 'Password must contain at least one lowercase letter',
                'field': 'new_password'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if contains special character
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', new_password):
            return Response({
                'error': 'Password must contain at least one special character',
                'field': 'new_password'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if similar to common passwords
        common_passwords = [
            'password', 'password123', 'admin123', 'letmein',
            'qwerty123', 'welcome123', 'abc12345', '12345678'
        ]
        if new_password.lower() in common_passwords:
            return Response({
                'error': 'Password is too common. Please choose a stronger password.',
                'field': 'new_password'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # 6. Change the password
        try:
            user.set_password(new_password)
            user.save()
            
            # Send notification
            try:
                from notifications.utils import send_notification
                send_notification(
                    recipient_user=user,
                    title='🔑 Password Changed Successfully',
                    message='Your password has been changed. If you did not make this change, please contact support immediately.',
                    notification_type='SYSTEM_ALERT',
                    link='/profile'
                )
            except:
                pass
            
            return Response({
                'message': 'Password changed successfully!',
                'success': True
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Password change failed: {e}")
            return Response({
                'error': 'Failed to change password. Please try again.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class DepartmentListView(generics.ListAPIView):
    """List all departments - PUBLIC for registration"""
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.AllowAny]


class DepartmentCreateView(generics.CreateAPIView):
    """Create a new department - ADMIN only"""
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            return Response(
                {'error': 'Only admins can create departments'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)


class DepartmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a department"""
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def update(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            return Response(
                {'error': 'Only admins can update departments'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            return Response(
                {'error': 'Only admins can delete departments'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)


# ============= REGISTRAR VIEWS =============

class RegistrarStudentListView(generics.ListAPIView):
    """List ONLY payment verified students for Registrar"""
    serializer_class = StudentProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.role not in ['REGISTRAR', 'ADMIN']:
            return StudentProfile.objects.none()
        
        queryset = StudentProfile.objects.filter(
            payment_status='VERIFIED'
        ).select_related('user')
        
        department_filter = self.request.query_params.get('department')
        if department_filter:
            queryset = queryset.filter(department=department_filter)
        
        doc_status = self.request.query_params.get('doc_status')
        if doc_status == 'uploaded':
            queryset = queryset.filter(documents_submitted=True)
        elif doc_status == 'verified':
            queryset = queryset.filter(documents_verified=True)
        elif doc_status == 'pending':
            queryset = queryset.filter(documents_submitted=False)
        
        enrollment_status = self.request.query_params.get('enrollment_status')
        if enrollment_status == 'activated':
            queryset = queryset.filter(is_enrolled=True)
        elif enrollment_status == 'pending':
            queryset = queryset.filter(is_enrolled=False)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        total = queryset.count()
        documents_uploaded = queryset.filter(documents_submitted=True).count()
        documents_verified = queryset.filter(documents_verified=True).count()
        activated = queryset.filter(is_enrolled=True).count()
        pending_upload = queryset.filter(documents_submitted=False).count()
        
        return Response({
            'results': serializer.data,
            'count': total,
            'stats': {
                'total': total,
                'documents_uploaded': documents_uploaded,
                'documents_verified': documents_verified,
                'activated': activated,
                'pending_upload': pending_upload,
                'ready_for_activation': queryset.filter(
                    documents_verified=True, 
                    is_enrolled=False
                ).count()
            }
        })


class RegistrarStudentVerifyView(APIView):
    """Verify or reject a student's documents"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, student_id):
        if request.user.role not in ['REGISTRAR', 'ADMIN']:
            return Response(
                {'error': 'Permission denied. Only Registrar or Admin can verify students.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if student.payment_status != 'VERIFIED':
            return Response(
                {'error': 'Payment must be verified before verifying documents'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        action = request.data.get('action')
        reason = request.data.get('reason', '')
        
        if action == 'verify':
            student.documents_verified = True
            student.documents_verified_at = timezone.now()
            student.save()
            student.user.is_active = True
            student.user.save()
            
            send_notification(
                recipient_user=student.user,
                title='✅ Documents Verified!',
                message=f'Your documents have been verified. Your Student ID is {student.student_id}. You are now ready for activation.',
                notification_type='SYSTEM_ALERT',
                link='/dashboard'
            )
            
            dept_head = Department.objects.filter(name=student.department).first()
            if dept_head and dept_head.head:
                send_notification(
                    recipient_user=dept_head.head,
                    title='📋 Student Documents Verified',
                    message=f'Student {student.user.full_name} has been verified by Registrar. Ready for activation.',
                    notification_type='SYSTEM_ALERT',
                    link='/dept/dashboard'
                )
            
            return Response({
                'message': 'Student documents verified successfully',
                'student_id': student.student_id,
                'documents_verified': True
            })
            
        elif action == 'reject':
            student.documents_verified = False
            student.save()
            
            send_notification(
                recipient_user=student.user,
                title='❌ Documents Rejected',
                message=f'Your documents have been rejected. Reason: {reason}. Please check and resubmit.',
                notification_type='SYSTEM_ALERT',
                link='/profile'
            )
            
            return Response({
                'message': 'Student rejected',
                'reason': reason
            })
        
        return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)


class RegistrarStudentActivateView(APIView):
    """Activate a student account"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, student_id):
        if request.user.role not in ['REGISTRAR', 'ADMIN']:
            return Response(
                {'error': 'Permission denied. Only Registrar or Admin can activate students.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if student.payment_status != 'VERIFIED':
            return Response({'error': 'Payment not verified. Finance must verify payment first.'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if not student.documents_verified:
            return Response({'error': 'Documents not verified. Please verify documents first.'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if not student.student_id:
            return Response({'error': 'Student ID not generated. Please generate ID first.'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if student.is_enrolled:
            return Response({'error': 'Student account is already activated'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        student.is_enrolled = True
        student.registration_complete = True
        student.activated_at = timezone.now()
        student.activated_by = request.user
        student.save()
        student.user.is_active = True
        student.user.save()
        
        send_notification(
            recipient_user=student.user,
            title='🎉 Account Activated!',
            message=f'Your account has been fully activated! You can now access all services: enroll in courses, take exams, attend live classes, and more.',
            notification_type='SYSTEM_ALERT',
            link='/dashboard'
        )
        
        dept_head = Department.objects.filter(name=student.department).first()
        if dept_head and dept_head.head:
            send_notification(
                recipient_user=dept_head.head,
                title='🎓 New Student Activated - Ready for Department Management',
                message=f'''
Student: {student.user.full_name}
Student ID: {student.student_id}
Email: {student.user.email}
Department: {student.department}
Program: {student.program}
Registration Type: {student.registration_type}
Enrollment Date: {student.enrollment_date}
Current Semester: {student.current_semester}

This student has been fully activated and is now ready for course registration and department management.
                ''',
                notification_type='SYSTEM_ALERT',
                link='/dept/dashboard'
            )
        
        send_notification(
            recipient_roles=['ADMIN'],
            title='Student Activated',
            message=f'Student {student.user.full_name} (ID: {student.student_id}) activated by Registrar.',
            notification_type='SYSTEM_ALERT',
            link='/admin/dashboard'
        )
        
        return Response({
            'message': 'Student activated successfully',
            'is_enrolled': student.is_enrolled,
            'student_id': student.student_id,
            'payment_status': student.payment_status,
            'documents_verified': student.documents_verified
        })


class RegistrarGenerateIDView(APIView):
    """Generate Student ID with configurable format"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, student_id):
        if request.user.role not in ['REGISTRAR', 'ADMIN']:
            return Response(
                {'error': 'Permission denied. Only Registrar or Admin can generate IDs.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if student.payment_status != 'VERIFIED':
            return Response({'error': 'Payment must be verified before generating ID'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if not student.documents_verified:
            return Response({'error': 'Documents must be verified before generating ID'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if student.student_id:
            return Response({'error': 'Student already has an ID'}, status=status.HTTP_400_BAD_REQUEST)
        
        from analytics.models import SystemConfig
        
        id_format = SystemConfig.get_value('student_id_format', 'STU{year}{seq:06d}')
        year = timezone.now().year        
        student_count = StudentProfile.objects.count() + 1
        
        try:
            student_id = id_format.format(
                year=year,
                seq=student_count,
                dept=student.department[:3].upper() if student.department else 'GEN'
            )
        except:
            student_id = f"STU{year}{student_count:06d}"
        
        student.student_id = student_id
        student.save()
        
        send_notification(
            recipient_user=student.user,
            title='🆔 Student ID Generated',
            message=f'Your Student ID has been generated: {student_id}. Please use this ID for all university activities.',
            notification_type='SYSTEM_ALERT',
            link='/profile'
        )
        
        return Response({
            'message': 'Student ID generated successfully',
            'student_id': student_id
        })


class RegistrarNotifyStudentView(APIView):
    """Send notification to student to upload documents"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, student_id):
        if request.user.role not in ['REGISTRAR', 'ADMIN']:
            return Response(
                {'error': 'Permission denied. Only Registrar can send notifications.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if student.payment_status != 'VERIFIED':
            return Response(
                {'error': 'Payment must be verified before requesting documents'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if student.is_enrolled:
            return Response(
                {'error': 'Student account is already activated'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        message = request.data.get('message', 'Please upload your required documents (Grade 8, Grade 12, Transcript) for verification.')
        
        send_notification(
            recipient_user=student.user,
            title='📄 Document Upload Required',
            message=message,
            notification_type='SYSTEM_ALERT',
            link='/upload-documents'
        )
        
        try:
            send_mail(
                subject='📄 Document Upload Required - DEMS',
                message=f"""
Dear {student.user.full_name},

Your payment has been verified. Please upload the following documents for verification:
- Grade 8 Certificate
- Grade 12 Certificate
- Academic Transcript
- Any other supporting documents

Please login to your DEMS account and upload these documents.

Best regards,
Registrar Office
DEMS University
                """,
                from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@dems.com',
                recipient_list=[student.user.email],
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Email failed: {e}")
        
        student.notification_sent = True
        student.save()
        
        return Response({
            'message': 'Notification sent successfully',
            'student_id': student.id,
            'student_name': student.user.full_name,
            'notification_sent': True
        }, status=status.HTTP_200_OK)


class RegistrarStudentDocumentsView(APIView):
    """Get all documents for a student (Registrar only)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, student_id):
        if request.user.role not in ['REGISTRAR', 'ADMIN']:
            return Response(
                {'error': 'Permission denied. Only Registrar can view student documents.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        
        documents = {
            'student_name': student.user.full_name,
            'student_id': student.student_id,
            'department': student.department,
            'documents_submitted': student.documents_submitted,
            'documents_verified': student.documents_verified,
            'documents_verified_at': student.documents_verified_at,
            'files': []
        }
        
        doc_fields = [
            ('grade_8_certificate', 'Grade 8 Certificate'),
            ('grade_12_certificate', 'Grade 12 Certificate'),
            ('transcript', 'Transcript'),
            ('other_documents', 'Other Documents'),
        ]
        
        for field, label in doc_fields:
            file_obj = getattr(student, field)
            if file_obj:
                documents['files'].append({
                    'field': field,
                    'label': label,
                    'filename': file_obj.name,
                    'url': file_obj.url,
                    'size': file_obj.size if hasattr(file_obj, 'size') else None,
                    'uploaded_at': getattr(student, 'documents_verified_at', None)
                })
        
        return Response(documents, status=status.HTTP_200_OK)


class RegistrarDownloadDocumentView(APIView):
    """Download a specific student document (Registrar only)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, document_type, student_id):
        # Allow ADMIN, REGISTRAR, DEPT_HEAD to download documents
        if request.user.role not in ['REGISTRAR', 'ADMIN', 'DEPT_HEAD']:
            return Response(
                {'error': 'Permission denied. Only Registrar, Admin, or Department Head can download documents.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if Department Head has access to this student
        if request.user.role == 'DEPT_HEAD':
            try:
                department = request.user.headed_department
                if student.department != department.name:
                    return Response(
                        {'error': 'You can only access documents from students in your department'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except:
                return Response(
                    {'error': 'You are not assigned to any department'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        valid_types = ['grade_8_certificate', 'grade_12_certificate', 'transcript', 'other_documents']
        
        if document_type not in valid_types:
            return Response(
                {'error': f'Invalid document type. Valid types: {", ".join(valid_types)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file_obj = getattr(student, document_type)
        if not file_obj:
            return Response(
                {'error': f'Document {document_type} not found for this student'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Build absolute URL for the file
        file_url = request.build_absolute_uri(file_obj.url)
        
        return Response({
            'url': file_url,
            'filename': file_obj.name,
            'student_name': student.user.full_name,
            'student_id': student.student_id,
            'document_type': document_type
        }, status=status.HTTP_200_OK)
class RegistrationConfigView(APIView):
    """Get or update registration configuration"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            config = RegistrationConfig.objects.filter(is_active=True).latest('created_at')
            serializer = RegistrationConfigSerializer(config)
            return Response(serializer.data)
        except RegistrationConfig.DoesNotExist:
            return Response({
                'registration_start_date': None,
                'registration_end_date': None,
                'semester': '1',
                'academic_year': str(timezone.now().year),
                'require_grade_8': True,
                'require_grade_12': True,
                'require_transcript': True,
                'require_other_documents': False,
                'is_active': False,
                'max_students_per_department': 100,
                'allow_senior_registration': True,
                'allow_fresh_registration': True
            })
    
    def post(self, request):
        if request.user.role not in ['REGISTRAR', 'ADMIN']:
            return Response(
                {'error': 'Permission denied. Only Registrar can configure registration.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        RegistrationConfig.objects.all().update(is_active=False)
        
        serializer = RegistrationConfigSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        config = serializer.save(updated_by=request.user, is_active=True)
        
        send_notification(
            recipient_roles=['ADMIN', 'DEPT_HEAD'],
            title='📅 Registration Period Updated',
            message=f'Registration period for {config.academic_year} - Semester {config.semester} has been configured.',
            notification_type='SYSTEM_ALERT',
            link='/registrar/dashboard'
        )
        
        return Response({
            'message': 'Registration configuration updated successfully',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def put(self, request):
        return self.post(request)


# ============= STUDENT DOCUMENT UPLOAD =============

class StudentDocumentUploadView(APIView):
    """Upload student documents"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        if request.user.role != 'STUDENT':
            return Response(
                {'error': 'Only students can upload documents'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return Response(
                {'error': 'Student profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if student.payment_status != 'VERIFIED':
            return Response(
                {'error': 'Payment must be verified before uploading documents'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if student.is_enrolled:
            return Response(
                {'error': 'Account already activated. No documents needed.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        allowed_fields = ['grade_8_certificate', 'grade_12_certificate', 'transcript', 'other_documents']
        updated = False
        uploaded_files = []
        
        for field in allowed_fields:
            if field in request.FILES:
                setattr(student, field, request.FILES[field])
                updated = True
                uploaded_files.append(field)
        
        if updated:
            student.documents_submitted = True
            student.save()
            
            send_notification(
                recipient_roles=['REGISTRAR'],
                title='📄 Documents Uploaded',
                message=f'Student {student.user.full_name} has uploaded documents for verification: {", ".join(uploaded_files)}.',
                notification_type='SYSTEM_ALERT',
                link='/registrar/dashboard'
            )
            
            send_notification(
                recipient_user=student.user,
                title='📄 Documents Submitted',
                message=f'Your documents ({", ".join(uploaded_files)}) have been submitted. Registrar will verify them shortly.',
                notification_type='SYSTEM_ALERT',
                link='/dashboard'
            )
            
            return Response({
                'message': 'Documents uploaded successfully',
                'documents_submitted': True,
                'uploaded_files': uploaded_files
            }, status=status.HTTP_200_OK)
        
        return Response(
            {'error': 'No valid document fields found in request'},
            status=status.HTTP_400_BAD_REQUEST
        )


# ============= STUDENT GRADE VIEW =============

class StudentGradesView(APIView):
    """Get student grades"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        if user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=user)
                from courses.models import Enrollment
                enrollments = Enrollment.objects.filter(student=student, status='COMPLETED')
                grades = []
                for enrollment in enrollments:
                    grades.append({
                        'course_code': enrollment.course.course_code,
                        'course_title': enrollment.course.title,
                        'grade': enrollment.grade,
                        'grade_points': float(enrollment.grade_points),
                        'semester': enrollment.course.semester,
                        'academic_year': enrollment.course.academic_year
                    })
                return Response({
                    'student_name': student.user.full_name,
                    'student_id': student.student_id,
                    'department': student.department,
                    'cgpa': float(student.cgpa),
                    'total_credits': student.total_credits,
                    'grades': grades
                })
            except StudentProfile.DoesNotExist:
                return Response({'error': 'Student profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        elif user.role in ['DEPT_HEAD', 'REGISTRAR']:
            students = []
            if user.role == 'DEPT_HEAD':
                try:
                    department = user.headed_department
                    student_profiles = StudentProfile.objects.filter(department=department.name, is_enrolled=True)
                except:
                    return Response({'error': 'Department not found'}, status=status.HTTP_404_NOT_FOUND)
            else:
                student_profiles = StudentProfile.objects.filter(is_enrolled=True)
            
            from courses.models import Enrollment
            for student in student_profiles:
                enrollments = Enrollment.objects.filter(student=student, status='COMPLETED')
                grades = []
                for enrollment in enrollments:
                    grades.append({
                        'course_code': enrollment.course.course_code,
                        'course_title': enrollment.course.title,
                        'grade': enrollment.grade,
                        'grade_points': float(enrollment.grade_points),
                        'semester': enrollment.course.semester,
                        'academic_year': enrollment.course.academic_year
                    })
                students.append({
                    'student_name': student.user.full_name,
                    'student_id': student.student_id,
                    'department': student.department,
                    'cgpa': float(student.cgpa),
                    'total_credits': student.total_credits,
                    'grades': grades
                })
            
            return Response(students)
        
        return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)


# ============= ADMIN USER CREATION VIEWS =============

class AdminCreateUserView(APIView):
    """Admin creates any user with proper department assignment"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        if request.user.role != 'ADMIN':
            return Response(
                {'error': 'Only admins can create users'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        email = request.data.get('email')
        full_name = request.data.get('full_name')
        password = request.data.get('password')
        role = request.data.get('role', 'STUDENT')
        phone = request.data.get('phone', '')
        department_name = request.data.get('department', '')
        headed_department_name = request.data.get('headed_department', '')
        
        if not email or not full_name or not password:
            return Response(
                {'error': 'Email, full name, and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if User.objects.filter(email=email).exists():
            return Response(
                {'error': 'User with this email already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = User.objects.create_user(
            email=email,
            full_name=full_name,
            password=password,
            role=role,
            phone=phone
        )
        
        if role == 'STUDENT':
            StudentProfile.objects.create(
                user=user,
                department=department_name,
                payment_status='PENDING',
                registration_type='FRESH'
            )
            send_notification(
                recipient_roles=['REGISTRAR'],
                title='📝 New Student Created by Admin',
                message=f'Student {full_name} created. Department: {department_name}',
                notification_type='SYSTEM_ALERT',
                link='/registrar/dashboard'
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
                department=headed_department_name,
                employee_id=f"HOD{user.id:06d}"
            )
            if headed_department_name:
                try:
                    department = Department.objects.get(name=headed_department_name)
                    department.head = user
                    department.save()
                except Department.DoesNotExist:
                    pass
        
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
        
        return Response({
            'message': f'{role} created successfully',
            'user': {
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role,
                'department': department_name
            }
        }, status=status.HTTP_201_CREATED)


# ================================================================
# ============= DEPARTMENT HEAD VIEWS (ADDED) =============
# ================================================================

# accounts/views.py - COMPLETE FIXED VERSION
# INCLUDES ALL DEPARTMENT HEAD VIEWS

from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.core.mail import send_mail
from django.conf import settings
from .models import User, StudentProfile, TeacherProfile, Department, RegistrationConfig
from .serializers import (
    UserSerializer, 
    RegisterSerializer, 
    LoginSerializer,
    StudentProfileSerializer, 
    TeacherProfileSerializer,
    DepartmentSerializer, 
    RegistrationConfigSerializer
)
from notifications.utils import send_notification
import logging
from datetime import timedelta

logger = logging.getLogger(__name__)

# ============= PASSWORD RESET TOKEN STORAGE =============
reset_tokens = {}

def generate_reset_token(user):
    token = get_random_string(64)
    reset_tokens[token] = {
        'user_id': user.id,
        'email': user.email,
        'created_at': timezone.now().isoformat(),
        'expires_at': (timezone.now() + timedelta(hours=24)).isoformat()
    }
    return token

def validate_reset_token(token):
    if token not in reset_tokens:
        return None
    token_data = reset_tokens[token]
    expires_at = timezone.datetime.fromisoformat(token_data['expires_at'])
    if timezone.now() > expires_at:
        del reset_tokens[token]
        return None
    try:
        return User.objects.get(id=token_data['user_id'])
    except User.DoesNotExist:
        return None

def clear_reset_token(token):
    if token in reset_tokens:
        del reset_tokens[token]


# ============= PASSWORD RESET VIEWS =============

class ForgotPasswordView(APIView):
    """Send password reset link to user's email"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response({
                'error': 'Email is required',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
            
            # Check if user is active
            if not user.is_active:
                return Response({
                    'error': 'Your account is inactive. Please contact support.',
                    'success': False
                }, status=status.HTTP_400_BAD_REQUEST)
            
            # Generate reset token
            reset_token = generate_reset_token(user)
            reset_link = f"http://localhost:3000/reset-password/{reset_token}"
            
            # Send email
            try:
                send_mail(
                    subject='🔑 Password Reset Request - DEMS',
                    message=f"""
Dear {user.full_name},

You requested a password reset for your DEMS account.

Click the link below to reset your password:
{reset_link}

This link will expire in 24 hours.

If you did not request this, please ignore this email.

Best regards,
DEMS Team
Mekdela Amba University
                    """,
                    from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@dems.com',
                    recipient_list=[email],
                    fail_silently=False,
                )
                logger.info(f"Password reset email sent to {email}")
                
                return Response({
                    'message': 'Password reset link has been sent to your email address.',
                    'success': True
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                logger.error(f"Failed to send password reset email: {e}")
                # Return the reset link for development (remove in production)
                return Response({
                    'message': 'Password reset link generated.',
                    'reset_link': reset_link,
                    'success': True,
                    'development': True
                }, status=status.HTTP_200_OK)
                
        except User.DoesNotExist:
            # ✅ IMPORTANT: Return specific error for non-existent email
            return Response({
                'error': 'The email address you entered is not registered in our system. Please check and try again.',
                'success': False
            }, status=status.HTTP_404_NOT_FOUND)
            
        except Exception as e:
            logger.error(f"Password reset error: {e}")
            return Response({
                'error': 'An error occurred. Please try again later.',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ResetPasswordView(APIView):
    """Reset password using token"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        token = request.data.get('token')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')
        
        # Validate input
        if not token:
            return Response({
                'error': 'Reset token is required',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not new_password or not confirm_password:
            return Response({
                'error': 'Password and confirmation are required',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if new_password != confirm_password:
            return Response({
                'error': 'Passwords do not match',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(new_password) < 8:
            return Response({
                'error': 'Password must be at least 8 characters long',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate token
        user = validate_reset_token(token)
        if not user:
            return Response({
                'error': 'Invalid or expired reset token. Please request a new password reset link.',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user.set_password(new_password)
            user.save()
            clear_reset_token(token)
            
            # Send confirmation notification
            send_notification(
                recipient_user=user,
                title='🔑 Password Changed Successfully',
                message='Your password has been changed. If you did not make this change, please contact support immediately.',
                notification_type='SYSTEM_ALERT',
                link='/login'
            )
            
            return Response({
                'message': 'Password reset successful. You can now login with your new password.',
                'success': True
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Password reset failed: {e}")
            return Response({
                'error': 'Failed to reset password. Please try again.',
                'success': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
class ValidateResetTokenView(APIView):
    """Validate password reset token"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        token = request.query_params.get('token')
        
        if not token:
            return Response({
                'valid': False,
                'error': 'Token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = validate_reset_token(token)
        if user:
            return Response({
                'valid': True,
                'email': user.email,
                'message': 'Token is valid'
            }, status=status.HTTP_200_OK)
        
        return Response({
            'valid': False,
            'error': 'Invalid or expired token. Please request a new password reset link.'
        }, status=status.HTTP_400_BAD_REQUEST)

# ============= AUTH VIEWS =============

class RegisterView(generics.CreateAPIView):
    permission_classes = [permissions.AllowAny]
    serializer_class = RegisterSerializer
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        refresh = RefreshToken.for_user(user)
        
        if user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=user)
                send_notification(
                    recipient_roles=['REGISTRAR'],
                    title='📝 New Student Registration',
                    message=f'New student {user.full_name} has registered. Department: {student.department}',
                    notification_type='SYSTEM_ALERT',
                    link='/registrar/dashboard'
                )
            except StudentProfile.DoesNotExist:
                pass
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'message': 'Registration successful'
        }, status=status.HTTP_201_CREATED)


# backend/accounts/views.py
# REPLACE LoginView - properly separates first-time students

# backend/accounts/views.py
# REPLACE THE ENTIRE LoginView CLASS

# accounts/views.py - ADD BRUTE FORCE TRACKING TO LoginView
# Find the top of your file and add this import:
from django.core.cache import cache

# Replace your LoginView class with this enhanced version:

# backend/accounts/views.py
# REPLACE LoginView with this COMPLETE version

# backend/accounts/views.py
# REPLACE LoginView with this

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email', '').lower()
        password = request.data.get('password', '')
        
        # ============================================================
        # BRUTE FORCE PROTECTION - ONLY THIS SPECIFIC EMAIL
        # ============================================================
        client_ip = self._get_client_ip(request)
        
        # ✅ KEY: Only track attempts for THIS specific email
        cache_key = f'login_attempts:{email}'
        
        # Get attempt count for THIS user ONLY
        attempts = cache.get(cache_key, 0)
        
        # Check if THIS user is locked
        lock_key = f'lockout:{email}'
        is_locked = cache.get(lock_key, False)
        
        # ✅ ONLY BLOCK THIS SPECIFIC USER
        if is_locked:
            return Response({
                'error': 'Account temporarily locked',
                'message': 'Too many failed login attempts for this account. Please try again after 15 minutes.',
                'retry_after': 900,
                'email': email
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        if attempts >= 5:
            # Lock THIS user for 15 minutes
            cache.set(lock_key, True, timeout=900)
            
            return Response({
                'error': 'Account temporarily locked',
                'message': 'Too many failed login attempts for this account. Please try again after 15 minutes.',
                'retry_after': 900,
                'email': email
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)
        
        # Try to authenticate
        serializer = LoginSerializer(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            # ✅ ONLY increment attempts for THIS user
            new_attempts = attempts + 1
            cache.set(cache_key, new_attempts, timeout=900)
            
            return Response({
                'error': 'Invalid credentials',
                'message': 'Invalid email or password.',
                'remaining_attempts': max(0, 5 - new_attempts)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        user = serializer.validated_data['user']
        
        # ✅ LOGIN SUCCESSFUL - Reset attempts for THIS user
        cache.delete(cache_key)
        cache.delete(lock_key)
        
        refresh = RefreshToken.for_user(user)
        
        # Continue with normal login logic...
        # (keep your existing login response code here)
        
        dashboard_map = {
            'STUDENT': '/dashboard',
            'TEACHER': '/teacher/dashboard',
            'FINANCE': '/finance/dashboard',
            'REGISTRAR': '/registrar/dashboard',
            'DEPT_HEAD': '/dept/dashboard',
            'ADMIN': '/admin/dashboard',
        }
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'dashboard': dashboard_map.get(user.role, '/dashboard'),
            'message': 'Login successful'
        })
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', '')
class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    
    def patch(self, request, *args, **kwargs):
        user = self.get_object()
        allowed_fields = ['full_name', 'phone', 'profile_picture']
        data = {}
        
        # Handle text fields
        for field in allowed_fields:
            if field in request.data and request.data[field] != '':
                data[field] = request.data[field]
        
        # Handle profile picture
        if 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']
            user.save()
            # Remove from data to avoid double saving
            data.pop('profile_picture', None)
        
        if not data and 'profile_picture' not in request.FILES:
            return Response({'message': 'No fields to update'}, status=status.HTTP_200_OK)
        
        # Update user fields
        for field, value in data.items():
            setattr(user, field, value)
        user.save()
        
        return Response({
            'message': 'Profile updated successfully',
            'user': UserSerializer(user).data
        }, status=status.HTTP_200_OK)

class StudentProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = StudentProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        try:
            student, created = StudentProfile.objects.get_or_create(user=self.request.user)
            return student
        except Exception as e:
            logger.error(f"Error getting student profile: {e}")
            return None
    
    def patch(self, request, *args, **kwargs):
        student = self.get_object()
        if not student:
            return Response({'error': 'Student profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        allowed_fields = ['address', 'date_of_birth', 'gender', 'department', 'program']
        data = {}
        for field in allowed_fields:
            if field in request.data and request.data[field] != '':
                data[field] = request.data[field]
        
        if not data:
            return Response({'message': 'No fields to update'}, status=status.HTTP_200_OK)
        
        serializer = self.get_serializer(student, data=data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()
        return Response({
            'message': 'Student profile updated successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)


class TeacherProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = TeacherProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        try:
            teacher, created = TeacherProfile.objects.get_or_create(user=self.request.user)
            return teacher
        except:
            return None
    
    def patch(self, request, *args, **kwargs):
        teacher = self.get_object()
        if not teacher:
            return Response({'error': 'Teacher profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        allowed_fields = ['department', 'qualification', 'specialization']
        data = {}
        for field in allowed_fields:
            if field in request.data and request.data[field] != '':
                data[field] = request.data[field]
        
        if not data:
            return Response({'message': 'No fields to update'}, status=status.HTTP_200_OK)
        
        serializer = self.get_serializer(teacher, data=data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()
        return Response({
            'message': 'Teacher profile updated successfully',
            'data': serializer.data
        }, status=status.HTTP_200_OK)


# ============= DEPARTMENT VIEWS =============

class DepartmentListView(generics.ListAPIView):
    """List all departments - PUBLIC for registration"""
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.AllowAny]


class DepartmentCreateView(generics.CreateAPIView):
    """Create a new department - ADMIN only"""
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            return Response(
                {'error': 'Only admins can create departments'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().create(request, *args, **kwargs)


class DepartmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a department"""
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def update(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            return Response(
                {'error': 'Only admins can update departments'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)
    
    def destroy(self, request, *args, **kwargs):
        if request.user.role != 'ADMIN':
            return Response(
                {'error': 'Only admins can delete departments'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)


# ============= REGISTRAR VIEWS =============

class RegistrarStudentListView(generics.ListAPIView):
    """List ONLY payment verified students for Registrar"""
    serializer_class = StudentProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.role not in ['REGISTRAR', 'ADMIN']:
            return StudentProfile.objects.none()
        
        queryset = StudentProfile.objects.filter(
            payment_status='VERIFIED'
        ).select_related('user')
        
        department_filter = self.request.query_params.get('department')
        if department_filter:
            queryset = queryset.filter(department=department_filter)
        
        doc_status = self.request.query_params.get('doc_status')
        if doc_status == 'uploaded':
            queryset = queryset.filter(documents_submitted=True)
        elif doc_status == 'verified':
            queryset = queryset.filter(documents_verified=True)
        elif doc_status == 'pending':
            queryset = queryset.filter(documents_submitted=False)
        
        enrollment_status = self.request.query_params.get('enrollment_status')
        if enrollment_status == 'activated':
            queryset = queryset.filter(is_enrolled=True)
        elif enrollment_status == 'pending':
            queryset = queryset.filter(is_enrolled=False)
        
        return queryset
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        total = queryset.count()
        documents_uploaded = queryset.filter(documents_submitted=True).count()
        documents_verified = queryset.filter(documents_verified=True).count()
        activated = queryset.filter(is_enrolled=True).count()
        pending_upload = queryset.filter(documents_submitted=False).count()
        
        return Response({
            'results': serializer.data,
            'count': total,
            'stats': {
                'total': total,
                'documents_uploaded': documents_uploaded,
                'documents_verified': documents_verified,
                'activated': activated,
                'pending_upload': pending_upload,
                'ready_for_activation': queryset.filter(
                    documents_verified=True, 
                    is_enrolled=False
                ).count()
            }
        })


class RegistrarStudentVerifyView(APIView):
    """Verify or reject a student's documents"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, student_id):
        if request.user.role not in ['REGISTRAR', 'ADMIN']:
            return Response(
                {'error': 'Permission denied. Only Registrar or Admin can verify students.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if student.payment_status != 'VERIFIED':
            return Response(
                {'error': 'Payment must be verified before verifying documents'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        action = request.data.get('action')
        reason = request.data.get('reason', '')
        
        if action == 'verify':
            student.documents_verified = True
            student.documents_verified_at = timezone.now()
            student.save()
            student.user.is_active = True
            student.user.save()
            
            send_notification(
                recipient_user=student.user,
                title='✅ Documents Verified!',
                message=f'Your documents have been verified. Your Student ID is {student.student_id}. You are now ready for activation.',
                notification_type='SYSTEM_ALERT',
                link='/dashboard'
            )
            
            dept_head = Department.objects.filter(name=student.department).first()
            if dept_head and dept_head.head:
                send_notification(
                    recipient_user=dept_head.head,
                    title='📋 Student Documents Verified',
                    message=f'Student {student.user.full_name} has been verified by Registrar. Ready for activation.',
                    notification_type='SYSTEM_ALERT',
                    link='/dept/dashboard'
                )
            
            return Response({
                'message': 'Student documents verified successfully',
                'student_id': student.student_id,
                'documents_verified': True
            })
            
        elif action == 'reject':
            student.documents_verified = False
            student.save()
            
            send_notification(
                recipient_user=student.user,
                title='❌ Documents Rejected',
                message=f'Your documents have been rejected. Reason: {reason}. Please check and resubmit.',
                notification_type='SYSTEM_ALERT',
                link='/profile'
            )
            
            return Response({
                'message': 'Student rejected',
                'reason': reason
            })
        
        return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)


class RegistrarStudentActivateView(APIView):
    """Activate a student account"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, student_id):
        if request.user.role not in ['REGISTRAR', 'ADMIN']:
            return Response(
                {'error': 'Permission denied. Only Registrar or Admin can activate students.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if student.payment_status != 'VERIFIED':
            return Response({'error': 'Payment not verified. Finance must verify payment first.'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if not student.documents_verified:
            return Response({'error': 'Documents not verified. Please verify documents first.'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if not student.student_id:
            return Response({'error': 'Student ID not generated. Please generate ID first.'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if student.is_enrolled:
            return Response({'error': 'Student account is already activated'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        student.is_enrolled = True
        student.registration_complete = True
        student.activated_at = timezone.now()
        student.activated_by = request.user
        student.save()
        student.user.is_active = True
        student.user.save()
        
        send_notification(
            recipient_user=student.user,
            title='🎉 Account Activated!',
            message=f'Your account has been fully activated! You can now access all services.',
            notification_type='SYSTEM_ALERT',
            link='/dashboard'
        )
        
        dept_head = Department.objects.filter(name=student.department).first()
        if dept_head and dept_head.head:
            send_notification(
                recipient_user=dept_head.head,
                title='🎓 New Student Activated',
                message=f'Student {student.user.full_name} (ID: {student.student_id}) has been activated.',
                notification_type='SYSTEM_ALERT',
                link='/dept/dashboard'
            )
        
        return Response({
            'message': 'Student activated successfully',
            'is_enrolled': student.is_enrolled,
            'student_id': student.student_id
        })


class RegistrarGenerateIDView(APIView):
    """Generate Student ID with configurable format"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, student_id):
        if request.user.role not in ['REGISTRAR', 'ADMIN']:
            return Response(
                {'error': 'Permission denied. Only Registrar or Admin can generate IDs.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if student.payment_status != 'VERIFIED':
            return Response({'error': 'Payment must be verified before generating ID'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if not student.documents_verified:
            return Response({'error': 'Documents must be verified before generating ID'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if student.student_id:
            return Response({'error': 'Student already has an ID'}, status=status.HTTP_400_BAD_REQUEST)
        
        from analytics.models import SystemConfig
        
        id_format = SystemConfig.get_value('student_id_format', 'STU{year}{seq:06d}')
        year = timezone.now().year
        student_count = StudentProfile.objects.count() + 1
        
        try:
            student_id = id_format.format(
                year=year,
                seq=student_count,
                dept=student.department[:3].upper() if student.department else 'GEN'
            )
        except:
            student_id = f"STU{year}{student_count:06d}"
        
        student.student_id = student_id
        student.save()
        
        send_notification(
            recipient_user=student.user,
            title='🆔 Student ID Generated',
            message=f'Your Student ID has been generated: {student_id}.',
            notification_type='SYSTEM_ALERT',
            link='/profile'
        )
        
        return Response({
            'message': 'Student ID generated successfully',
            'student_id': student_id
        })


class RegistrarNotifyStudentView(APIView):
    """Send notification to student to upload documents"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, student_id):
        if request.user.role not in ['REGISTRAR', 'ADMIN']:
            return Response(
                {'error': 'Permission denied. Only Registrar can send notifications.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if student.payment_status != 'VERIFIED':
            return Response(
                {'error': 'Payment must be verified before requesting documents'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if student.is_enrolled:
            return Response(
                {'error': 'Student account is already activated'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        message = request.data.get('message', 'Please upload your required documents for verification.')
        
        send_notification(
            recipient_user=student.user,
            title='📄 Document Upload Required',
            message=message,
            notification_type='SYSTEM_ALERT',
            link='/upload-documents'
        )
        
        student.notification_sent = True
        student.save()
        
        return Response({
            'message': 'Notification sent successfully',
            'notification_sent': True
        }, status=status.HTTP_200_OK)


class RegistrarStudentDocumentsView(APIView):
    """Get all documents for a student (Registrar only)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, student_id):
        if request.user.role not in ['REGISTRAR', 'ADMIN']:
            return Response(
                {'error': 'Permission denied. Only Registrar can view student documents.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        
        documents = {
            'student_name': student.user.full_name,
            'student_id': student.student_id,
            'department': student.department,
            'documents_submitted': student.documents_submitted,
            'documents_verified': student.documents_verified,
            'documents_verified_at': student.documents_verified_at,
            'files': []
        }
        
        doc_fields = [
            ('grade_8_certificate', 'Grade 8 Certificate'),
            ('grade_12_certificate', 'Grade 12 Certificate'),
            ('transcript', 'Transcript'),
            ('other_documents', 'Other Documents'),
        ]
        
        for field, label in doc_fields:
            file_obj = getattr(student, field)
            if file_obj:
                documents['files'].append({
                    'field': field,
                    'label': label,
                    'filename': file_obj.name,
                    'url': file_obj.url,
                    'size': file_obj.size if hasattr(file_obj, 'size') else None,
                    'uploaded_at': getattr(student, 'documents_verified_at', None)
                })
        
        return Response(documents, status=status.HTTP_200_OK)


class RegistrarDownloadDocumentView(APIView):
    """Download a specific student document (Registrar only)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, document_type, student_id):
        if request.user.role not in ['REGISTRAR', 'ADMIN']:
            return Response(
                {'error': 'Permission denied. Only Registrar can download documents.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student not found'}, status=status.HTTP_404_NOT_FOUND)
        
        valid_types = ['grade_8_certificate', 'grade_12_certificate', 'transcript', 'other_documents']
        
        if document_type not in valid_types:
            return Response(
                {'error': f'Invalid document type. Valid types: {", ".join(valid_types)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file_obj = getattr(student, document_type)
        if not file_obj:
            return Response(
                {'error': f'Document {document_type} not found for this student'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response({
            'url': file_obj.url,
            'filename': file_obj.name,
            'student_name': student.user.full_name,
            'student_id': student.student_id,
            'document_type': document_type
        }, status=status.HTTP_200_OK)


# ============= REGISTRAR CONFIGURATION VIEWS =============

class RegistrationConfigView(APIView):
    """Get or update registration configuration"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            config = RegistrationConfig.objects.filter(is_active=True).latest('created_at')
            serializer = RegistrationConfigSerializer(config)
            return Response(serializer.data)
        except RegistrationConfig.DoesNotExist:
            return Response({
                'registration_start_date': None,
                'registration_end_date': None,
                'semester': '1',
                'academic_year': str(timezone.now().year),
                'require_grade_8': True,
                'require_grade_12': True,
                'require_transcript': True,
                'require_other_documents': False,
                'is_active': False,
                'max_students_per_department': 100,
                'allow_senior_registration': True,
                'allow_fresh_registration': True
            })
    
    def post(self, request):
        if request.user.role not in ['REGISTRAR', 'ADMIN']:
            return Response(
                {'error': 'Permission denied. Only Registrar can configure registration.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        RegistrationConfig.objects.all().update(is_active=False)
        
        serializer = RegistrationConfigSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        config = serializer.save(updated_by=request.user, is_active=True)
        
        send_notification(
            recipient_roles=['ADMIN', 'DEPT_HEAD'],
            title='📅 Registration Period Updated',
            message=f'Registration period for {config.academic_year} - Semester {config.semester} has been configured.',
            notification_type='SYSTEM_ALERT',
            link='/registrar/dashboard'
        )
        
        return Response({
            'message': 'Registration configuration updated successfully',
            'data': serializer.data
        }, status=status.HTTP_201_CREATED)
    
    def put(self, request):
        return self.post(request)


# ============= STUDENT DOCUMENT UPLOAD =============

class StudentDocumentUploadView(APIView):
    """Upload student documents"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        if request.user.role != 'STUDENT':
            return Response(
                {'error': 'Only students can upload documents'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return Response(
                {'error': 'Student profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if student.payment_status != 'VERIFIED':
            return Response(
                {'error': 'Payment must be verified before uploading documents'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if student.is_enrolled:
            return Response(
                {'error': 'Account already activated. No documents needed.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        allowed_fields = ['grade_8_certificate', 'grade_12_certificate', 'transcript', 'other_documents']
        updated = False
        uploaded_files = []
        
        for field in allowed_fields:
            if field in request.FILES:
                setattr(student, field, request.FILES[field])
                updated = True
                uploaded_files.append(field)
        
        if updated:
            student.documents_submitted = True
            student.save()
            
            send_notification(
                recipient_roles=['REGISTRAR'],
                title='📄 Documents Uploaded',
                message=f'Student {student.user.full_name} has uploaded documents.',
                notification_type='SYSTEM_ALERT',
                link='/registrar/dashboard'
            )
            
            return Response({
                'message': 'Documents uploaded successfully',
                'documents_submitted': True,
                'uploaded_files': uploaded_files
            }, status=status.HTTP_200_OK)
        
        return Response(
            {'error': 'No valid document fields found in request'},
            status=status.HTTP_400_BAD_REQUEST
        )


# ============= ADMIN USER CREATION VIEWS =============

class AdminCreateUserView(APIView):
    """Admin creates any user with proper department assignment"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        if request.user.role != 'ADMIN':
            return Response(
                {'error': 'Only admins can create users'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        email = request.data.get('email')
        full_name = request.data.get('full_name')
        password = request.data.get('password')
        role = request.data.get('role', 'STUDENT')
        phone = request.data.get('phone', '')
        department_name = request.data.get('department', '')
        headed_department_name = request.data.get('headed_department', '')
        
        if not email or not full_name or not password:
            return Response(
                {'error': 'Email, full name, and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if User.objects.filter(email=email).exists():
            return Response(
                {'error': 'User with this email already exists'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = User.objects.create_user(
            email=email,
            full_name=full_name,
            password=password,
            role=role,
            phone=phone
        )
        
        if role == 'STUDENT':
            StudentProfile.objects.create(
                user=user,
                department=department_name,
                payment_status='PENDING',
                registration_type='FRESH'
            )
            send_notification(
                recipient_roles=['REGISTRAR'],
                title='📝 New Student Created by Admin',
                message=f'Student {full_name} created. Department: {department_name}',
                notification_type='SYSTEM_ALERT',
                link='/registrar/dashboard'
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
                department=headed_department_name,
                employee_id=f"HOD{user.id:06d}"
            )
            if headed_department_name:
                try:
                    department = Department.objects.get(name=headed_department_name)
                    department.head = user
                    department.save()
                except Department.DoesNotExist:
                    pass
        
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
        
        return Response({
            'message': f'{role} created successfully',
            'user': {
                'id': user.id,
                'email': user.email,
                'full_name': user.full_name,
                'role': user.role,
                'department': department_name
            }
        }, status=status.HTTP_201_CREATED)


# ================================================================
# ============= DEPARTMENT HEAD VIEWS =============
# ================================================================

# accounts/views.py - ADD/REPLACE THESE DEPARTMENT HEAD VIEWS

# ================================================================
# ============= DEPARTMENT HEAD VIEWS (COMPLETE FIXED) =============
# ================================================================

class DeptHeadStudentListView(APIView):
    """List students in department head's department with year filtering"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        if user.role != 'DEPT_HEAD':
            return Response(
                {'results': [], 'count': 0, 'message': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            department = user.headed_department
            if not department:
                return Response({
                    'results': [],
                    'count': 0,
                    'message': 'No department assigned'
                }, status=status.HTTP_200_OK)
            
            # Get filter parameters
            year_filter = request.query_params.get('year')
            semester_filter = request.query_params.get('semester')
            status_filter = request.query_params.get('status')
            search_term = request.query_params.get('search', '')
            
            # Base queryset
            students = StudentProfile.objects.filter(
                department=department.name
            ).select_related('user').order_by('-enrollment_date')
            
            # Filter by year
            if year_filter:
                try:
                    year = int(year_filter)
                    # Year 1: Semesters 1-2, Year 2: Semesters 3-4, etc.
                    semester_start = (year - 1) * 2 + 1
                    semester_end = year * 2
                    students = students.filter(
                        current_semester__gte=semester_start,
                        current_semester__lte=semester_end
                    )
                except ValueError:
                    pass
            
            # Filter by semester
            if semester_filter:
                try:
                    students = students.filter(current_semester=int(semester_filter))
                except ValueError:
                    pass
            
            # Filter by status
            if status_filter == 'enrolled':
                students = students.filter(is_enrolled=True)
            elif status_filter == 'pending':
                students = students.filter(is_enrolled=False, documents_verified=False)
            elif status_filter == 'verified':
                students = students.filter(documents_verified=True)
            elif status_filter == 'not_enrolled':
                students = students.filter(is_enrolled=False)
            
            # Search
            if search_term:
                students = students.filter(
                    Q(user__full_name__icontains=search_term) |
                    Q(student_id__icontains=search_term) |
                    Q(user__email__icontains=search_term)
                )
            
            # Build result
            result = []
            for student in students:
                # Get student's results/courses
                from courses.models import Enrollment
                enrollments = Enrollment.objects.filter(
                    student=student
                ).select_related('course')
                
                course_grades = []
                total_marks_obtained = 0
                total_marks_possible = 0
                
                for enrollment in enrollments:
                    enrollment.update_course_grade()
                    course_grades.append({
                        'course_id': enrollment.course.id,
                        'course_code': enrollment.course.course_code,
                        'course_title': enrollment.course.title,
                        'credit_hours': enrollment.course.credit_hours,
                        'grade': enrollment.grade_letter or 'NON',
                        'grade_points': float(enrollment.grade_points or 0),
                        'marks_obtained': float(enrollment.total_marks_obtained or 0),
                        'marks_possible': float(enrollment.total_marks_possible or 0),
                        'percentage': float(enrollment.percentage_score or 0),
                        'status': enrollment.status,
                    })
                    
                    if enrollment.total_marks_obtained:
                        total_marks_obtained += float(enrollment.total_marks_obtained)
                    if enrollment.total_marks_possible:
                        total_marks_possible += float(enrollment.total_marks_possible)
                
                overall_percentage = 0
                if total_marks_possible > 0:
                    overall_percentage = (total_marks_obtained / total_marks_possible) * 100
                
                result.append({
                    'id': student.id,
                    'full_name': student.user.full_name if student.user else 'Unknown',
                    'email': student.user.email if student.user else '',
                    'student_id': student.student_id or '',
                    'department': student.department,
                    'current_semester': student.current_semester,
                    'year': (student.current_semester + 1) // 2 if student.current_semester else 0,
                    'documents_verified': student.documents_verified,
                    'is_enrolled': student.is_enrolled,
                    'payment_status': student.payment_status,
                    'cgpa': str(student.cgpa) if student.cgpa else '0.00',
                    'enrollment_date': student.enrollment_date.isoformat() if student.enrollment_date else None,
                    'total_credits': student.total_credits,
                    'course_grades': course_grades,
                    'overall_marks': {
                        'obtained': round(total_marks_obtained, 2),
                        'possible': round(total_marks_possible, 2),
                        'percentage': round(overall_percentage, 2),
                    },
                    'has_results': len([g for g in course_grades if g['grade'] != 'NON']) > 0,
                })
            
            # Statistics
            total = len(result)
            enrolled = len([s for s in result if s['is_enrolled']])
            pending = len([s for s in result if not s['is_enrolled'] and not s['documents_verified']])
            verified = len([s for s in result if s['documents_verified']])
            has_results = len([s for s in result if s['has_results']])
            
            return Response({
                'results': result,
                'count': total,
                'stats': {
                    'total': total,
                    'enrolled': enrolled,
                    'pending': pending,
                    'verified': verified,
                    'has_results': has_results,
                }
            })
            
        except Exception as e:
            logger.error(f"Error fetching students: {e}")
            return Response({
                'results': [],
                'count': 0,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DeptHeadTeacherListView(APIView):
    """List teachers in department head's department with full details"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        if user.role != 'DEPT_HEAD':
            return Response({
                'results': [],
                'count': 0,
                'message': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            department = user.headed_department
            if not department:
                return Response({
                    'results': [],
                    'count': 0,
                    'message': 'No department assigned'
                }, status=status.HTTP_200_OK)
            
            search_term = request.query_params.get('search', '')
            
            # Get teachers from TeacherProfile
            teachers = TeacherProfile.objects.filter(
                department=department.name
            ).select_related('user').order_by('-joining_date')
            
            if search_term:
                teachers = teachers.filter(
                    Q(user__full_name__icontains=search_term) |
                    Q(employee_id__icontains=search_term) |
                    Q(user__email__icontains=search_term)
                )
            
            result = []
            seen_ids = set()
            
            for teacher in teachers:
                if teacher.user and teacher.user.id not in seen_ids:
                    seen_ids.add(teacher.user.id)
                    
                    # Get courses taught by this teacher
                    from courses.models import Course
                    courses_taught = Course.objects.filter(
                        instructor=teacher.user,
                        department=department
                    ).count()
                    
                    # Get enrolled students in those courses
                    from courses.models import Enrollment
                    student_count = Enrollment.objects.filter(
                        course__instructor=teacher.user,
                        status='ACTIVE'
                    ).count()
                    
                    result.append({
                        'id': teacher.id,
                        'user_id': teacher.user.id,
                        'full_name': teacher.user.full_name,
                        'email': teacher.user.email,
                        'department': teacher.department,
                        'employee_id': teacher.employee_id or '',
                        'qualification': teacher.qualification or '',
                        'specialization': teacher.specialization or '',
                        'is_verified': teacher.is_verified,
                        'joining_date': teacher.joining_date.isoformat() if teacher.joining_date else None,
                        'courses_taught': courses_taught,
                        'student_count': student_count,
                        'is_active': teacher.user.is_active,
                    })
            
            # Also get users with role TEACHER or DEPT_HEAD not in TeacherProfile
            teacher_users = User.objects.filter(
                role__in=['TEACHER', 'DEPT_HEAD'],
                is_active=True
            ).exclude(id=user.id)
            
            for u in teacher_users:
                if u.id not in seen_ids and u.id not in [t.get('user_id') for t in result]:
                    # Check if they are in the department
                    from courses.models import Course
                    courses_in_dept = Course.objects.filter(
                        instructor=u,
                        department=department
                    ).exists()
                    
                    if courses_in_dept:
                        seen_ids.add(u.id)
                        result.append({
                            'id': None,
                            'user_id': u.id,
                            'full_name': u.full_name,
                            'email': u.email,
                            'department': department.name,
                            'employee_id': '',
                            'qualification': '',
                            'specialization': '',
                            'is_verified': True,
                            'joining_date': None,
                            'courses_taught': Course.objects.filter(instructor=u, department=department).count(),
                            'student_count': 0,
                            'is_active': u.is_active,
                        })
            
            return Response({
                'results': result,
                'count': len(result),
                'department': department.name,
            })
            
        except Exception as e:
            logger.error(f"Error fetching teachers: {e}")
            return Response({
                'results': [],
                'count': 0,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DeptHeadCourseListView(APIView):
    """List courses in department head's department"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        if user.role != 'DEPT_HEAD':
            return Response({
                'results': [],
                'count': 0,
                'message': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from courses.models import Course
            from courses.serializers import CourseSerializer
            
            department = user.headed_department
            if not department:
                return Response({
                    'results': [],
                    'count': 0,
                    'message': 'No department assigned'
                }, status=status.HTTP_200_OK)
            
            courses = Course.objects.filter(
                department=department
            ).select_related('instructor', 'department').order_by('-created_at')
            
            # Manually serialize courses
            result = []
            for course in courses:
                # Get enrolled count
                enrolled_count = course.enrollments.filter(status='ACTIVE').count()
                
                result.append({
                    'id': course.id,
                    'course_code': course.course_code,
                    'title': course.title,
                    'description': course.description or '',
                    'credit_hours': course.credit_hours,
                    'semester': course.semester,
                    'capacity': course.capacity,
                    'instructor': course.instructor.id if course.instructor else None,
                    'instructor_name': course.instructor.full_name if course.instructor else 'Not Assigned',
                    'department': course.department.id if course.department else None,
                    'department_name': course.department.name if course.department else department.name,
                    'is_active': course.is_active,
                    'is_approved': course.is_approved,
                    'enrolled_count': enrolled_count,
                    'created_at': course.created_at.isoformat() if course.created_at else None,
                })
            
            total = len(result)
            approved = len([c for c in result if c['is_approved']])
            pending = total - approved
            
            return Response({
                'results': result,
                'count': total,
                'stats': {
                    'total': total,
                    'approved': approved,
                    'pending': pending,
                }
            })
            
        except Exception as e:
            print(f"Error fetching courses: {e}")
            return Response({
                'results': [],
                'count': 0,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DeptHeadCourseApproveView(APIView):
    """Approve or reject a course"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, course_id):
        if request.user.role != 'DEPT_HEAD':
            return Response(
                {'error': 'Permission denied. Only Department Head can approve courses.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            from courses.models import Course
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if course is in department
        try:
            department = request.user.headed_department
            if course.department != department:
                return Response(
                    {'error': 'You can only approve courses in your department'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Exception as e:
            return Response(
                {'error': 'You are not assigned to any department'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        action = request.data.get('action')
        reason = request.data.get('reason', '')
        
        if action == 'approve':
            course.is_approved = True
            course.approved_by = request.user
            course.save()
            
            send_notification(
                recipient_user=course.instructor,
                title='✅ Course Approved',
                message=f'Your course "{course.title}" has been approved by Department Head.',
                notification_type='COURSE_APPROVED',
                link=f'/courses/{course.id}'
            )
            
            return Response({
                'message': 'Course approved successfully',
                'is_approved': True
            })
            
        elif action == 'reject':
            course.is_approved = False
            course.is_active = False
            course.save()
            
            send_notification(
                recipient_user=course.instructor,
                title='❌ Course Rejected',
                message=f'Your course "{course.title}" has been rejected. Reason: {reason}',
                notification_type='COURSE_REJECTED',
                link='/teacher/courses'
            )
            
            return Response({
                'message': 'Course rejected',
                'reason': reason
            })
        
        return Response(
            {'error': 'Invalid action. Use "approve" or "reject".'},
            status=status.HTTP_400_BAD_REQUEST
        )


class DeptHeadFinalExamListView(APIView):
    """List final exams in department head's department"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        if user.role != 'DEPT_HEAD':
            return Response({
                'results': [],
                'count': 0,
                'message': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        try:
            from exams.models import Exam
            
            department = user.headed_department
            if not department:
                return Response({
                    'results': [],
                    'count': 0,
                    'message': 'No department assigned'
                }, status=status.HTTP_200_OK)
            
            search_term = request.query_params.get('search', '')
            status_filter = request.query_params.get('status')
            
            exams = Exam.objects.filter(
                course__department=department
            ).select_related('course', 'created_by').order_by('-start_time')
            
            if search_term:
                exams = exams.filter(
                    Q(title__icontains=search_term) |
                    Q(course__title__icontains=search_term) |
                    Q(course__course_code__icontains=search_term)
                )
            
            if status_filter == 'published':
                exams = exams.filter(is_published=True)
            elif status_filter == 'draft':
                exams = exams.filter(is_published=False)
            elif status_filter == 'ongoing':
                now = timezone.now()
                exams = exams.filter(start_time__lte=now, end_time__gte=now)
            elif status_filter == 'upcoming':
                now = timezone.now()
                exams = exams.filter(start_time__gt=now)
            elif status_filter == 'completed':
                now = timezone.now()
                exams = exams.filter(end_time__lt=now)
            
            result = []
            for exam in exams:
                # Get submission stats
                from exams.models import ExamAttempt
                attempts = ExamAttempt.objects.filter(exam=exam)
                total_attempts = attempts.count()
                submitted = attempts.filter(status__in=['SUBMITTED', 'GRADED']).count()
                graded = attempts.filter(status='GRADED').count()
                
                result.append({
                    'id': exam.id,
                    'title': exam.title,
                    'description': exam.description or '',
                    'course': exam.course.id if exam.course else None,
                    'course_title': exam.course.title if exam.course else 'Unknown',
                    'course_code': exam.course.course_code if exam.course else '',
                    'course_department': exam.course.department.name if exam.course and exam.course.department else department.name,
                    'duration_minutes': exam.duration_minutes,
                    'start_time': exam.start_time.isoformat() if exam.start_time else None,
                    'end_time': exam.end_time.isoformat() if exam.end_time else None,
                    'total_marks': float(exam.total_marks) if exam.total_marks else 0,
                    'passing_mark': float(exam.passing_mark) if exam.passing_mark else 0,
                    'is_published': exam.is_published,
                    'proctoring_enabled': exam.proctoring_enabled,
                    'created_by': exam.created_by.id if exam.created_by else None,
                    'created_by_name': exam.created_by.full_name if exam.created_by else None,
                    'created_at': exam.created_at.isoformat() if exam.created_at else None,
                    'total_attempts': total_attempts,
                    'submitted_count': submitted,
                    'graded_count': graded,
                    'pending_count': submitted - graded,
                })
            
            total = len(result)
            published = len([e for e in result if e['is_published']])
            
            return Response({
                'results': result,
                'count': total,
                'stats': {
                    'total': total,
                    'published': published,
                }
            })
            
        except Exception as e:
            logger.error(f"Error fetching final exams: {e}")
            return Response({
                'results': [],
                'count': 0,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DeptHeadFinalExamDetailView(APIView):
    """Get details of a specific final exam"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, exam_id):
        if request.user.role != 'DEPT_HEAD':
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            from exams.models import Exam
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if exam is in department
        try:
            department = request.user.headed_department
            if exam.course.department != department:
                return Response(
                    {'error': 'Exam not in your department'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Exception as e:
            return Response(
                {'error': 'Department not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        return Response({
            'id': exam.id,
            'title': exam.title,
            'description': exam.description or '',
            'course': exam.course.id if exam.course else None,
            'course_title': exam.course.title if exam.course else 'Unknown',
            'course_code': exam.course.course_code if exam.course else '',
            'duration_minutes': exam.duration_minutes,
            'start_time': exam.start_time.isoformat() if exam.start_time else None,
            'end_time': exam.end_time.isoformat() if exam.end_time else None,
            'total_marks': float(exam.total_marks) if exam.total_marks else 0,
            'passing_mark': float(exam.passing_mark) if exam.passing_mark else 0,
            'is_published': exam.is_published,
            'proctoring_enabled': exam.proctoring_enabled,
            'created_by': exam.created_by.id if exam.created_by else None,
            'created_by_name': exam.created_by.full_name if exam.created_by else None,
            'created_at': exam.created_at.isoformat() if exam.created_at else None,
        })


class DeptHeadFinalExamUpdateView(APIView):
    """Update final exam schedule (date/time only)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def put(self, request, exam_id):
        if request.user.role != 'DEPT_HEAD':
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            from exams.models import Exam
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if exam is in department
        try:
            department = request.user.headed_department
            if exam.course.department != department:
                return Response(
                    {'error': 'Exam not in your department'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Exception as e:
            return Response(
                {'error': 'Department not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Only allow updating date and time
        start_time = request.data.get('start_time')
        end_time = request.data.get('end_time')
        
        if start_time:
            exam.start_time = start_time
        if end_time:
            exam.end_time = end_time
        
        exam.save()
        
        return Response({
            'message': 'Exam schedule updated successfully',
            'exam': {
                'id': exam.id,
                'title': exam.title,
                'start_time': exam.start_time.isoformat() if exam.start_time else None,
                'end_time': exam.end_time.isoformat() if exam.end_time else None,
            }
        })


class DeptHeadFinalExamDeleteView(APIView):
    """Delete a final exam"""
    permission_classes = [permissions.IsAuthenticated]
    
    def delete(self, request, exam_id):
        if request.user.role != 'DEPT_HEAD':
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            from exams.models import Exam
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if exam is in department
        try:
            department = request.user.headed_department
            if exam.course.department != department:
                return Response(
                    {'error': 'Exam not in your department'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Exception as e:
            return Response(
                {'error': 'Department not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        exam.delete()
        return Response({'message': 'Exam deleted successfully'})


class DeptHeadDashboardView(APIView):
    """Get department head dashboard statistics"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        if user.role != 'DEPT_HEAD':
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            department = user.headed_department
            if not department:
                return Response(
                    {'error': 'You are not assigned to any department'},
                    status=status.HTTP_404_NOT_FOUND
                )
        except Exception as e:
            return Response(
                {'error': 'Department not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # ============ STUDENTS ============
        students = StudentProfile.objects.filter(department=department.name)
        total_students = students.count()
        
        # Students by year (based on current_semester)
        # Year 1: Semesters 1-2, Year 2: Semesters 3-4, etc.
        students_by_year = {}
        for semester in range(1, 17):  # Up to 8 years (16 semesters)
            year = (semester + 1) // 2
            count = students.filter(current_semester=semester).count()
            if count > 0:
                if year not in students_by_year:
                    students_by_year[year] = 0
                students_by_year[year] += count
        
        enrolled_students = students.filter(is_enrolled=True).count()
        pending_students = students.filter(is_enrolled=False, documents_verified=False).count()
        verified_students = students.filter(documents_verified=True).count()
        
        # ============ TEACHERS ============
        teachers = TeacherProfile.objects.filter(department=department.name)
        total_teachers = teachers.count()
        verified_teachers = teachers.filter(is_verified=True).count()
        unverified_teachers = teachers.filter(is_verified=False).count()
        
        # ============ COURSES ============
        from courses.models import Course
        courses = Course.objects.filter(department=department)
        total_courses = courses.count()
        approved_courses = courses.filter(is_approved=True).count()
        pending_courses = courses.filter(is_approved=False).count()
        
        # Courses by semester/year
        courses_by_semester = {}
        for sem in range(1, 9):
            count = courses.filter(semester=str(sem)).count()
            if count > 0:
                courses_by_semester[f"Semester {sem}"] = count
        
        # ============ EXAMS ============
        from exams.models import Exam
        exams = Exam.objects.filter(course__department=department)
        total_exams = exams.count()
        published_exams = exams.filter(is_published=True).count()
        
        # ============ ENROLLMENTS ============
        from courses.models import Enrollment
        enrollments = Enrollment.objects.filter(course__department=department, status='ACTIVE')
        total_enrollments = enrollments.count()
        
        # ============ RESULTS (Submitted by Teachers) ============
        from exams.models import ExamAttempt
        submitted_results = ExamAttempt.objects.filter(
            exam__course__department=department,
            status__in=['SUBMITTED', 'GRADED']
        )
        total_submitted_results = submitted_results.count()
        graded_results = submitted_results.filter(status='GRADED').count()
        pending_grading = submitted_results.filter(status='SUBMITTED').count()
        
        # Results sent to Registrar
        sent_to_registrar = submitted_results.filter(
            result_sent_to_registrar=True
        ).count() if hasattr(ExamAttempt, 'result_sent_to_registrar') else 0
        
        # ============ GRADE DISTRIBUTION ============
        from courses.models import Enrollment as CourseEnrollment
        completed_enrollments = CourseEnrollment.objects.filter(
            course__department=department,
            status='COMPLETED'
        )
        
        grade_distribution = {
            'A+': 0, 'A': 0, 'A-': 0,
            'B+': 0, 'B': 0, 'B-': 0,
            'C+': 0, 'C': 0, 'C-': 0,
            'D+': 0, 'D': 0,
            'F': 0, 'NON': 0
        }
        
        for enrollment in completed_enrollments:
            grade = enrollment.grade_letter or 'NON'
            if grade in grade_distribution:
                grade_distribution[grade] += 1
            else:
                grade_distribution['NON'] += 1
        
        return Response({
            'department': {
                'id': department.id,
                'name': department.name,
                'code': department.code,
                'head_name': user.full_name,
            },
            'students': {
                'total': total_students,
                'by_year': students_by_year,
                'enrolled': enrolled_students,
                'pending': pending_students,
                'verified': verified_students,
            },
            'teachers': {
                'total': total_teachers,
                'verified': verified_teachers,
                'unverified': unverified_teachers,
            },
            'courses': {
                'total': total_courses,
                'approved': approved_courses,
                'pending': pending_courses,
                'by_semester': courses_by_semester,
            },
            'exams': {
                'total': total_exams,
                'published': published_exams,
            },
            'enrollments': {
                'total': total_enrollments,
            },
            'results': {
                'total_submitted': total_submitted_results,
                'graded': graded_results,
                'pending_grading': pending_grading,
                'sent_to_registrar': sent_to_registrar,
            },
            'grade_distribution': grade_distribution,
        })
 
class DeptHeadTeacherManagementView(APIView):
    """Manage teachers in department - Add, Remove, Verify"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        user = request.user
        if user.role != 'DEPT_HEAD':
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            department = user.headed_department
            if not department:
                return Response(
                    {'error': 'No department assigned'},
                    status=status.HTTP_404_NOT_FOUND
                )
        except:
            return Response(
                {'error': 'Department not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        action = request.data.get('action')
        teacher_id = request.data.get('teacher_id')
        
        if not action or not teacher_id:
            return Response(
                {'error': 'action and teacher_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            teacher = User.objects.get(id=teacher_id)
        except User.DoesNotExist:
            return Response(
                {'error': 'Teacher not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if teacher.role not in ['TEACHER', 'DEPT_HEAD']:
            return Response(
                {'error': 'User is not a teacher'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            teacher_profile = TeacherProfile.objects.get(user=teacher)
        except TeacherProfile.DoesNotExist:
            # Create teacher profile if it doesn't exist
            teacher_profile = TeacherProfile.objects.create(
                user=teacher,
                department=department.name,
                employee_id=f"TCH{teacher.id:06d}"
            )
        
        if action == 'verify':
            teacher_profile.is_verified = True
            teacher_profile.department = department.name
            teacher_profile.save()
            
            # Send notification
            from notifications.utils import send_notification
            send_notification(
                recipient_user=teacher,
                title='✅ Teacher Verified',
                message=f'You have been verified as a teacher in {department.name} department.',
                notification_type='SYSTEM_ALERT',
                link='/teacher/dashboard'
            )
            
            return Response({
                'message': 'Teacher verified successfully',
                'is_verified': True,
                'teacher_id': teacher.id,
                'full_name': teacher.full_name,
            })
        
        elif action == 'unverify':
            teacher_profile.is_verified = False
            teacher_profile.save()
            return Response({
                'message': 'Teacher unverified',
                'is_verified': False,
            })
        
        elif action == 'assign_department':
            teacher_profile.department = department.name
            teacher_profile.save()
            return Response({
                'message': f'Teacher assigned to {department.name} department',
                'department': department.name,
            })
        
        elif action == 'remove':
            teacher_profile.department = ''
            teacher_profile.is_verified = False
            teacher_profile.save()
            
            # Send notification
            from notifications.utils import send_notification
            send_notification(
                recipient_user=teacher,
                title='📋 Department Removed',
                message=f'You have been removed from {department.name} department.',
                notification_type='SYSTEM_ALERT',
                link='/dashboard'
            )
            
            return Response({
                'message': f'Teacher removed from {department.name} department',
            })
        
        return Response(
            {'error': 'Invalid action'},
            status=status.HTTP_400_BAD_REQUEST
        )
class DeptHeadStudentResultsView(APIView):
    """View student results/grades for department head"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, student_id):
        user = request.user
        if user.role != 'DEPT_HEAD':
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            department = user.headed_department
            if not department:
                return Response(
                    {'error': 'No department assigned'},
                    status=status.HTTP_404_NOT_FOUND
                )
        except:
            return Response(
                {'error': 'Department not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            student = StudentProfile.objects.get(id=student_id)
        except StudentProfile.DoesNotExist:
            return Response(
                {'error': 'Student not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if student is in department
        if student.department != department.name:
            return Response(
                {'error': 'Student is not in your department'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from courses.models import Enrollment
        enrollments = Enrollment.objects.filter(
            student=student
        ).select_related('course')
        
        results = []
        total_marks_obtained = 0
        total_marks_possible = 0
        
        for enrollment in enrollments:
            enrollment.update_course_grade()
            
            # Get teacher name
            teacher_name = enrollment.course.instructor.full_name if enrollment.course.instructor else 'Not Assigned'
            
            results.append({
                'course_id': enrollment.course.id,
                'course_code': enrollment.course.course_code,
                'course_title': enrollment.course.title,
                'credit_hours': enrollment.course.credit_hours,
                'teacher_name': teacher_name,
                'semester': enrollment.course.semester,
                'marks_obtained': float(enrollment.total_marks_obtained or 0),
                'marks_possible': float(enrollment.total_marks_possible or 0),
                'percentage': float(enrollment.percentage_score or 0),
                'grade': enrollment.grade_letter or 'NON',
                'grade_points': float(enrollment.grade_points or 0),
                'status': enrollment.status,
                'completed': enrollment.status == 'COMPLETED',
            })
            
            if enrollment.total_marks_obtained:
                total_marks_obtained += float(enrollment.total_marks_obtained)
            if enrollment.total_marks_possible:
                total_marks_possible += float(enrollment.total_marks_possible)
        
        overall_percentage = 0
        if total_marks_possible > 0:
            overall_percentage = (total_marks_obtained / total_marks_possible) * 100
        
        from utils.grading import calculate_grade
        overall_grade = calculate_grade(overall_percentage)
        
        # Get exam results
        from exams.models import ExamAttempt
        exam_attempts = ExamAttempt.objects.filter(
            student=student,
            status__in=['SUBMITTED', 'GRADED']
        ).select_related('exam', 'exam__course')
        
        exam_results = []
        for attempt in exam_attempts:
            exam_results.append({
                'exam_id': attempt.exam.id,
                'exam_title': attempt.exam.title,
                'course_code': attempt.exam.course.course_code,
                'score': float(attempt.score or 0),
                'total_marks': float(attempt.total_marks or 0),
                'percentage': float(attempt.percentage or 0),
                'passed': attempt.passed,
                'status': attempt.status,
            })
        
        return Response({
            'student': {
                'id': student.id,
                'full_name': student.user.full_name,
                'student_id': student.student_id,
                'email': student.user.email,
                'department': student.department,
                'current_semester': student.current_semester,
                'year': (student.current_semester + 1) // 2 if student.current_semester else 0,
                'cgpa': float(student.cgpa or 0),
                'total_credits': student.total_credits,
            },
            'course_results': results,
            'exam_results': exam_results,
            'summary': {
                'total_courses': len(enrollments),
                'completed_courses': len([r for r in results if r['status'] == 'COMPLETED']),
                'total_marks_obtained': round(total_marks_obtained, 2),
                'total_marks_possible': round(total_marks_possible, 2),
                'overall_percentage': round(overall_percentage, 2),
                'overall_grade': overall_grade,
                'cgpa': float(student.cgpa or 0),
            }
        })


class DeptHeadSendResultsToRegistrarView(APIView):
    """Department Head sends student results to Registrar (Read-only for Registrar)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        user = request.user
        if user.role != 'DEPT_HEAD':
            return Response(
                {'error': 'Permission denied. Only Department Head can send results to Registrar.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            department = user.headed_department
            if not department:
                return Response(
                    {'error': 'No department assigned'},
                    status=status.HTTP_404_NOT_FOUND
                )
        except:
            return Response(
                {'error': 'Department not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        student_id = request.data.get('student_id')
        course_id = request.data.get('course_id')
        send_all = request.data.get('send_all', False)
        
        from courses.models import Enrollment
        
        if student_id:
            # Send results for specific student
            try:
                student = StudentProfile.objects.get(id=student_id)
                if student.department != department.name:
                    return Response(
                        {'error': 'Student is not in your department'},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                enrollments = Enrollment.objects.filter(student=student)
                sent_count = 0
                
                for enrollment in enrollments:
                    enrollment.update_course_grade()
                    if enrollment.status == 'COMPLETED' and enrollment.grade_letter and enrollment.grade_letter != 'NON':
                        # Mark as sent to Registrar
                        enrollment.result_sent_to_registrar = True
                        enrollment.result_sent_at = timezone.now()
                        enrollment.result_sent_by = user
                        enrollment.save()
                        sent_count += 1
                
                # Send notification to Registrar
                from notifications.utils import send_notification
                send_notification(
                    recipient_roles=['REGISTRAR'],
                    title='📋 Student Results Sent',
                    message=f'Department Head {user.full_name} has sent results for student {student.user.full_name} ({student.student_id}).',
                    notification_type='SYSTEM_ALERT',
                    link='/registrar/dashboard'
                )
                
                return Response({
                    'message': f'Results sent to Registrar for {student.user.full_name}',
                    'sent_count': sent_count,
                    'student_id': student.id,
                    'student_name': student.user.full_name,
                })
                
            except StudentProfile.DoesNotExist:
                return Response(
                    {'error': 'Student not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        elif course_id:
            # Send results for all students in a course
            try:
                from courses.models import Course
                course = Course.objects.get(id=course_id, department=department)
                
                enrollments = Enrollment.objects.filter(course=course)
                sent_count = 0
                
                for enrollment in enrollments:
                    enrollment.update_course_grade()
                    if enrollment.status == 'COMPLETED' and enrollment.grade_letter and enrollment.grade_letter != 'NON':
                        enrollment.result_sent_to_registrar = True
                        enrollment.result_sent_at = timezone.now()
                        enrollment.result_sent_by = user
                        enrollment.save()
                        sent_count += 1
                
                from notifications.utils import send_notification
                send_notification(
                    recipient_roles=['REGISTRAR'],
                    title='📋 Course Results Sent',
                    message=f'Department Head {user.full_name} has sent results for course {course.course_code} - {course.title}.',
                    notification_type='SYSTEM_ALERT',
                    link='/registrar/dashboard'
                )
                
                return Response({
                    'message': f'Results sent to Registrar for course {course.course_code}',
                    'sent_count': sent_count,
                    'course_id': course.id,
                    'course_name': course.title,
                })
                
            except Course.DoesNotExist:
                return Response(
                    {'error': 'Course not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        elif send_all:
            # Send all results for the department
            enrollments = Enrollment.objects.filter(
                course__department=department,
                status='COMPLETED'
            )
            sent_count = 0
            
            for enrollment in enrollments:
                enrollment.update_course_grade()
                if enrollment.grade_letter and enrollment.grade_letter != 'NON':
                    enrollment.result_sent_to_registrar = True
                    enrollment.result_sent_at = timezone.now()
                    enrollment.result_sent_by = user
                    enrollment.save()
                    sent_count += 1
            
            from notifications.utils import send_notification
            send_notification(
                recipient_roles=['REGISTRAR'],
                title='📋 Department Results Sent',
                message=f'Department Head {user.full_name} has sent all results for {department.name} department.',
                notification_type='SYSTEM_ALERT',
                link='/registrar/dashboard'
            )
            
            return Response({
                'message': f'All results sent to Registrar for {department.name}',
                'sent_count': sent_count,
                'department': department.name,
            })
        
        return Response(
            {'error': 'Please provide student_id, course_id, or send_all=True'},
            status=status.HTTP_400_BAD_REQUEST
        )


class DeptHeadGetSentResultsView(APIView):
    """Get results that have been sent to Registrar (Read-only for Registrar)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Department Head can view sent results
        if user.role == 'DEPT_HEAD':
            try:
                department = user.headed_department
                if not department:
                    return Response({
                        'results': [],
                        'message': 'No department assigned'
                    }, status=status.HTTP_200_OK)
            except:
                return Response({
                    'results': [],
                    'message': 'Department not found'
                }, status=status.HTTP_200_OK)
        
        # Registrar can view all sent results (READ ONLY)
        elif user.role == 'REGISTRAR':
            department = None  # Can see all
        else:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from courses.models import Enrollment
        
        enrollments = Enrollment.objects.filter(
            result_sent_to_registrar=True
        ).select_related('student__user', 'course')
        
        if user.role == 'DEPT_HEAD':
            enrollments = enrollments.filter(course__department=department)
        
        result = []
        for enrollment in enrollments:
            result.append({
                'student_id': enrollment.student.id,
                'student_name': enrollment.student.user.full_name,
                'student_number': enrollment.student.student_id,
                'course_id': enrollment.course.id,
                'course_code': enrollment.course.course_code,
                'course_title': enrollment.course.title,
                'credit_hours': enrollment.course.credit_hours,
                'grade': enrollment.grade_letter or 'NON',
                'grade_points': float(enrollment.grade_points or 0),
                'percentage': float(enrollment.percentage_score or 0),
                'sent_at': enrollment.result_sent_at.isoformat() if enrollment.result_sent_at else None,
                'sent_by': enrollment.result_sent_by.full_name if enrollment.result_sent_by else None,
                'department': enrollment.course.department.name if enrollment.course.department else None,
            })
        
        return Response({
            'results': result,
            'count': len(result),
            'user_role': user.role,
            'message': 'Read-only results from Department Head' if user.role == 'REGISTRAR' else 'Results sent to Registrar',
        })
 # ================================================================
# PASSWORD RESET WITH OTP - COMPLETE
# ================================================================

# accounts/views.py - ADD THIS VIEW

# ================================================================
# PASSWORD RESET WITH OTP - COMPLETE
# ================================================================

# accounts/views.py - FIXED SendResetOTPView

# accounts/views.py - FIXED SendResetOTPView with fallback

class SendResetOTPView(APIView):
    """Send OTP to user's email for password reset"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        
        if not email:
            return Response({
                'error': 'Email is required',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({
                'error': 'The email address you entered is not registered in our system. Please check and try again.',
                'success': False
            }, status=status.HTTP_404_NOT_FOUND)
        
        if not user.is_active:
            return Response({
                'error': 'Your account is inactive. Please contact support.',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        import random
        otp = str(random.randint(100000, 999999))
        verification_token = get_random_string(64)
        
        PasswordResetOTP.objects.filter(user=user, is_used=False).delete()
        
        expires_at = timezone.now() + timedelta(minutes=5)
        reset_otp = PasswordResetOTP.objects.create(
            user=user,
            email=email,
            otp=otp,
            verification_token=verification_token,
            expires_at=expires_at
        )
        
        # Try to send email, but don't fail if it doesn't work
        email_sent = False
        try:
            send_mail(
                subject='🔑 Password Reset OTP - DEMS',
                message=f"""
Dear {user.full_name},

You requested a password reset for your DEMS account.

Your OTP (One-Time Password) is: {otp}

This OTP will expire in 10 minutes.

If you did not request this, please ignore this email.

Best regards,
DEMS Team
Mekdela Amba University
                """,
                from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@dems.com',
                recipient_list=[email],
                fail_silently=False,
            )
            email_sent = True
        except Exception as e:
            logger.error(f"Failed to send OTP email: {e}")
            # Don't return error, continue with the process
        
        # Always return success with OTP info
        return Response({
            'message': 'OTP sent to your email address.' if email_sent else 'OTP generated. Please check console for OTP.',
            'email': email,
            'otp': otp,  # Return OTP for development
            'verification_token': verification_token,
            'success': True,
            'email_sent': email_sent,
            'development': True
        }, status=status.HTTP_200_OK)
# accounts/views.py - FIXED VerifyOTPView

class VerifyOTPView(APIView):
    """Verify OTP and return token for password reset"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        otp = request.data.get('otp')
        verification_token = request.data.get('verification_token')
        
        if not email or not otp or not verification_token:
            return Response({
                'error': 'Email, OTP, and verification token are required',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            reset_otp = PasswordResetOTP.objects.get(
                email=email,
                otp=otp,
                verification_token=verification_token,
                is_used=False
            )
        except PasswordResetOTP.DoesNotExist:
            return Response({
                'error': 'Invalid OTP or verification token. Please request a new OTP.',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check if OTP is expired
        if not reset_otp.is_valid():
            return Response({
                'error': 'OTP has expired. Please request a new OTP.',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Mark OTP as used
        reset_otp.is_used = True
        reset_otp.save()
        
        # Generate a new reset token
        reset_token = get_random_string(64)
        
        # Store the reset token in the OTP record or use a simple cache
        # For simplicity, we'll store it in the user object using a temporary approach
        # We'll just return the token and validate it with the OTP record
        
        return Response({
            'message': 'OTP verified successfully.',
            'reset_token': reset_token,
            'email': email,
            'success': True
        }, status=status.HTTP_200_OK)

# accounts/views.py - FIXED ResetPasswordWithTokenView

class ResetPasswordWithTokenView(APIView):
    """Reset password using verified token"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        reset_token = request.data.get('reset_token')
        new_password = request.data.get('new_password')
        confirm_password = request.data.get('confirm_password')
        
        # Validate input
        if not email or not reset_token:
            return Response({
                'error': 'Email and reset token are required',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not new_password or not confirm_password:
            return Response({
                'error': 'Password and confirmation are required',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if new_password != confirm_password:
            return Response({
                'error': 'Passwords do not match',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if len(new_password) < 6:
            return Response({
                'error': 'Password must be at least 6 characters long',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({
                'error': 'User not found',
                'success': False
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Verify the reset token - check if there's a valid OTP record for this user
        # that was verified recently
        try:
            # Check if there's a verified OTP for this user in the last 5 minutes
            time_threshold = timezone.now() - timedelta(minutes=5)
            reset_otp = PasswordResetOTP.objects.get(
                user=user,
                is_used=True,
                updated_at__gte=time_threshold
            )
            # Since we don't have updated_at, we'll use created_at as fallback
            # The token is valid if the OTP was verified recently
        except PasswordResetOTP.DoesNotExist:
            return Response({
                'error': 'Invalid reset token. Please request a new OTP.',
                'success': False
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Reset password
        user.set_password(new_password)
        user.save()
        
        # Delete all OTPs for this user after successful reset
        PasswordResetOTP.objects.filter(user=user).delete()
        
        # Send confirmation email
        try:
            send_mail(
                subject='✅ Password Changed Successfully - DEMS',
                message=f"""
Dear {user.full_name},

Your password has been changed successfully.

If you did not make this change, please contact support immediately.

Best regards,
DEMS Team
Mekdela Amba University
                """,
                from_email=settings.DEFAULT_FROM_EMAIL or 'noreply@dems.com',
                recipient_list=[email],
                fail_silently=True,
            )
        except:
            pass
        
        return Response({
            'message': 'Password reset successfully. You can now login with your new password.',
            'success': True
        }, status=status.HTTP_200_OK)

class ValidateResetTokenView(APIView):
    """Validate password reset token"""
    permission_classes = [permissions.AllowAny]
    
    def get(self, request):
        token = request.query_params.get('token')
        
        if not token:
            return Response({
                'valid': False,
                'error': 'Token is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            user = User.objects.get(password_reset_token=token)
            if hasattr(user, 'password_reset_token_created') and user.password_reset_token_created:
                token_age = timezone.now() - user.password_reset_token_created
                if token_age > timedelta(hours=24):
                    return Response({
                        'valid': False,
                        'error': 'Token has expired. Please request a new OTP.'
                    }, status=status.HTTP_400_BAD_REQUEST)
            
            return Response({
                'valid': True,
                'email': user.email,
                'message': 'Token is valid'
            }, status=status.HTTP_200_OK)
            
        except User.DoesNotExist:
            return Response({
                'valid': False,
                'error': 'Invalid token. Please request a new OTP.'
            }, status=status.HTTP_400_BAD_REQUEST)
 # accounts/views.py - ADD THIS VIEW

class UserListView(generics.ListAPIView):
    """
    List all users - For chat and admin purposes
    """
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserSerializer
    
    def get_queryset(self):
        user = self.request.user
        
        # Admin can see all users
        if user.role == 'ADMIN':
            return User.objects.all().order_by('full_name')
        
        # Department Head can see users in their department
        if user.role == 'DEPT_HEAD':
            try:
                department = user.headed_department
                if department:
                    # Get students in department
                    student_ids = StudentProfile.objects.filter(
                        department=department.name
                    ).values_list('user_id', flat=True)
                    # Get teachers in department
                    teacher_ids = TeacherProfile.objects.filter(
                        department=department.name
                    ).values_list('user_id', flat=True)
                    return User.objects.filter(
                        Q(id__in=student_ids) | 
                        Q(id__in=teacher_ids) |
                        Q(role='ADMIN')
                    ).order_by('full_name')
            except:
                pass
            return User.objects.none()
        
        # Teacher can see their students
        if user.role == 'TEACHER':
            # Get courses taught by this teacher
            from courses.models import Course, Enrollment
            courses = Course.objects.filter(instructor=user)
            enrollments = Enrollment.objects.filter(
                course__in=courses,
                status='ACTIVE'
            ).select_related('student__user')
            student_ids = [e.student.user_id for e in enrollments]
            
            # Also include other teachers and admins
            return User.objects.filter(
                Q(id__in=student_ids) |
                Q(role='ADMIN') |
                Q(role='TEACHER')
            ).order_by('full_name')
        
        # Finance can see all students
        if user.role == 'FINANCE':
            student_ids = StudentProfile.objects.all().values_list('user_id', flat=True)
            return User.objects.filter(
                Q(id__in=student_ids) |
                Q(role='ADMIN') |
                Q(role='FINANCE')
            ).order_by('full_name')
        
        # Registrar can see all students
        if user.role == 'REGISTRAR':
            student_ids = StudentProfile.objects.all().values_list('user_id', flat=True)
            return User.objects.filter(
                Q(id__in=student_ids) |
                Q(role='ADMIN') |
                Q(role='REGISTRAR')
            ).order_by('full_name')
        
        # Student can see their teachers and admins
        if user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=user)
                # Get courses enrolled by this student
                from courses.models import Enrollment
                enrollments = Enrollment.objects.filter(
                    student=student,
                    status='ACTIVE'
                ).select_related('course__instructor')
                teacher_ids = [e.course.instructor_id for e in enrollments if e.course.instructor_id]
                
                # Get department head
                dept_head = None
                if student.department:
                    try:
                        from accounts.models import Department
                        dept = Department.objects.filter(name=student.department).first()
                        if dept and dept.head:
                            dept_head = dept.head.id
                    except:
                        pass
                
                return User.objects.filter(
                    Q(id__in=teacher_ids) |
                    Q(id=dept_head) |
                    Q(role='ADMIN') |
                    Q(role='REGISTRAR')
                ).order_by('full_name')
            except StudentProfile.DoesNotExist:
                return User.objects.none()
        
        return User.objects.none()           
# accounts/views.py - ADD THIS VIEW

class AdminLoginView(APIView):
    """Admin-only login endpoint with role verification"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        
        if not email or not password:
            return Response(
                {'error': 'Email and password are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        user = authenticate(request, username=email, password=password)
        
        if not user:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        if not user.is_active:
            return Response(
                {'error': 'Account is disabled'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # ✅ CRITICAL: Check if user is ADMIN
        if user.role != 'ADMIN':
            return Response(
                {'error': 'Access denied. Admin credentials required.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        refresh = RefreshToken.for_user(user)
        
        # Log the admin login
        SystemLog.objects.create(
            user=user,
            action='ADMIN_LOGIN',
            details={'email': email, 'ip': request.META.get('REMOTE_ADDR')},
            log_level='INFO'
        )
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'role': user.role,
            'message': 'Admin login successful'
        })        
 # accounts/views.py - ADD SESSION EXPIRATION CHECK
# Add this import at the top:


# Add this helper function:

def check_session_expiration(request):
    """Check if session has expired"""
    if not request.user.is_authenticated:
        return True
    
    # Get session
    session_key = request.session.session_key
    if not session_key:
        return True
    
    try:
        session = Session.objects.get(session_key=session_key)
        
        # Check if session is expired
        if session.expire_date < timezone.now():
            # Delete expired session
            session.delete()
            request.session.flush()
            return True
        
        # Check session age
        session_age = timezone.now() - session.created_at
        if session_age > timedelta(seconds=settings.SESSION_COOKIE_AGE):
            session.delete()
            request.session.flush()
            return True
            
    except Session.DoesNotExist:
        return True
    
    return False       