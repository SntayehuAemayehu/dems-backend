# courses/views.py - COMPLETE FIXED VERSION
# With proper assignment viewing for students

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Q
from django.utils import timezone
from .models import Course, CourseMaterial, Enrollment, Assignment, AssignmentSubmission
from .serializers import (
    CourseSerializer, CourseMaterialSerializer, EnrollmentSerializer,
    AssignmentSerializer, AssignmentSubmissionSerializer
)
from accounts.models import StudentProfile, Department
from notifications.utils import send_notification
import os
from rest_framework.views import APIView
import magic
from django.core.files.storage import default_storage


class CourseListView(generics.ListCreateAPIView):
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Course.objects.filter(is_active=True)
        
        if user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=user)
                if student.is_enrolled:
                    queryset = queryset.filter(
                        department__name=student.department,
                        is_approved=True
                    )
                else:
                    return Course.objects.none()
            except StudentProfile.DoesNotExist:
                return Course.objects.none()
        
        elif user.role == 'TEACHER':
            queryset = queryset.filter(instructor=user)
        
        elif user.role == 'DEPT_HEAD':
            try:
                department = user.headed_department
                queryset = queryset.filter(department=department)
            except:
                pass
        
        return queryset.order_by('course_code')
    
    def create(self, request, *args, **kwargs):
        if request.user.role not in ['TEACHER', 'ADMIN', 'DEPT_HEAD']:
            return Response(
                {'error': 'Only teachers, admins, and department heads can create courses'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        data = request.data.copy()
        
        if request.user.role == 'DEPT_HEAD':
            data['is_approved'] = True
            data['approved_by'] = request.user.id
            try:
                department = request.user.headed_department
                if department:
                    data['department'] = department.id
            except:
                pass
        
        if request.user.role == 'ADMIN':
            data['is_approved'] = True
        
        if not data.get('instructor'):
            data['instructor'] = request.user.id
        
        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save(instructor=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CourseDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=user)
                if student.is_enrolled:
                    return Course.objects.filter(department__name=student.department)
                return Course.objects.none()
            except:
                return Course.objects.none()
        return Course.objects.all()
    
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        data = serializer.data
        
        # ✅ Add assignments for this course
        assignments = Assignment.objects.filter(course=instance).order_by('due_date')
        assignment_serializer = AssignmentSerializer(assignments, many=True)
        
        # ✅ If student, add submission status
        if request.user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=request.user)
                for assignment in assignment_serializer.data:
                    has_submitted = AssignmentSubmission.objects.filter(
                        assignment_id=assignment['id'],
                        student=student
                    ).exists()
                    assignment['has_submitted'] = has_submitted
                    if has_submitted:
                        submission = AssignmentSubmission.objects.get(
                            assignment_id=assignment['id'],
                            student=student
                        )
                        assignment['submission_id'] = submission.id
                        assignment['submitted_at'] = submission.submitted_at.isoformat() if submission.submitted_at else None
                        assignment['marks_obtained'] = float(submission.marks_obtained) if submission.marks_obtained is not None else None
                        assignment['feedback'] = submission.feedback or ''
                        assignment['submission_status'] = 'submitted'
                    else:
                        assignment['submission_status'] = 'pending'
            except StudentProfile.DoesNotExist:
                pass
        
        data['assignments'] = assignment_serializer.data
        data['assignments_count'] = len(assignment_serializer.data)
        
        return Response(data)
    
    def destroy(self, request, *args, **kwargs):
        course = self.get_object()
        if request.user.role != 'ADMIN' and course.instructor != request.user:
            return Response(
                {'error': 'You do not have permission to delete this course'},
                status=status.HTTP_403_FORBIDDEN
            )
        course.is_active = False
        course.save()
        return Response({'message': 'Course deleted successfully'}, status=status.HTTP_200_OK)


class CourseMaterialView(generics.ListCreateAPIView):
    serializer_class = CourseMaterialSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        course_id = self.kwargs.get('course_id')
        user = self.request.user
        
        if user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=user)
                if student.is_enrolled and Enrollment.objects.filter(student=student, course_id=course_id, status='ACTIVE').exists():
                    return CourseMaterial.objects.filter(course_id=course_id)
                return CourseMaterial.objects.none()
            except StudentProfile.DoesNotExist:
                return CourseMaterial.objects.none()
        
        return CourseMaterial.objects.filter(course_id=course_id)
    
    def create(self, request, *args, **kwargs):
        course_id = self.kwargs.get('course_id')
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if request.user.role != 'ADMIN' and course.instructor != request.user:
            return Response(
                {'error': 'You do not have permission to upload materials to this course'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if 'file' not in request.FILES:
            return Response(
                {'error': 'File is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        file = request.FILES['file']
        
        max_size = 500 * 1024 * 1024
        if file.size > max_size:
            return Response(
                {'error': f'File size exceeds {max_size // (1024*1024)}MB limit'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        material_type = request.data.get('material_type', 'OTHER')
        
        if file.name:
            ext = file.name.split('.')[-1].lower()
            video_extensions = ['mp4', 'webm', 'mov', 'avi', 'mkv', 'flv', 'wmv', 'm4v', '3gp', 'mpg', 'mpeg']
            image_extensions = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg']
            audio_extensions = ['mp3', 'wav', 'aac', 'ogg', 'm4a', 'flac', 'wma']
            
            if ext in video_extensions:
                material_type = 'VIDEO'
            elif ext in image_extensions:
                material_type = 'IMAGE'
            elif ext in audio_extensions:
                material_type = 'AUDIO'
            elif ext == 'pdf':
                material_type = 'PDF'
            elif ext in ['ppt', 'pptx']:
                material_type = 'SLIDE'
            elif ext in ['doc', 'docx']:
                material_type = 'DOC'
        
        data = request.data.copy()
        data['course'] = course.id
        data['uploaded_by'] = request.user.id
        data['material_type'] = material_type
        
        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save(course=course, uploaded_by=request.user)
        
        enrollments = Enrollment.objects.filter(course=course, status='ACTIVE')
        for enrollment in enrollments:
            send_notification(
                recipient_user=enrollment.student.user,
                title='📚 New Course Material Uploaded',
                message=f'New {material_type.lower()} "{data.get("title")}" has been uploaded to {course.title}.',
                notification_type='SYSTEM_ALERT',
                link=f'/courses/{course.id}'
            )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CourseMaterialDetailView(generics.RetrieveDestroyAPIView):
    queryset = CourseMaterial.objects.all()
    serializer_class = CourseMaterialSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def destroy(self, request, *args, **kwargs):
        material = self.get_object()
        if request.user.role != 'ADMIN' and material.uploaded_by != request.user:
            return Response(
                {'error': 'You do not have permission to delete this material'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if material.file:
            try:
                os.remove(material.file.path)
            except:
                pass
        
        material.delete()
        return Response({'message': 'Material deleted successfully'}, status=status.HTTP_200_OK)


class EnrollmentView(generics.ListCreateAPIView):
    serializer_class = EnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'STUDENT':
            return Enrollment.objects.filter(student__user=user)
        elif user.role == 'TEACHER':
            return Enrollment.objects.filter(course__instructor=user)
        elif user.role == 'REGISTRAR':
            return Enrollment.objects.all()
        elif user.role == 'DEPT_HEAD':
            try:
                department = user.headed_department
                return Enrollment.objects.filter(course__department=department)
            except:
                return Enrollment.objects.none()
        elif user.role in ['ADMIN']:
            return Enrollment.objects.all()
        return Enrollment.objects.none()
    
    def create(self, request, *args, **kwargs):
        if request.user.role != 'STUDENT':
            return Response({'error': 'Only students can enroll'}, status=status.HTTP_403_FORBIDDEN)
        
        course_id = request.data.get('course')
        
        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not student.is_enrolled:
            return Response({'error': 'Your account is not activated. Please contact registrar.'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if course.department.name != student.department:
            return Response({'error': 'You can only enroll in courses within your department'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if Enrollment.objects.filter(student=student, course=course).exists():
            return Response({'error': 'Already enrolled'}, status=status.HTTP_400_BAD_REQUEST)
        
        if student.payment_status != 'VERIFIED':
            return Response({'error': 'Payment not verified'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not course.is_approved:
            return Response({'error': 'Course is not approved yet'}, status=status.HTTP_400_BAD_REQUEST)
        
        if course.enrolled_count >= course.capacity:
            return Response({'error': 'Course is full'}, status=status.HTTP_400_BAD_REQUEST)
        
        enrollment = Enrollment.objects.create(student=student, course=course, status='ACTIVE')
        serializer = self.get_serializer(enrollment)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class CourseApprovalView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, course_id):
        if request.user.role not in ['DEPT_HEAD', 'ADMIN']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if request.user.role == 'DEPT_HEAD':
            try:
                if course.department != request.user.headed_department:
                    return Response({'error': 'You can only approve courses in your department'}, 
                                  status=status.HTTP_403_FORBIDDEN)
            except:
                return Response({'error': 'You are not assigned to any department'}, 
                              status=status.HTTP_403_FORBIDDEN)
        
        action = request.data.get('action')
        if action == 'approve':
            course.is_approved = True
            course.approved_by = request.user
            course.save()
            
            if course.instructor:
                send_notification(
                    recipient_user=course.instructor,
                    title='✅ Course Approved',
                    message=f'Your course "{course.title}" has been approved.',
                    notification_type='COURSE_APPROVED'
                )
            
            return Response({'message': 'Course approved successfully'})
        elif action == 'reject':
            course.is_active = False
            course.save()
            return Response({'message': 'Course rejected'})
        
        return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)


class DeptStudentListView(generics.ListAPIView):
    serializer_class = EnrollmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.role != 'DEPT_HEAD':
            return Enrollment.objects.none()
        try:
            department = user.headed_department
            if department:
                return Enrollment.objects.filter(
                    course__department=department,
                    status='ACTIVE'
                ).select_related('student__user', 'course')
            return Enrollment.objects.none()
        except:
            return Enrollment.objects.none()


class DeptCourseListView(generics.ListCreateAPIView):
    serializer_class = CourseSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        queryset = Course.objects.filter(is_active=True)
        
        if user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=user)
                if student.is_enrolled:
                    queryset = queryset.filter(
                        department__name=student.department,
                        is_approved=True
                    )
                else:
                    return Course.objects.none()
            except StudentProfile.DoesNotExist:
                return Course.objects.none()
        
        elif user.role == 'TEACHER':
            queryset = queryset.filter(instructor=user)
        
        elif user.role == 'DEPT_HEAD':
            try:
                department = user.headed_department
                queryset = queryset.filter(department=department)
            except:
                pass
        
        return queryset.order_by('course_code')
    
    def create(self, request, *args, **kwargs):
        if request.user.role not in ['TEACHER', 'ADMIN', 'DEPT_HEAD']:
            return Response(
                {'error': 'Only teachers, admins, and department heads can create courses'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        data = request.data.copy()
        
        if request.user.role == 'DEPT_HEAD':
            try:
                department = request.user.headed_department
                if department:
                    data['department'] = department.id
                    data['is_approved'] = True
                    data['approved_by'] = request.user.id
            except:
                pass
        
        if request.user.role == 'ADMIN':
            data['is_approved'] = True
        
        if not data.get('instructor'):
            data['instructor'] = request.user.id
        
        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save(instructor=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class StartLiveClassView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, course_id):
        if request.user.role != 'TEACHER':
            return Response({'error': 'Only teachers can start live classes'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if course.instructor != request.user:
            return Response({'error': 'You do not own this course'}, status=status.HTTP_403_FORBIDDEN)
        
        course.is_active = True
        course.save()
        
        enrollments = Enrollment.objects.filter(course=course, status='ACTIVE')
        for enrollment in enrollments:
            send_notification(
                recipient_user=enrollment.student.user,
                title='🎥 Live Class Started',
                message=f'The live class for {course.title} has started! Join now.',
                notification_type='LIVE_CLASS_STARTED',
                link=f'/live-class/{course.id}'
            )
        
        return Response({
            'message': 'Live class started successfully',
            'course_id': course.id
        }, status=status.HTTP_200_OK)


# ============= ASSIGNMENT VIEWS WITH VIDEO SUPPORT =============

class AssignmentListView(generics.ListCreateAPIView):
    serializer_class = AssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        course_id = self.kwargs.get('course_id')
        user = self.request.user
        
        if user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=user)
                if student.is_enrolled and Enrollment.objects.filter(student=student, course_id=course_id, status='ACTIVE').exists():
                    return Assignment.objects.filter(course_id=course_id)
                return Assignment.objects.none()
            except StudentProfile.DoesNotExist:
                return Assignment.objects.none()
        
        return Assignment.objects.filter(course_id=course_id)
    
    def create(self, request, *args, **kwargs):
        course_id = self.kwargs.get('course_id')
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if request.user.role != 'ADMIN' and course.instructor != request.user:
            return Response(
                {'error': 'You do not have permission to create assignments for this course'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        data = request.data.copy()
        data['course'] = course.id
        data['created_by'] = request.user.id
        
        if 'video_attachment' in request.FILES:
            video_file = request.FILES['video_attachment']
            max_size = 500 * 1024 * 1024
            if video_file.size > max_size:
                return Response(
                    {'error': f'Video file size exceeds {max_size // (1024*1024)}MB limit'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            data['video_attachment'] = video_file
            data['assignment_type'] = 'VIDEO'
        
        if 'attachment' in request.FILES:
            data['attachment'] = request.FILES['attachment']
        
        if request.data.get('link_url'):
            data['link_url'] = request.data.get('link_url')
            if not data.get('assignment_type') or data.get('assignment_type') == 'DOCUMENT':
                data['assignment_type'] = 'LINK'
        
        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save(course=course, created_by=request.user)
        
        enrollments = Enrollment.objects.filter(course=course, status='ACTIVE')
        for enrollment in enrollments:
            send_notification(
                recipient_user=enrollment.student.user,
                title='📝 New Assignment Posted',
                message=f'New assignment "{data.get("title")}" has been posted for {course.title}. Due: {data.get("due_date")}',
                notification_type='SYSTEM_ALERT',
                link=f'/courses/{course.id}'
            )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AssignmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Assignment.objects.all()
    serializer_class = AssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def destroy(self, request, *args, **kwargs):
        assignment = self.get_object()
        if request.user.role != 'ADMIN' and assignment.created_by != request.user:
            return Response(
                {'error': 'You do not have permission to delete this assignment'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)


class AssignmentSubmissionView(generics.ListCreateAPIView):
    serializer_class = AssignmentSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        assignment_id = self.kwargs.get('assignment_id')
        user = self.request.user
        
        queryset = AssignmentSubmission.objects.filter(assignment_id=assignment_id)
        
        if user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=user)
                queryset = queryset.filter(student=student)
            except StudentProfile.DoesNotExist:
                return AssignmentSubmission.objects.none()
        
        return queryset
    
    def create(self, request, *args, **kwargs):
        assignment_id = self.kwargs.get('assignment_id')
        
        try:
            assignment = Assignment.objects.get(id=assignment_id)
        except Assignment.DoesNotExist:
            return Response({'error': 'Assignment not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if request.user.role != 'STUDENT':
            return Response({'error': 'Only students can submit assignments'}, status=status.HTTP_403_FORBIDDEN)
        
        if timezone.now() > assignment.due_date:
            return Response({'error': 'Assignment submission deadline has passed'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if AssignmentSubmission.objects.filter(assignment=assignment, student=student).exists():
            return Response({'error': 'You have already submitted this assignment'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        data = request.data.copy()
        data['assignment'] = assignment.id
        data['student'] = student.id
        
        if 'submission_video' in request.FILES:
            video_file = request.FILES['submission_video']
            max_size = 500 * 1024 * 1024
            if video_file.size > max_size:
                return Response(
                    {'error': f'Video file size exceeds {max_size // (1024*1024)}MB limit'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            data['submission_video'] = video_file
            data['submission_type'] = 'VIDEO'
        
        if 'submission_file' in request.FILES:
            file = request.FILES['submission_file']
            if file.size > 50 * 1024 * 1024:
                return Response({'error': 'File size exceeds 50MB limit'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            data['submission_file'] = file
            if not data.get('submission_type') or data.get('submission_type') == 'VIDEO':
                data['submission_type'] = 'FILE'
        
        if request.data.get('submission_link'):
            data['submission_link'] = request.data.get('submission_link')
            if not data.get('submission_type') or data.get('submission_type') in ['FILE', 'VIDEO']:
                data['submission_type'] = 'LINK'
        
        if request.data.get('submission_text'):
            data['submission_text'] = request.data.get('submission_text')
            if not data.get('submission_type') or data.get('submission_type') in ['FILE', 'VIDEO', 'LINK']:
                data['submission_type'] = 'TEXT'
        
        if not any([
            data.get('submission_file'), 
            data.get('submission_video'), 
            data.get('submission_text'), 
            data.get('submission_link')
        ]):
            return Response(
                {'error': 'Please provide a submission (file, video, text, or link)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save(assignment=assignment, student=student)
        
        send_notification(
            recipient_user=assignment.created_by,
            title='📄 Assignment Submitted',
            message=f'Student {student.user.full_name} has submitted "{assignment.title}"',
            notification_type='SYSTEM_ALERT',
            link=f'/teacher/courses/{assignment.course.id}'
        )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class GradeAssignmentView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, submission_id):
        if request.user.role not in ['TEACHER', 'ADMIN']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            submission = AssignmentSubmission.objects.get(id=submission_id)
        except AssignmentSubmission.DoesNotExist:
            return Response({'error': 'Submission not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if request.user.role != 'ADMIN' and submission.assignment.created_by != request.user:
            return Response(
                {'error': 'You do not have permission to grade this submission'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        marks = request.data.get('marks_obtained')
        feedback = request.data.get('feedback', '')
        
        if marks is None:
            return Response({'error': 'Marks are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            marks = float(marks)
            if marks < 0 or marks > float(submission.assignment.total_marks):
                return Response(
                    {'error': f'Marks must be between 0 and {submission.assignment.total_marks}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except:
            return Response({'error': 'Invalid marks value'}, status=status.HTTP_400_BAD_REQUEST)
        
        submission.marks_obtained = marks
        submission.feedback = feedback
        submission.graded_by = request.user
        submission.graded_at = timezone.now()
        submission.save()
        
        send_notification(
            recipient_user=submission.student.user,
            title='✅ Assignment Graded',
            message=f'Your submission for "{submission.assignment.title}" has been graded. Marks: {marks}/{submission.assignment.total_marks}',
            notification_type='GRADE_RELEASED',
            link=f'/courses/{submission.assignment.course.id}'
        )
        
        return Response({
            'message': 'Assignment graded successfully',
            'marks_obtained': marks,
            'feedback': feedback
        })


class StudentCourseMaterialsView(generics.ListAPIView):
    serializer_class = CourseMaterialSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        course_id = self.kwargs.get('course_id')
        user = self.request.user
        
        if user.role != 'STUDENT':
            return CourseMaterial.objects.none()
        
        try:
            student = StudentProfile.objects.get(user=user)
            if student.is_enrolled and Enrollment.objects.filter(student=student, course_id=course_id, status='ACTIVE').exists():
                return CourseMaterial.objects.filter(course_id=course_id)
            return CourseMaterial.objects.none()
        except StudentProfile.DoesNotExist:
            return CourseMaterial.objects.none()


class StudentCourseAssignmentsView(generics.ListAPIView):
    """Get assignments for a student enrolled in a course"""
    serializer_class = AssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        course_id = self.kwargs.get('course_id')
        user = self.request.user
        
        if user.role != 'STUDENT':
            return Assignment.objects.none()
        
        try:
            student = StudentProfile.objects.get(user=user)
            if student.is_enrolled and Enrollment.objects.filter(
                student=student, 
                course_id=course_id, 
                status='ACTIVE'
            ).exists():
                return Assignment.objects.filter(
                    course_id=course_id
                ).order_by('due_date')
            return Assignment.objects.none()
        except StudentProfile.DoesNotExist:
            return Assignment.objects.none()
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        result = []
        try:
            student = StudentProfile.objects.get(user=request.user)
            for assignment_data in serializer.data:
                assignment_id = assignment_data['id']
                has_submitted = AssignmentSubmission.objects.filter(
                    assignment_id=assignment_id,
                    student=student
                ).exists()
                
                submission = AssignmentSubmission.objects.filter(
                    assignment_id=assignment_id,
                    student=student
                ).first()
                
                assignment_data['has_submitted'] = has_submitted
                assignment_data['submission_id'] = submission.id if submission else None
                assignment_data['submission_status'] = 'submitted' if has_submitted else 'pending'
                assignment_data['submitted_at'] = submission.submitted_at.isoformat() if submission and submission.submitted_at else None
                assignment_data['marks_obtained'] = float(submission.marks_obtained) if submission and submission.marks_obtained is not None else None
                assignment_data['feedback'] = submission.feedback if submission else ''
                
                result.append(assignment_data)
        except StudentProfile.DoesNotExist:
            pass
        
        return Response(result)


class StudentAssignmentSubmissionView(generics.CreateAPIView):
    serializer_class = AssignmentSubmissionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        assignment_id = self.kwargs.get('assignment_id')
        
        if request.user.role != 'STUDENT':
            return Response({'error': 'Only students can submit assignments'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            assignment = Assignment.objects.get(id=assignment_id)
        except Assignment.DoesNotExist:
            return Response({'error': 'Assignment not found'}, status=status.HTTP_404_NOT_FOUND)
        
        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if not student.is_enrolled:
            return Response({'error': 'Your account is not activated'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not Enrollment.objects.filter(student=student, course=assignment.course, status='ACTIVE').exists():
            return Response({'error': 'You are not enrolled in this course'}, status=status.HTTP_403_FORBIDDEN)
        
        if timezone.now() > assignment.due_date:
            return Response({'error': 'Assignment submission deadline has passed'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        if AssignmentSubmission.objects.filter(assignment=assignment, student=student).exists():
            return Response({'error': 'You have already submitted this assignment'}, 
                          status=status.HTTP_400_BAD_REQUEST)
        
        data = request.data.copy()
        data['assignment'] = assignment.id
        data['student'] = student.id
        
        if 'submission_video' in request.FILES:
            video_file = request.FILES['submission_video']
            max_size = 500 * 1024 * 1024
            if video_file.size > max_size:
                return Response(
                    {'error': f'Video file size exceeds {max_size // (1024*1024)}MB limit'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            data['submission_video'] = video_file
            data['submission_type'] = 'VIDEO'
        
        if 'submission_file' in request.FILES:
            file = request.FILES['submission_file']
            if file.size > 50 * 1024 * 1024:
                return Response({'error': 'File size exceeds 50MB limit'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            data['submission_file'] = file
            if not data.get('submission_type'):
                data['submission_type'] = 'FILE'
        
        if request.data.get('submission_link'):
            data['submission_link'] = request.data.get('submission_link')
            if not data.get('submission_type'):
                data['submission_type'] = 'LINK'
        
        if request.data.get('submission_text'):
            data['submission_text'] = request.data.get('submission_text')
            if not data.get('submission_type'):
                data['submission_type'] = 'TEXT'
        
        if not any([
            data.get('submission_file'), 
            data.get('submission_video'), 
            data.get('submission_text'), 
            data.get('submission_link')
        ]):
            return Response(
                {'error': 'Please provide a submission (file, video, text, or link)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save(assignment=assignment, student=student)
        
        send_notification(
            recipient_user=assignment.created_by,
            title='📄 Assignment Submitted',
            message=f'Student {student.user.full_name} has submitted "{assignment.title}"',
            notification_type='SYSTEM_ALERT',
            link=f'/teacher/courses/{assignment.course.id}'
        )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
        # Add this class to courses/views.py

class StudentAssignmentResultsView(APIView):
    """Get assignment results for the logged-in student"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return Response([], status=status.HTTP_200_OK)
        
        # Get all assignment submissions for this student
        submissions = AssignmentSubmission.objects.filter(
            student=student
        ).select_related('assignment', 'assignment__course')
        
        results = []
        for submission in submissions:
            results.append({
                'id': submission.id,
                'title': submission.assignment.title,
                'course_title': submission.assignment.course.title,
                'course_code': submission.assignment.course.course_code,
                'total_marks': float(submission.assignment.total_marks),
                'marks_obtained': float(submission.marks_obtained) if submission.marks_obtained is not None else None,
                'feedback': submission.feedback or '',
                'submitted_at': submission.submitted_at.isoformat() if submission.submitted_at else None,
                'due_date': submission.assignment.due_date.isoformat() if submission.assignment.due_date else None,
                'is_graded': submission.marks_obtained is not None,
            })
        
        return Response(results, status=status.HTTP_200_OK)
 # courses/views.py - ADD COURSE GRADE VIEW

class CourseGradeView(APIView):
    """Get student's grade for a specific course"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, course_id):
        user = request.user
        
        if user.role != 'STUDENT':
            return Response({'error': 'Only students can view course grades'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        try:
            student = StudentProfile.objects.get(user=user)
            enrollment = Enrollment.objects.get(
                student=student,
                course_id=course_id
            )
            
            # Update grade if needed
            enrollment.update_course_grade()
            
            return Response({
                'course_id': enrollment.course.id,
                'course_code': enrollment.course.course_code,
                'course_title': enrollment.course.title,
                'credit_hours': enrollment.course.credit_hours,
                'total_marks_obtained': float(enrollment.total_marks_obtained) if enrollment.total_marks_obtained else 0,
                'total_marks_possible': float(enrollment.total_marks_possible) if enrollment.total_marks_possible else 0,
                'percentage': float(enrollment.percentage_score) if enrollment.percentage_score else 0,
                'grade_letter': enrollment.grade_letter or 'NON',
                'grade_points': float(enrollment.grade_points) if enrollment.grade_points else 0,
                'status': enrollment.status,
                'cgpa': float(student.cgpa) if student.cgpa else 0,
            })
            
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=status.HTTP_404_NOT_FOUND)
        except Enrollment.DoesNotExist:
            return Response({'error': 'Not enrolled in this course'}, status=status.HTTP_404_NOT_FOUND)


class StudentAllCourseGradesView(APIView):
    """Get all course grades for a student"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        if user.role != 'STUDENT':
            return Response({'error': 'Only students can view grades'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        try:
            student = StudentProfile.objects.get(user=user)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        enrollments = Enrollment.objects.filter(
            student=student
        ).select_related('course')
        
        results = []
        for enrollment in enrollments:
            enrollment.update_course_grade()
            
            results.append({
                'course_id': enrollment.course.id,
                'course_code': enrollment.course.course_code,
                'course_title': enrollment.course.title,
                'credit_hours': enrollment.course.credit_hours,
                'total_marks_obtained': float(enrollment.total_marks_obtained) if enrollment.total_marks_obtained else 0,
                'total_marks_possible': float(enrollment.total_marks_possible) if enrollment.total_marks_possible else 0,
                'percentage': float(enrollment.percentage_score) if enrollment.percentage_score else 0,
                'grade_letter': enrollment.grade_letter or 'NON',
                'grade_points': float(enrollment.grade_points) if enrollment.grade_points else 0,
                'status': enrollment.status,
            })
        
        return Response({
            'student_name': student.user.full_name,
            'student_id': student.student_id,
            'department': student.department,
            'cgpa': float(student.cgpa) if student.cgpa else 0,
            'total_credits': student.total_credits,
            'courses': results
        })       
 # courses/views.py - ADD TEACHER COURSE GRADES

class TeacherCourseGradesView(APIView):
    """Get all student grades for a specific course (Teacher only)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, course_id):
        user = request.user
        
        if user.role not in ['TEACHER', 'ADMIN', 'DEPT_HEAD']:
            return Response({'error': 'Permission denied'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        try:
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if teacher owns this course
        if user.role == 'TEACHER' and course.instructor != user:
            return Response({'error': 'You are not the instructor for this course'}, 
                          status=status.HTTP_403_FORBIDDEN)
        
        enrollments = Enrollment.objects.filter(
            course=course
        ).select_related('student__user')
        
        results = []
        for enrollment in enrollments:
            enrollment.update_course_grade()
            
            results.append({
                'student_id': enrollment.student.id,
                'student_name': enrollment.student.user.full_name,
                'student_email': enrollment.student.user.email,
                'student_number': enrollment.student.student_id,
                'total_marks_obtained': float(enrollment.total_marks_obtained) if enrollment.total_marks_obtained else 0,
                'total_marks_possible': float(enrollment.total_marks_possible) if enrollment.total_marks_possible else 0,
                'percentage': float(enrollment.percentage_score) if enrollment.percentage_score else 0,
                'grade_letter': enrollment.grade_letter or 'NON',
                'grade_points': float(enrollment.grade_points) if enrollment.grade_points else 0,
                'status': enrollment.status,
            })
        
        # Calculate class statistics
        completed = [r for r in results if r['status'] == 'COMPLETED']
        if completed:
            avg_percentage = sum(r['percentage'] for r in completed) / len(completed)
            grade_distribution = {}
            for r in completed:
                grade = r['grade_letter']
                grade_distribution[grade] = grade_distribution.get(grade, 0) + 1
        else:
            avg_percentage = 0
            grade_distribution = {}
        
        return Response({
            'course_id': course.id,
            'course_code': course.course_code,
            'course_title': course.title,
            'total_students': enrollments.count(),
            'completed_students': len(completed),
            'average_percentage': round(avg_percentage, 2),
            'grade_distribution': grade_distribution,
            'students': results
        })       