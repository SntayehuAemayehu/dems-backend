# proctoring/views.py - COMPLETE FIXED VERSION
# All existing code preserved, added ProctorCaptureView and AI endpoints

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.core.files.base import ContentFile
from django.conf import settings
import base64
import uuid
import os
from collections import defaultdict
from .models import ProctorImage, ProctorLog, ProctorSession
from .serializers import ProctorImageSerializer, ProctorLogSerializer, ProctorSessionSerializer
from exams.models import ExamAttempt
from accounts.models import StudentProfile
from notifications.utils import send_notification
import logging

logger = logging.getLogger(__name__)


# ============================================================
# EXISTING VIEWS - PRESERVED
# ============================================================

class ProctorImageView(APIView):
    """Capture proctoring image and retrieve images for a session"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, attempt_id):
        """Get all images for a specific attempt"""
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        user = request.user
        if user.role == 'STUDENT':
            try:
                student = user.student_profile
                if attempt.student != student:
                    return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
            except:
                return Response({'error': 'Student profile not found'}, status=status.HTTP_404_NOT_FOUND)
        elif user.role not in ['ADMIN', 'TEACHER', 'DEPT_HEAD']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get images
        images = ProctorImage.objects.filter(attempt=attempt).order_by('-capture_time')
        
        # Build full URLs for images
        result = []
        for img in images:
            image_url = None
            if img.image:
                try:
                    if hasattr(img.image, 'url'):
                        image_url = img.image.url
                    else:
                        image_url = str(img.image)
                except Exception as e:
                    logger.error(f"Error getting image URL: {e}")
                    image_url = None
            
            result.append({
                'id': img.id,
                'image': image_url,
                'capture_time': img.capture_time.isoformat() if img.capture_time else None,
                'is_suspicious': img.is_suspicious,
                'face_detected': img.face_detected,
                'multiple_faces': img.multiple_faces,
                'mobile_detected': img.mobile_detected,
                'suspicious_reason': img.suspicious_reason,
                'flagged_by': img.flagged_by.full_name if img.flagged_by else None,
                'flagged_at': img.flagged_at.isoformat() if img.flagged_at else None,
            })
        
        # Get or create session
        session, created = ProctorSession.objects.get_or_create(attempt=attempt)
        
        return Response({
            'images': result,
            'total': len(result),
            'suspicious_count': images.filter(is_suspicious=True).count(),
            'session': {
                'id': session.id,
                'total_captures': session.total_captures,
                'suspicious_events': session.suspicious_events,
                'review_status': session.review_status,
                'is_active': session.is_active,
            }
        })
    
    def post(self, request, attempt_id):
        """Capture and save a proctoring image"""
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check if user owns this attempt
        if request.user.role == 'STUDENT':
            try:
                student = request.user.student_profile
                if attempt.student != student:
                    return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
            except:
                return Response({'error': 'Student profile not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get image data from request
        image_data = request.data.get('image_data')
        
        if not image_data:
            return Response({'error': 'No image data provided'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Handle base64 image data
        try:
            # Remove data URL prefix if present
            if 'base64,' in image_data:
                format_str, imgstr = image_data.split(';base64,')
                if '/' in format_str:
                    ext = format_str.split('/')[-1]
                else:
                    ext = 'jpg'
                if ext not in ['jpeg', 'jpg', 'png', 'gif', 'webp']:
                    ext = 'jpg'
            else:
                imgstr = image_data
                ext = 'jpg'
            
            # Decode base64
            image_bytes = base64.b64decode(imgstr)
            
            # Validate image
            if not image_bytes or len(image_bytes) < 100:
                return Response({'error': 'Invalid image data - file too small'}, status=status.HTTP_400_BAD_REQUEST)
            
            # Check for common image file signatures
            is_valid_image = False
            if len(image_bytes) > 4:
                if image_bytes[0] == 0xFF and image_bytes[1] == 0xD8 and image_bytes[2] == 0xFF:
                    is_valid_image = True
                    ext = 'jpg'
                elif image_bytes[0] == 0x89 and image_bytes[1] == 0x50 and image_bytes[2] == 0x4E and image_bytes[3] == 0x47:
                    is_valid_image = True
                    ext = 'png'
                elif image_bytes[0] == 0x47 and image_bytes[1] == 0x49 and image_bytes[2] == 0x46:
                    is_valid_image = True
                    ext = 'gif'
                elif image_bytes[0] == 0x52 and image_bytes[1] == 0x49 and image_bytes[2] == 0x46 and image_bytes[3] == 0x46:
                    is_valid_image = True
                    ext = 'webp'
            
            if not is_valid_image:
                ext = 'jpg'
            
            # Create a ContentFile from bytes
            filename = f"proctor_{attempt_id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.{ext}"
            content_file = ContentFile(image_bytes, name=filename)
            
        except Exception as e:
            logger.error(f"Error processing image: {e}")
            return Response({'error': f'Invalid image data: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get metadata
        face_detected = request.data.get('face_detected', True)
        multiple_faces = request.data.get('multiple_faces', False)
        mobile_detected = request.data.get('mobile_detected', False)
        
        # Get or create proctor session
        session, created = ProctorSession.objects.get_or_create(attempt=attempt)
        session.total_captures += 1
        
        # Create the image record
        proctor_image = ProctorImage.objects.create(
            attempt=attempt,
            image=content_file,
            face_detected=face_detected,
            multiple_faces=multiple_faces,
            mobile_detected=mobile_detected,
            is_suspicious=False
        )
        
        # Check for suspicious activity
        if multiple_faces:
            ProctorLog.objects.create(
                attempt=attempt,
                event_type='MULTIPLE_FACES',
                details={'message': 'Multiple faces detected in frame'}
            )
            session.suspicious_events += 1
        
        if not face_detected:
            ProctorLog.objects.create(
                attempt=attempt,
                event_type='FACE_LOST',
                details={'message': 'No face detected in frame'}
            )
            session.suspicious_events += 1
        
        if mobile_detected:
            ProctorLog.objects.create(
                attempt=attempt,
                event_type='TAB_SWITCH',
                details={'message': 'Mobile device detected in frame'}
            )
            session.suspicious_events += 1
        
        # Auto-flag if suspicious events exceed threshold
        if session.suspicious_events >= 3:
            session.review_status = 'FLAGGED'
            attempt.status = 'FLAGGED'
            attempt.save()
            
            send_notification(
                recipient_roles=['ADMIN'],
                title='🚨 Auto-Flagged Exam',
                message=f'Exam "{attempt.exam.title}" by {attempt.student.user.full_name} was auto-flagged due to {session.suspicious_events} suspicious events.',
                notification_type='SYSTEM_ALERT',
                link='/admin/proctoring-review'
            )
        
        session.save()
        
        # Return the image URL for confirmation
        image_url = None
        if proctor_image.image:
            try:
                image_url = proctor_image.image.url
            except:
                pass
        
        return Response({
            'message': 'Image captured successfully',
            'image_id': proctor_image.id,
            'image_url': image_url,
            'suspicious_events': session.suspicious_events,
            'review_status': session.review_status
        }, status=status.HTTP_201_CREATED)


class FlagSuspiciousView(APIView):
    """Flag an image as suspicious"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, image_id):
        if request.user.role not in ['ADMIN', 'TEACHER']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            image = ProctorImage.objects.get(id=image_id)
        except ProctorImage.DoesNotExist:
            return Response({'error': 'Image not found'}, status=status.HTTP_404_NOT_FOUND)
        
        reason = request.data.get('reason', 'Flagged by reviewer')
        
        image.is_suspicious = True
        image.suspicious_reason = reason
        image.flagged_by = request.user
        image.flagged_at = timezone.now()
        image.save()
        
        session, created = ProctorSession.objects.get_or_create(attempt=image.attempt)
        session.review_status = 'FLAGGED'
        session.suspicious_events += 1
        session.save()
        
        attempt = image.attempt
        if attempt:
            attempt.status = 'FLAGGED'
            attempt.save()
        
        send_notification(
            recipient_roles=['ADMIN'],
            title='🚨 Image Flagged',
            message=f'Image from exam "{attempt.exam.title}" has been flagged by {request.user.full_name}. Reason: {reason}',
            notification_type='SYSTEM_ALERT',
            link='/admin/proctoring-review'
        )
        
        return Response({
            'message': 'Image flagged as suspicious',
            'session_id': session.id
        })


class ClearFlagView(APIView):
    """Clear a suspicious flag from an image"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, image_id):
        if request.user.role not in ['ADMIN']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            image = ProctorImage.objects.get(id=image_id)
        except ProctorImage.DoesNotExist:
            return Response({'error': 'Image not found'}, status=status.HTTP_404_NOT_FOUND)
        
        image.is_suspicious = False
        image.suspicious_reason = ''
        image.flagged_by = None
        image.flagged_at = None
        image.save()
        
        return Response({'message': 'Flag cleared successfully'})


class ProctorLogView(generics.ListCreateAPIView):
    """Get proctoring logs"""
    serializer_class = ProctorLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        attempt_id = self.kwargs.get('attempt_id')
        return ProctorLog.objects.filter(attempt_id=attempt_id)


class ProctorSessionView(generics.RetrieveUpdateAPIView):
    """Get or update proctoring session"""
    serializer_class = ProctorSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        attempt_id = self.kwargs.get('attempt_id')
        session, created = ProctorSession.objects.get_or_create(attempt_id=attempt_id)
        return session


class ReviewProctoringView(APIView):
    """List proctoring sessions for review with full details including images"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        # Check permission
        if user.role not in ['ADMIN', 'TEACHER', 'DEPT_HEAD']:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get sessions based on role
        if user.role == 'ADMIN':
            sessions = ProctorSession.objects.filter(
                review_status__in=['PENDING', 'FLAGGED']
            ).order_by('-started_at')
        else:  # TEACHER or DEPT_HEAD
            sessions = ProctorSession.objects.filter(
                attempt__exam__course__instructor=user,
                review_status__in=['PENDING', 'FLAGGED']
            ).order_by('-started_at')
        
        # Prepare response with full details
        result = []
        for session in sessions:
            attempt = session.attempt
            if not attempt:
                continue
            
            # Get images
            images = ProctorImage.objects.filter(attempt=attempt).order_by('-capture_time')
            images_slice = images[:20]
            
            # Build image data with URLs
            image_data = []
            for img in images_slice:
                image_url = None
                if img.image:
                    try:
                        image_url = img.image.url
                    except:
                        pass
                image_data.append({
                    'id': img.id,
                    'image': image_url,
                    'capture_time': img.capture_time.isoformat() if img.capture_time else None,
                    'is_suspicious': img.is_suspicious,
                    'face_detected': img.face_detected,
                    'multiple_faces': img.multiple_faces,
                    'mobile_detected': img.mobile_detected,
                    'suspicious_reason': img.suspicious_reason,
                })
            
            suspicious_count = images.filter(is_suspicious=True).count()
            
            result.append({
                'id': session.id,
                'attempt': attempt.id,
                'student_name': attempt.student.user.full_name if attempt.student else 'Unknown',
                'student_id': attempt.student.student_id if attempt.student else '',
                'exam_title': attempt.exam.title if attempt.exam else 'Unknown',
                'exam_id': attempt.exam.id if attempt.exam else None,
                'started_at': session.started_at.isoformat() if session.started_at else None,
                'ended_at': session.ended_at.isoformat() if session.ended_at else None,
                'is_active': session.is_active,
                'total_captures': session.total_captures,
                'suspicious_events': session.suspicious_events,
                'review_status': session.review_status,
                'review_notes': session.review_notes,
                'image_count': images.count(),
                'suspicious_image_count': suspicious_count,
                'score': attempt.score,
                'percentage': attempt.percentage,
                'passed': attempt.passed,
                'status': attempt.status,
                'images': image_data
            })
        
        return Response(result)


class ReviewProctoringDetailView(APIView):
    """Get detailed proctoring session with all images and logs"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, session_id):
        if request.user.role not in ['ADMIN', 'TEACHER', 'DEPT_HEAD']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            session = ProctorSession.objects.get(id=session_id)
        except ProctorSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission for teacher
        if request.user.role == 'TEACHER':
            if session.attempt.exam.course.instructor != request.user:
                return Response({'error': 'You do not have permission to view this session'}, status=status.HTTP_403_FORBIDDEN)
        
        images = ProctorImage.objects.filter(attempt=session.attempt).order_by('-capture_time')
        logs = ProctorLog.objects.filter(attempt=session.attempt).order_by('-timestamp')
        
        # Build image URLs
        image_data = []
        for img in images:
            image_url = None
            if img.image:
                try:
                    image_url = img.image.url
                except:
                    pass
            image_data.append({
                'id': img.id,
                'image': image_url,
                'capture_time': img.capture_time.isoformat() if img.capture_time else None,
                'is_suspicious': img.is_suspicious,
                'face_detected': img.face_detected,
                'multiple_faces': img.multiple_faces,
                'mobile_detected': img.mobile_detected,
                'suspicious_reason': img.suspicious_reason,
            })
        
        return Response({
            'session': ProctorSessionSerializer(session).data,
            'images': image_data,
            'logs': ProctorLogSerializer(logs, many=True).data,
            'total_images': images.count(),
            'suspicious_images': images.filter(is_suspicious=True).count(),
            'student_name': session.attempt.student.user.full_name if session.attempt else None,
            'exam_title': session.attempt.exam.title if session.attempt else None,
        })


class ReviewProctoringUpdateView(APIView):
    """Update proctoring review status"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, session_id):
        if request.user.role not in ['ADMIN', 'TEACHER', 'DEPT_HEAD']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            session = ProctorSession.objects.get(id=session_id)
        except ProctorSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission for teacher
        if request.user.role == 'TEACHER':
            if session.attempt.exam.course.instructor != request.user:
                return Response({'error': 'You do not have permission to update this session'}, status=status.HTTP_403_FORBIDDEN)
        
        action = request.data.get('action')
        notes = request.data.get('notes', '')
        
        attempt = session.attempt
        
        if action == 'review':
            session.review_status = 'REVIEWED'
            session.review_notes = notes
            session.save()
            
            if attempt:
                attempt.status = 'GRADED'
                attempt.save()
            
            if attempt and attempt.student:
                send_notification(
                    recipient_user=attempt.student.user,
                    title='✅ Proctoring Review Complete',
                    message=f'Your exam "{attempt.exam.title}" has been reviewed and cleared.',
                    notification_type='SYSTEM_ALERT',
                    link='/results'
                )
            
            return Response({'message': 'Session reviewed successfully'})
        
        elif action == 'clear_flag':
            session.review_status = 'REVIEWED'
            session.suspicious_events = 0
            session.review_notes = f'Flag cleared by {request.user.full_name}. {notes}'
            session.save()
            
            ProctorImage.objects.filter(attempt=session.attempt).update(
                is_suspicious=False,
                suspicious_reason=''
            )
            
            if attempt:
                attempt.status = 'GRADED'
                attempt.save()
            
            if attempt and attempt.student:
                send_notification(
                    recipient_user=attempt.student.user,
                    title='✅ Flag Cleared',
                    message=f'The flag on your exam "{attempt.exam.title}" has been cleared.',
                    notification_type='SYSTEM_ALERT',
                    link='/results'
                )
            
            return Response({'message': 'Flag cleared successfully'})
        
        elif action == 'flag':
            session.review_status = 'FLAGGED'
            session.review_notes = notes
            session.save()
            
            if attempt:
                attempt.status = 'FLAGGED'
                attempt.save()
            
            if attempt and attempt.student:
                send_notification(
                    recipient_user=attempt.student.user,
                    title='📋 Exam Flagged for Review',
                    message=f'Your exam "{attempt.exam.title}" has been flagged for review.',
                    notification_type='SYSTEM_ALERT',
                    link='/results'
                )
            
            send_notification(
                recipient_roles=['ADMIN'],
                title='🚨 Exam Flagged for Review',
                message=f'Exam "{attempt.exam.title if attempt else ""}" has been flagged by {request.user.full_name}.',
                notification_type='SYSTEM_ALERT',
                link='/admin/proctoring-review'
            )
            
            return Response({'message': 'Session flagged for review'})
        
        return Response({'error': 'Invalid action'}, status=status.HTTP_400_BAD_REQUEST)


class FlaggedExamsView(APIView):
    """Get all flagged exams with details"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        if request.user.role not in ['ADMIN', 'TEACHER']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        queryset = ExamAttempt.objects.filter(status='FLAGGED')
        
        if request.user.role == 'TEACHER':
            queryset = queryset.filter(exam__course__instructor=request.user)
        
        data = []
        for attempt in queryset:
            session = ProctorSession.objects.filter(attempt=attempt).first()
            data.append({
                'id': attempt.id,
                'student_name': attempt.student.user.full_name,
                'student_id': attempt.student.student_id,
                'exam_title': attempt.exam.title,
                'course_title': attempt.exam.course.title,
                'score': attempt.score,
                'percentage': attempt.percentage,
                'status': attempt.status,
                'start_time': attempt.start_time,
                'suspicious_events': session.suspicious_events if session else 0,
                'review_status': session.review_status if session else 'PENDING',
                'suspicious_images': ProctorImage.objects.filter(
                    attempt=attempt,
                    is_suspicious=True
                ).count() if session else 0,
                'total_captures': session.total_captures if session else 0,
            })
        
        return Response({
            'total': queryset.count(),
            'exams': data
        })


# ============================================================
# ✅ NEW: ProctorCaptureView - For Frontend Integration
# ============================================================

class ProctorCaptureView(APIView):
    """
    Capture and save proctoring image from frontend
    POST /api/proctoring/sessions/capture/
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            # Get data from request
            exam_id = request.data.get('exam_id')
            image_data = request.data.get('image_data')
            metadata = request.data.get('metadata', {})

            if not exam_id:
                return Response({
                    'error': 'exam_id is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            if not image_data:
                return Response({
                    'error': 'image_data is required'
                }, status=status.HTTP_400_BAD_REQUEST)

            # Get student profile
            try:
                student = StudentProfile.objects.get(user=request.user)
            except StudentProfile.DoesNotExist:
                return Response({
                    'error': 'Student profile not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # Get exam attempt
            try:
                attempt = ExamAttempt.objects.get(
                    id=exam_id,
                    student=student
                )
            except ExamAttempt.DoesNotExist:
                return Response({
                    'error': 'Exam attempt not found'
                }, status=status.HTTP_404_NOT_FOUND)

            # Get or create proctor session
            session, created = ProctorSession.objects.get_or_create(
                attempt=attempt,
                defaults={
                    'is_active': True,
                    'started_at': timezone.now()
                }
            )

            # Process image
            try:
                # Remove data URL prefix if present
                if 'base64,' in image_data:
                    format_str, imgstr = image_data.split(';base64,')
                    if '/' in format_str:
                        ext = format_str.split('/')[-1]
                    else:
                        ext = 'jpg'
                else:
                    imgstr = image_data
                    ext = 'jpg'

                # Decode base64
                image_bytes = base64.b64decode(imgstr)

                # Create filename
                filename = f"proctor_{attempt.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.{ext}"
                content_file = ContentFile(image_bytes, name=filename)

                # Create proctor image record
                proctor_image = ProctorImage.objects.create(
                    attempt=attempt,
                    image=content_file,
                    face_detected=metadata.get('face_detected', True),
                    multiple_faces=metadata.get('multiple_faces', False),
                    mobile_detected=metadata.get('mobile_detected', False),
                    gaze_direction=metadata.get('gaze_direction', 'CENTER'),
                    gaze_confidence=metadata.get('gaze_confidence', 0.0),
                    gaze_x=metadata.get('gaze_x', 0.0),
                    gaze_y=metadata.get('gaze_y', 0.0),
                    head_tilt_x=metadata.get('head_tilt_x', 0.0),
                    head_tilt_y=metadata.get('head_tilt_y', 0.0),
                    eyes_closed=metadata.get('eyes_closed', False),
                    objects_detected=metadata.get('objects_detected', []),
                    is_suspicious=False
                )

                # Update session
                session.total_captures += 1

                # Check for suspicious events
                suspicious_events = []

                if metadata.get('multiple_faces', False):
                    suspicious_events.append('MULTIPLE_FACES')
                    ProctorLog.objects.create(
                        attempt=attempt,
                        event_type='MULTIPLE_FACES',
                        details={'message': 'Multiple faces detected'}
                    )
                    session.suspicious_events += 1

                if not metadata.get('face_detected', True):
                    suspicious_events.append('FACE_LOST')
                    ProctorLog.objects.create(
                        attempt=attempt,
                        event_type='FACE_LOST',
                        details={'message': 'No face detected'}
                    )
                    session.suspicious_events += 1

                if metadata.get('gaze_direction', 'CENTER') != 'CENTER':
                    suspicious_events.append('GAZE_AWAY')
                    ProctorLog.objects.create(
                        attempt=attempt,
                        event_type='GAZE_AWAY',
                        details={
                            'direction': metadata.get('gaze_direction'),
                            'confidence': metadata.get('gaze_confidence', 0)
                        }
                    )
                    session.gaze_events_count += 1
                    session.suspicious_events += 1

                if metadata.get('objects_detected', []):
                    suspicious_events.append('OBJECT_DETECTED')
                    ProctorLog.objects.create(
                        attempt=attempt,
                        event_type='OBJECT_DETECTED',
                        details={'objects': metadata.get('objects_detected')}
                    )
                    session.object_events_count += 1
                    session.suspicious_events += 1

                # Auto-flag if threshold exceeded
                is_flagged = False
                if session.suspicious_events >= 3:
                    session.review_status = 'AUTO_FLAGGED'
                    is_flagged = True

                    # Flag the image
                    proctor_image.is_suspicious = True
                    proctor_image.suspicious_reason = f'Auto-flagged: {", ".join(suspicious_events)}'
                    proctor_image.save()

                    # Update attempt status
                    attempt.status = 'FLAGGED'
                    attempt.save()

                    # Send notification
                    send_notification(
                        recipient_roles=['ADMIN'],
                        title='🚨 AI Auto-Flagged Exam',
                        message=f'Exam "{attempt.exam.title}" by {student.user.full_name} auto-flagged. Events: {", ".join(suspicious_events)}',
                        notification_type='SYSTEM_ALERT',
                        link='/admin/proctoring-review'
                    )

                session.save()

                # Build image URL
                image_url = request.build_absolute_uri(proctor_image.image.url) if proctor_image.image else None

                return Response({
                    'success': True,
                    'message': 'Proctoring image captured',
                    'image_id': proctor_image.id,
                    'image_url': image_url,
                    'suspicious_events': session.suspicious_events,
                    'review_status': session.review_status,
                    'is_flagged': is_flagged,
                    'is_suspicious': proctor_image.is_suspicious,
                    'suspicious_reason': proctor_image.suspicious_reason,
                    'capture_time': proctor_image.capture_time.isoformat()
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                logger.error(f"Error processing image: {e}")
                return Response({
                    'error': f'Failed to process image: {str(e)}'
                }, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.error(f"Proctor capture error: {e}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProctorSessionStatusView(APIView):
    """
    Get proctoring session status
    GET /api/proctoring/sessions/<attempt_id>/status/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, attempt_id):
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id)
        except ExamAttempt.DoesNotExist:
            return Response({
                'error': 'Attempt not found'
            }, status=status.HTTP_404_NOT_FOUND)

        # Check permission
        if request.user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=request.user)
                if attempt.student != student:
                    return Response({
                        'error': 'Permission denied'
                    }, status=status.HTTP_403_FORBIDDEN)
            except:
                return Response({
                    'error': 'Permission denied'
                }, status=status.HTTP_403_FORBIDDEN)

        # Get session
        try:
            session = ProctorSession.objects.get(attempt=attempt)
        except ProctorSession.DoesNotExist:
            return Response({
                'is_active': False,
                'total_captures': 0,
                'suspicious_events': 0,
                'review_status': 'PENDING'
            })

        return Response({
            'is_active': session.is_active,
            'total_captures': session.total_captures,
            'suspicious_events': session.suspicious_events,
            'review_status': session.review_status,
            'gaze_events': session.gaze_events_count,
            'object_events': session.object_events_count,
            'started_at': session.started_at.isoformat() if session.started_at else None,
            'ml_risk_score': session.ml_risk_score
        })


# ============================================================
# ✅ NEW: AI Proctoring Views
# ============================================================

class AIProctorAnalysisView(APIView):
    """AI-powered proctoring analysis"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        if request.user.role not in ['ADMIN', 'TEACHER']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        session_id = request.data.get('session_id')
        if not session_id:
            return Response({'error': 'session_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            session = ProctorSession.objects.get(id=session_id)
        except ProctorSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get all images
        images = ProctorImage.objects.filter(attempt=session.attempt).order_by('-capture_time')
        
        # Analyze images
        analysis = {
            'total_images': images.count(),
            'suspicious_images': images.filter(is_suspicious=True).count(),
            'gaze_analysis': self._analyze_gaze(images),
            'object_analysis': self._analyze_objects(images),
            'head_analysis': self._analyze_head_position(images),
            'eye_analysis': self._analyze_eyes(images),
            'ml_risk_score': session.ml_risk_score,
            'recommendation': self._get_recommendation(session)
        }
        
        return Response({
            'success': True,
            'session_id': session.id,
            'student_name': session.attempt.student.user.full_name,
            'exam_title': session.attempt.exam.title,
            'analysis': analysis
        })
    
    def _analyze_gaze(self, images):
        """Analyze gaze patterns"""
        gaze_data = {
            'directions': defaultdict(int),
            'average_confidence': 0,
            'gaze_away_count': 0,
            'total_analyzed': 0
        }
        
        for img in images:
            if img.gaze_direction:
                gaze_data['directions'][img.gaze_direction] += 1
                gaze_data['total_analyzed'] += 1
                gaze_data['average_confidence'] += img.gaze_confidence
                
                if img.gaze_direction != 'CENTER':
                    gaze_data['gaze_away_count'] += 1
        
        if gaze_data['total_analyzed'] > 0:
            gaze_data['average_confidence'] /= gaze_data['total_analyzed']
        
        return gaze_data
    
    def _analyze_objects(self, images):
        """Analyze detected objects"""
        objects = defaultdict(int)
        total_frames = 0
        
        for img in images:
            if img.objects_detected:
                total_frames += 1
                for obj in img.objects_detected:
                    objects[obj] += 1
        
        return {
            'detected_objects': dict(objects),
            'total_frames_with_objects': total_frames,
            'suspicious_objects': [obj for obj, count in objects.items() if count > 3]
        }
    
    def _analyze_head_position(self, images):
        """Analyze head position"""
        head_data = {
            'tilted_count': 0,
            'average_tilt_x': 0,
            'average_tilt_y': 0,
            'total_analyzed': 0
        }
        
        for img in images:
            if img.head_tilt_x != 0 or img.head_tilt_y != 0:
                head_data['total_analyzed'] += 1
                head_data['average_tilt_x'] += img.head_tilt_x
                head_data['average_tilt_y'] += img.head_tilt_y
                if abs(img.head_tilt_x) > 25 or abs(img.head_tilt_y) > 20:
                    head_data['tilted_count'] += 1        
        if head_data['total_analyzed'] > 0:
            head_data['average_tilt_x'] /= head_data['total_analyzed']
            head_data['average_tilt_y'] /= head_data['total_analyzed']
        
        return head_data
    
    def _analyze_eyes(self, images):
        """Analyze eye status"""
        eye_data = {
            'closed_count': 0,
            'total_analyzed': 0,
            'average_openness': 0
        }
        
        for img in images:
            eye_data['total_analyzed'] += 1
            if img.eyes_closed:
                eye_data['closed_count'] += 1
            eye_data['average_openness'] += img.gaze_confidence
        
        if eye_data['total_analyzed'] > 0:
            eye_data['average_openness'] /= eye_data['total_analyzed']
        
        return eye_data
    
    def _get_recommendation(self, session):
        """Get recommendation based on analysis"""
        if session.review_status in ['FLAGGED', 'AUTO_FLAGGED']:
            return '🚨 Immediate review required. Multiple suspicious events detected.'
        elif session.suspicious_events > 2:
            return '⚠️ Review recommended. Moderate suspicious activity detected.'
        elif session.suspicious_events > 0:
            return 'ℹ️ Monitor session. Minor suspicious activity detected.'
        else:
            return '✅ No suspicious activity detected. Session is clean.'


class AIProctorSessionSummaryView(APIView):
    """Get AI-generated summary of a proctoring session"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, session_id):
        if request.user.role not in ['ADMIN', 'TEACHER']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            session = ProctorSession.objects.get(id=session_id)
        except ProctorSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get analysis
        images = ProctorImage.objects.filter(attempt=session.attempt)
        logs = ProctorLog.objects.filter(attempt=session.attempt)
        
        summary = {
            'session_id': session.id,
            'student': session.attempt.student.user.full_name,
            'exam': session.attempt.exam.title,
            'duration': (session.ended_at - session.started_at).total_seconds() / 60 if session.ended_at else 0,
            'captures': session.total_captures,
            'suspicious_events': session.suspicious_events,
            'review_status': session.review_status,
            'ml_risk_score': session.ml_risk_score,
            'events_breakdown': {
                'gaze_events': session.gaze_events_count,
                'object_events': session.object_events_count,
                'head_tilt_events': session.head_tilt_events_count,
            },
            'timeline': [
                {
                    'time': log.timestamp.isoformat(),
                    'event': log.event_type,
                    'details': log.details
                }
                for log in logs[:20]
            ],
            'risk_assessment': {
                'level': 'HIGH' if session.review_status in ['FLAGGED', 'AUTO_FLAGGED'] else 'MEDIUM' if session.suspicious_events > 2 else 'LOW',
                'score': session.ml_risk_score,
                'recommendation': self._get_recommendation(session)
            }
        }
        
        return Response(summary)
    
    def _get_recommendation(self, session):
        if session.review_status in ['FLAGGED', 'AUTO_FLAGGED']:
            return '🚨 Immediate investigation required'
        elif session.suspicious_events > 2:
            return '⚠️ Review recommended'
        elif session.suspicious_events > 0:
            return 'ℹ️ Monitor closely'
        return '✅ All clear'


class AIProctorAutoFlagView(APIView):
    """Auto-flag a session based on AI analysis"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, session_id):
        if request.user.role not in ['ADMIN']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            session = ProctorSession.objects.get(id=session_id)
        except ProctorSession.DoesNotExist:
            return Response({'error': 'Session not found'}, status=status.HTTP_404_NOT_FOUND)
        
        reason = request.data.get('reason', 'Auto-flagged by AI')
        
        # Flag the session
        session.review_status = 'AUTO_FLAGGED'
        session.review_notes = f"AI Auto-flag: {reason}"
        session.save()
        
        # Flag suspicious images
        ProctorImage.objects.filter(attempt=session.attempt).update(
            is_suspicious=True,
            suspicious_reason=reason
        )
        
        # Update attempt status
        attempt = session.attempt
        attempt.status = 'FLAGGED'
        attempt.save()
        
        # Send notification
        send_notification(
            recipient_roles=['ADMIN'],
            title='🚨 AI Auto-Flagged Exam',
            message=f'AI auto-flagged exam "{attempt.exam.title}" for {attempt.student.user.full_name}. Reason: {reason}',
            notification_type='SYSTEM_ALERT',
            link='/admin/proctoring-review'
        )
        
        return Response({
            'success': True,
            'message': 'Session auto-flagged successfully',
            'session_id': session.id,
            'status': session.review_status
        })


class AIObjectDetectionView(APIView):
    """AI Object Detection endpoint for proctoring"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        if request.user.role != 'STUDENT':
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        attempt_id = request.data.get('attempt_id')
        objects = request.data.get('objects', [])
        
        if not attempt_id:
            return Response({'error': 'attempt_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Log object detection
        ProctorLog.objects.create(
            attempt=attempt,
            event_type='OBJECT_DETECTED',
            details={'objects': objects, 'timestamp': timezone.now().isoformat()}
        )
        
        # Check for suspicious objects
        suspicious_objects = ['cell phone', 'mobile phone', 'book', 'laptop', 'tablet']
        detected_suspicious = [obj for obj in objects if any(s in obj.lower() for s in suspicious_objects)]
        
        if detected_suspicious:
            # Create proctor image record
            ProctorImage.objects.create(
                attempt=attempt,
                objects_detected=detected_suspicious,
                is_suspicious=True,
                suspicious_reason=f"Suspicious objects detected: {', '.join(detected_suspicious)}",
                object_confidence=0.8
            )
            
            # Update session
            try:
                session = ProctorSession.objects.get(attempt=attempt)
                session.object_events_count += 1
                session.suspicious_events += 1
                if session.suspicious_events >= session.auto_flag_threshold:
                    session.review_status = 'AUTO_FLAGGED'
                session.save()
            except ProctorSession.DoesNotExist:
                pass
        
        return Response({
            'success': True,
            'detected': objects,
            'suspicious': detected_suspicious
        })


class AIGazeAnalysisView(APIView):
    """AI Gaze Analysis endpoint"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        if request.user.role != 'STUDENT':
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        attempt_id = request.data.get('attempt_id')
        gaze_data = request.data.get('gaze_data', {})
        
        if not attempt_id:
            return Response({'error': 'attempt_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Create or update proctor image with gaze data
        ProctorImage.objects.create(
            attempt=attempt,
            gaze_direction=gaze_data.get('direction', 'CENTER'),
            gaze_confidence=gaze_data.get('confidence', 0.0),
            gaze_x=gaze_data.get('gaze_x', 0.0),
            gaze_y=gaze_data.get('gaze_y', 0.0),
            head_tilt_x=gaze_data.get('tilt_x', 0.0),
            head_tilt_y=gaze_data.get('tilt_y', 0.0),
            eyes_closed=gaze_data.get('eyes_closed', False),
            is_suspicious=gaze_data.get('direction', 'CENTER') != 'CENTER'
        )
        
        # Log gaze event
        ProctorLog.objects.create(
            attempt=attempt,
            event_type='GAZE_AWAY' if gaze_data.get('direction') != 'CENTER' else 'TAB_SWITCH',
            details=gaze_data
        )
        
        return Response({
            'success': True,
            'message': 'Gaze data recorded'
        })