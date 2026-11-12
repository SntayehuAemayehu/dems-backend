# exams/views.py - COMPLETE WITH ALL VIEWS
from decimal import Decimal
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Q
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.db import transaction
from .models import Exam, Question, ExamAttempt, Answer, ExamRecording, ExaminerAssignment
from .serializers import ExamSerializer, QuestionSerializer, ExamAttemptSerializer
from accounts.models import StudentProfile, TeacherProfile
from notifications.utils import send_notification
from courses.models import COURSE_ACCESS_ENROLLMENT_STATUSES, Course, Enrollment
from proctoring.models import ProctorSession, ProctorImage
from accounts.face_service import extract_embedding, compare_embeddings
import logging
from django.core.files.base import ContentFile
import os
from .ai_proctor import AIProctorBackend
from django.core.files.base import ContentFile
logger = logging.getLogger(__name__)
import hashlib
import secrets
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings as django_settings
from .seb_service import (
    generate_and_save,
    verify_config_key_hash,
)
from .models import SEBSession  # add SEBSession to existing model import


def _can_manage_exam(exam, user):
    return user.role == 'ADMIN' or exam.course.instructor_id == user.id or exam.created_by_id == user.id


def _broadcast_exam_questions(exam):
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    async_to_sync(get_channel_layer().group_send)(
        f'exam_proctor_{exam.id}',
        {
            'type': 'exam_update',
            'questions': QuestionSerializer(exam.questions.order_by('order'), many=True).data,
        },
    )


# ============================================================
# EXISTING VIEWS - PRESERVED
# ============================================================

# exams/views.py
class ExamListView(generics.ListCreateAPIView):
    serializer_class = ExamSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == 'TEACHER':
            # ✅ FIX: Just filter by instructor. The missing table was crashing this query.
            return Exam.objects.filter(
                Q(course__instructor=user)
            ).distinct()
        
        elif user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=user)
                enrolled_courses = Enrollment.objects.filter(
                    student=student, 
                    status__in=COURSE_ACCESS_ENROLLMENT_STATUSES
                ).values_list('course_id', flat=True)
                
                return Exam.objects.filter(
                    course__in=enrolled_courses, 
                    is_published=True
                )
            except StudentProfile.DoesNotExist:
                return Exam.objects.none()
        
        elif user.role == 'DEPT_HEAD':
            try:
                department = user.headed_department
                return Exam.objects.filter(course__department=department)
            except:
                return Exam.objects.none()
        else:
            return Exam.objects.all()
    
    def create(self, request, *args, **kwargs):
        if request.user.role not in ['TEACHER', 'ADMIN', 'DEPT_HEAD']:
            return Response(
                {'error': 'Only teachers, admins, and department heads can create exams.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        course_id = request.data.get('course')
        try:
            from courses.models import Course
            course = Course.objects.get(id=course_id)
        except Course.DoesNotExist:
            return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if request.user.role == 'DEPT_HEAD':
            try:
                department = request.user.headed_department
                if course.department != department:
                    return Response(
                        {'error': 'You can only create exams for courses in your department'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except:
                return Response(
                    {'error': 'You are not assigned to any department'},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif request.user.role != 'ADMIN' and course.instructor != request.user:
            return Response(
                {'error': 'You do not own this course'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer.save(created_by=request.user)

        exam = serializer.instance
        if exam.is_published and not exam.seb_enabled:
            try:
                generate_and_save(exam)
            except Exception as e:
                logger.error(f"SEB generation failed on create for exam {exam.id}: {e}")
        
        enrollments = Enrollment.objects.filter(course=course, status='ACTIVE')
        for enrollment in enrollments:
            send_notification(
                recipient_user=enrollment.student.user,
                title='📝 New Exam Scheduled',
                message=f'Exam "{serializer.data.get("title")}" has been scheduled for {course.title}.',
                notification_type='EXAM_SCHEDULED',
                link='/exams'
            )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ExamDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Exam.objects.all()
    serializer_class = ExamSerializer
    permission_classes = [permissions.IsAuthenticated]

    def update(self, request, *args, **kwargs):
        exam = self.get_object()
        if not _can_manage_exam(exam, request.user):
            return Response({'error': 'You do not have permission to update this exam'}, status=status.HTTP_403_FORBIDDEN)

        was_published = exam.is_published
        response = super().update(request, *args, **kwargs)

        if response.status_code < 400:
            exam.refresh_from_db()
            # ✅ Auto-generate SEB on publish transition
            if not was_published and exam.is_published:
                try:
                    generate_and_save(exam)
                    logger.info(f"SEB config generated for exam {exam.id}")
                except Exception as e:
                    logger.error(f"SEB generation failed for exam {exam.id}: {e}")
                    # Don't fail the publish — just log
            _broadcast_exam_questions(exam)
        return response


class QuestionView(generics.ListCreateAPIView):
    serializer_class = QuestionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        exam_id = self.kwargs.get('exam_id')
        return Question.objects.filter(exam_id=exam_id).order_by('order')
    
    def perform_create(self, serializer):
        exam_id = self.kwargs.get('exam_id')
        exam = Exam.objects.get(id=exam_id)
        serializer.save(exam=exam)
    
    def create(self, request, *args, **kwargs):
        exam_id = self.kwargs.get('exam_id')
        
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # ✅ FIX: Allow if user is ADMIN, DEPT_HEAD, or the COURSE INSTRUCTOR
        if request.user.role != 'ADMIN' and exam.course.instructor != request.user and request.user.role != 'DEPT_HEAD':
            return Response(
                {'error': 'You do not have permission to add questions to this exam'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        data = request.data.copy()
        question_type = data.get('type')
        
        if question_type == 'MCQ':
            options = data.get('options', [])
            if isinstance(options, dict):
                options = [v for v in options.values() if v and v.strip()]
            elif isinstance(options, list):
                options = [v for v in options if v and v.strip()]
            else:
                options = []
            
            if len(options) < 2:
                return Response(
                    {'error': 'MCQ questions must have at least 2 options'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            data['options'] = options
            
            if not data.get('correct_answer'):
                return Response(
                    {'error': 'MCQ questions must have a correct answer selected'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        elif question_type == 'TF':
            if not data.get('correct_answer'):
                return Response(
                    {'error': 'True/False questions must have a correct answer'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            data['options'] = []
        
        elif question_type == 'SHORT':
            data['correct_answer'] = ''
            data['options'] = []
        
        else:
            return Response(
                {'error': f'Invalid question type: {question_type}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        question_count = Question.objects.filter(exam=exam).count()
        data['order'] = question_count
        
        serializer = self.get_serializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        self.perform_create(serializer)
        _broadcast_exam_questions(exam)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

# exams/views.py

class QuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    # ✅ ALLOW TEACHERS TO UPDATE QUESTIONS
    def update(self, request, *args, **kwargs):
        question = self.get_object()
        
        # Permission check
        if not _can_manage_exam(question.exam, request.user):
            return Response(
                {'error': 'You do not have permission to update this question'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        data = request.data.copy()
        question_type = data.get('type', question.type)
        
        # Validate and format MCQ options
        if question_type == 'MCQ':
            options = data.get('options', [])
            if isinstance(options, dict):
                options = [v for v in options.values() if v and v.strip()]
            elif isinstance(options, list):
                options = [v for v in options if v and v.strip()]
                
            if len(options) < 2:
                return Response(
                    {'error': 'MCQ questions must have at least 2 options'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            data['options'] = options
            
            if not data.get('correct_answer'):
                return Response(
                    {'error': 'MCQ questions must have a correct answer selected'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        elif question_type == 'TF':
            if not data.get('correct_answer'):
                return Response(
                    {'error': 'True/False questions must have a correct answer'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            data['options'] = [] # Clear options for TF
            
        elif question_type == 'SHORT':
            data['correct_answer'] = ''
            data['options'] = []

        # Perform partial update (PATCH) or full update (PUT)
        partial = kwargs.pop('partial', False)
        serializer = self.get_serializer(question, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        _broadcast_exam_questions(question.exam)
        return Response(serializer.data)

    # ✅ ALLOW TEACHERS TO DELETE QUESTIONS
    def destroy(self, request, *args, **kwargs):
        question = self.get_object()
        
        # Permission check
        if not _can_manage_exam(question.exam, request.user):
            return Response(
                {'error': 'You do not have permission to delete this question'},
                status=status.HTTP_403_FORBIDDEN
            )
        exam = question.exam
        question.delete()
        _broadcast_exam_questions(exam)
        return Response({'message': 'Question deleted successfully'}, status=status.HTTP_200_OK)



class StartExamView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, exam_id):
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)

        if not exam.is_published:
            return Response({'error': 'Exam is not published'}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ TEMPORARILY DISABLED FOR HOMEPAGE FLOW TESTING
        # if exam.seb_enabled:
        #     session_id = request.COOKIES.get('seb_session_id')
        #     if not session_id:
        #         return Response(
        #             {'error': 'This exam requires Safe Exam Browser. Please open the .seb file.'},
        #             status=status.HTTP_403_FORBIDDEN
        #         )
        #     try:
        #         seb_session = SEBSession.objects.get(id=session_id, exam=exam)
        #     except (SEBSession.DoesNotExist, ValueError):
        #         return Response(
        #             {'error': 'Invalid SEB session. Please reopen the .seb file.'},
        #             status=status.HTTP_403_FORBIDDEN
        #         )
        #     if not seb_session.is_valid():
        #         return Response(
        #             {'error': 'SEB session expired. Please reopen the .seb file.'},
        #             status=status.HTTP_403_FORBIDDEN
        #         )

        now = timezone.now()
        if now < exam.start_time:
            return Response({'error': 'Exam has not started yet'}, status=status.HTTP_400_BAD_REQUEST)
        if now > exam.end_time:
            return Response({'error': 'Exam has ended'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ TEMPORARILY DISABLED FOR HOMEPAGE FLOW TESTING
        # if exam.seb_enabled:
        #     if seb_session.student_id != student.id:
        #         return Response(
        #             {'error': 'SEB session does not belong to this student.'},
        #             status=status.HTTP_403_FORBIDDEN
        #         )

        if not Enrollment.objects.filter(
            student=student,
            course=exam.course,
            status__in=COURSE_ACCESS_ENROLLMENT_STATUSES,
        ).exists():
            return Response({'error': 'You are not enrolled in this course'}, status=status.HTTP_400_BAD_REQUEST)

        if ExamAttempt.objects.filter(student=student, exam=exam, status__in=['IN_PROGRESS', 'SUBMITTED']).exists():
            return Response({'error': 'You have already taken this exam'}, status=status.HTTP_400_BAD_REQUEST)

        questions = exam.questions.all()
        if not questions:
            return Response({'error': 'No questions found for this exam'}, status=status.HTTP_400_BAD_REQUEST)

        attempt = ExamAttempt.objects.create(
            student=student,
            exam=exam,
            status='IN_PROGRESS',
            end_time=timezone.now() + timezone.timedelta(minutes=exam.duration_minutes)
        )

        # ✅ TEMPORARILY DISABLED FOR HOMEPAGE FLOW TESTING
        # if exam.seb_enabled:
        #     seb_session.used = True
        #     seb_session.attempt = attempt
        #     seb_session.save(update_fields=['used', 'attempt'])

        response = Response({
            'attempt_id': attempt.id,
            'questions': QuestionSerializer(questions, many=True).data,
            'duration_minutes': exam.duration_minutes,
            'end_time': attempt.end_time
        })
        # Clear the cookie (single-use)
        # response.delete_cookie('seb_session_id', path=f'/api/exams/{exam.id}/')
        return response


class SubmitExamView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, attempt_id):
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id, student__user=request.user)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if attempt.status == 'SUBMITTED':
            return Response({'error': 'Exam already submitted'}, status=status.HTTP_400_BAD_REQUEST)
        
        answers_data = request.data.get('answers', {})
        exam = attempt.exam
        total_score = 0
        total_marks = 0
        
        with transaction.atomic():
            for question in exam.questions.all():
                total_marks += float(question.marks)
                student_answer = answers_data.get(str(question.id), '')
                
                if question.type in ['MCQ', 'TF']:
                    is_correct = student_answer.strip().upper() == question.correct_answer.strip().upper()
                    marks_obtained = float(question.marks) if is_correct else 0
                    if is_correct:
                        total_score += marks_obtained
                else:
                    marks_obtained = None
                    is_correct = False
                
                Answer.objects.create(
                    attempt=attempt,
                    question=question,
                    answer_text=student_answer,
                    marks_obtained=marks_obtained,
                    is_correct=is_correct if question.type in ['MCQ', 'TF'] else False,
                    feedback=''
                )
            
            attempt.status = 'SUBMITTED'
            attempt.score = total_score
            attempt.total_marks = total_marks
            
            auto_graded_marks = sum(
                float(q.marks) for q in exam.questions.all() if q.type in ['MCQ', 'TF']
            )
            if auto_graded_marks > 0:
                attempt.percentage = (total_score / auto_graded_marks * 100) if auto_graded_marks > 0 else 0
            else:
                attempt.percentage = 0
            
            has_essay = exam.questions.filter(type='SHORT').exists()
            if not has_essay:
                attempt.passed = attempt.percentage >= float(exam.passing_mark)
            else:
                attempt.passed = False
            
            attempt.answers = answers_data
            attempt.save()
        
        send_notification(
            recipient_user=exam.created_by,
            title='📝 Exam Submitted',
            message=f'Student {attempt.student.user.full_name} submitted "{exam.title}".',
            notification_type='EXAM_SCHEDULED',
            link=f'/exams/submissions/{exam.id}/'
        )
        
        return Response({
            'message': 'Exam submitted successfully',
            'score': attempt.score,
            'total_marks': attempt.total_marks,
            'percentage': attempt.percentage,
            'passed': attempt.passed,
            'has_essay': has_essay,
            'needs_grading': has_essay
        })


class ExamResultsView(generics.ListAPIView):
    serializer_class = ExamAttemptSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.role == 'STUDENT':
            return ExamAttempt.objects.filter(
                student__user=user, 
                status__in=['SUBMITTED', 'GRADED']
            ).select_related('exam', 'student__user')
        elif user.role == 'TEACHER':
            return ExamAttempt.objects.filter(
                exam__course__instructor=user, 
                status__in=['SUBMITTED', 'GRADED']
            ).select_related('exam', 'student__user')
        else:
            return ExamAttempt.objects.filter(
                status__in=['SUBMITTED', 'GRADED']
            ).select_related('exam', 'student__user')
    
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        result_data = []
        for item in serializer.data:
            attempt = queryset.get(id=item['id'])
            has_essay = attempt.exam.questions.filter(type='SHORT').exists()
            essay_graded = True
            if has_essay:
                essay_answers = Answer.objects.filter(
                    attempt=attempt,
                    question__type='SHORT'
                )
                essay_graded = all(a.marks_obtained is not None for a in essay_answers)
            
            result_data.append({
                **item,
                'has_essay': has_essay,
                'essay_graded': essay_graded,
                'can_view_details': has_essay and essay_graded
            })
        
        return Response(result_data)


class ExamSubmissionsView(APIView):
    """Get all submissions for an exam with full details including essay answers"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, exam_id):
        user = request.user

        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check permissions
        if user.role == 'TEACHER':
            if exam.course.instructor != user:
                return Response(
                    {'error': 'You are not the instructor for this exam'},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif user.role == 'DEPT_HEAD':
            try:
                department = user.headed_department
                if exam.course.department != department:
                    return Response(
                        {'error': 'You can only view exams in your department'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except:
                return Response(
                    {'error': 'You are not assigned to any department'},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif user.role not in ['ADMIN']:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )

        attempts = ExamAttempt.objects.filter(
            exam=exam,
            status__in=['SUBMITTED', 'GRADED']
        ).select_related('student__user')

        result = []
        for attempt in attempts:
            answers = Answer.objects.filter(attempt=attempt).select_related('question')

            auto_graded_answers = []
            essay_answers = []

            for answer in answers:
                answer_data = {
                    'id': answer.id,
                    'question_id': answer.question.id,
                    'question_text': answer.question.text,
                    'question_type': answer.question.type,
                    'answer_text': answer.answer_text,
                    'marks_obtained': float(answer.marks_obtained) if answer.marks_obtained is not None else None,
                    'max_marks': float(answer.question.marks),
                    'is_correct': answer.is_correct,
                    'graded': answer.graded_at is not None,
                    'graded_by': answer.graded_by.full_name if answer.graded_by else None,
                    'graded_at': answer.graded_at.isoformat() if answer.graded_at else None,
                    'feedback': answer.feedback if hasattr(answer, 'feedback') else '',
                }

                if answer.question.type in ['MCQ', 'TF']:
                    auto_graded_answers.append(answer_data)
                else:
                    essay_answers.append(answer_data)

            # ✅ student_id is the Registrar-generated ID (MAU2026000026),
            # NOT the database PK. We keep 'student_pk' too just in case you need it.
            registrar_id = attempt.student.student_id or ''

            result.append({
                'attempt_id': attempt.id,
                'student_id': registrar_id,                    # ✅ Registrar ID (string)
                'student_pk': attempt.student.id,              # ✅ Database PK (int) — for debugging
                'student_name': attempt.student.user.full_name,
                'student_email': attempt.student.user.email,
                'start_time': attempt.start_time.isoformat(),
                'end_time': attempt.end_time.isoformat() if attempt.end_time else None,
                'status': attempt.status,
                'score': float(attempt.score) if attempt.score else 0,
                'total_marks': float(attempt.total_marks) if attempt.total_marks else 0,
                'percentage': float(attempt.percentage) if attempt.percentage else 0,
                'passed': attempt.passed,
                'auto_graded_answers': auto_graded_answers,
                'essay_answers': essay_answers,
                'auto_graded_score': sum(a['marks_obtained'] for a in auto_graded_answers if a['marks_obtained'] is not None),
                'essay_score': sum(a['marks_obtained'] for a in essay_answers if a['marks_obtained'] is not None),
                'total_essay_marks': sum(a['max_marks'] for a in essay_answers),
                'essay_graded_count': sum(1 for a in essay_answers if a['graded']),
                'essay_total_count': len(essay_answers),
                'all_essay_graded': all(a['graded'] for a in essay_answers) if essay_answers else True,
            })

        return Response({
            'exam_id': exam.id,
            'exam_title': exam.title,
            'total_submissions': len(result),
            'submissions': result
        })

# exams/views.py - GradeEssayAnswerView - FIXED

# exams/views.py - COMPLETE GradeEssayAnswerView



class GradeEssayAnswerView(APIView):
    """
    Grade a single essay answer and auto-calculate course grade
    POST /api/exams/grade-essay/
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        answer_id = request.data.get('answer_id')
        marks_obtained = request.data.get('marks_obtained')
        feedback = request.data.get('feedback', '')
        
        if not answer_id:
            return Response(
                {'error': 'answer_id is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            answer = Answer.objects.get(id=answer_id)
        except Answer.DoesNotExist:
            return Response(
                {'error': 'Answer not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        user = request.user
        exam = answer.attempt.exam
        attempt = answer.attempt
        
        # ============ CHECK PERMISSION ============
        if user.role == 'TEACHER':
            if exam.course.instructor != user:
                return Response(
                    {'error': 'You are not the instructor for this exam'},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif user.role == 'DEPT_HEAD':
            try:
                department = user.headed_department
                if exam.course.department != department:
                    return Response(
                        {'error': 'You can only grade exams in your department'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except:
                return Response(
                    {'error': 'You are not assigned to any department'},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif user.role not in ['ADMIN']:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # ============ VALIDATE MARKS ============
        if marks_obtained is None:
            return Response(
                {'error': 'marks_obtained is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            marks = float(marks_obtained)
            max_marks = float(answer.question.marks)
            if marks < 0 or marks > max_marks:
                return Response(
                    {'error': f'Marks must be between 0 and {max_marks}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except (ValueError, TypeError):
            return Response(
                {'error': 'Invalid marks value'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ============ SAVE GRADE ============
        with transaction.atomic():
            answer.marks_obtained = Decimal(str(marks))
            answer.graded_by = user
            answer.graded_at = timezone.now()
            answer.feedback = feedback
            answer.save()
            
            # Update attempt score
            all_answers = Answer.objects.filter(attempt=attempt)
            total_score = Decimal('0')
            all_graded = True
            
            for ans in all_answers:
                if ans.marks_obtained is not None:
                    total_score += ans.marks_obtained
                else:
                    all_graded = False
            
            attempt.score = total_score
            
            # Convert to float for percentage calculation
            total_marks_float = float(attempt.total_marks) if attempt.total_marks else 0
            total_score_float = float(total_score)
            
            if total_marks_float > 0:
                attempt.percentage = Decimal(str((total_score_float / total_marks_float) * 100))
                attempt.passed = attempt.percentage >= Decimal(str(float(exam.passing_mark)))
            else:
                attempt.percentage = Decimal('0')
                attempt.passed = False
            
            attempt.save()
            
            # Check if all answers are graded
            if all_graded:
                attempt.status = 'GRADED'
                attempt.save()
                
                # ============ UPDATE COURSE GRADE ============
                try:
                    enrollment = Enrollment.objects.get(
                        student=attempt.student,
                        course=exam.course
                    )
                    enrollment.update_course_grade()
                    logger.info(f"✅ Course grade updated for {attempt.student.user.full_name} in {exam.course.course_code}")
                except Enrollment.DoesNotExist:
                    logger.warning(f"⚠️ No enrollment found for student {attempt.student.id} in course {exam.course.id}")
                except Exception as e:
                    logger.error(f"❌ Failed to update course grade: {e}")
                
                # ============ UPDATE STUDENT CGPA ============
                try:
                    attempt.student.update_cgpa()
                    logger.info(f"✅ CGPA updated for {attempt.student.user.full_name}")
                except Exception as e:
                    logger.error(f"❌ Failed to update CGPA: {e}")
                
                # ============ SEND NOTIFICATION ============
                send_notification(
                    recipient_user=attempt.student.user,
                    title='✅ Exam Fully Graded!',
                    message=f'All answers for "{attempt.exam.title}" have been graded. Your score: {float(attempt.percentage):.1f}%',
                    notification_type='GRADE_RELEASED',
                    link='/results'
                )
            else:
                send_notification(
                    recipient_user=attempt.student.user,
                    title='📝 Answer Graded',
                    message=f'An answer for "{attempt.exam.title}" has been graded.',
                    notification_type='GRADE_RELEASED',
                    link='/results'
                )
        
        # ============ GET UPDATED GRADE SUMMARY ============
        grade_summary = None
        try:
            enrollment = Enrollment.objects.get(
                student=attempt.student,
                course=exam.course
            )
            grade_summary = enrollment.get_grade_summary()
        except Enrollment.DoesNotExist:
            pass
        
        return Response({
            'success': True,
            'message': 'Answer graded successfully',
            'answer_id': answer.id,
            'marks_obtained': float(marks),
            'feedback': feedback,
            'attempt_score': float(attempt.score) if attempt.score else 0,
            'attempt_percentage': float(attempt.percentage) if attempt.percentage else 0,
            'attempt_passed': attempt.passed,
            'all_graded': all_graded,
            'course_grade': grade_summary,
            'student_cgpa': float(attempt.student.cgpa) if attempt.student.cgpa else 0,
        }, status=status.HTTP_200_OK)
class GetEssayAnswersView(APIView):
    """Get all essay answers for a student's attempt"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, attempt_id):
        user = request.user
        
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if user.role == 'STUDENT':
            if attempt.student.user != user:
                return Response(
                    {'error': 'You can only view your own answers'},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif user.role == 'TEACHER':
            if attempt.exam.course.instructor != user:
                return Response(
                    {'error': 'You are not the instructor for this exam'},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif user.role not in ['ADMIN', 'DEPT_HEAD']:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        essay_answers = Answer.objects.filter(
            attempt=attempt,
            question__type='SHORT'
        ).select_related('question')
        
        result = []
        for answer in essay_answers:
            result.append({
                'id': answer.id,
                'question_id': answer.question.id,
                'question_text': answer.question.text,
                'answer_text': answer.answer_text,
                'marks_obtained': float(answer.marks_obtained) if answer.marks_obtained is not None else None,
                'max_marks': float(answer.question.marks),
                'graded': answer.graded_at is not None,
                'graded_by': answer.graded_by.full_name if answer.graded_by else None,
                'graded_at': answer.graded_at.isoformat() if answer.graded_at else None,
                'feedback': answer.feedback if hasattr(answer, 'feedback') else '',
            })
        
        return Response({
            'attempt_id': attempt.id,
            'student_name': attempt.student.user.full_name,
            'exam_title': attempt.exam.title,
            'essay_answers': result,
            'total_essay_marks': sum(a['max_marks'] for a in result),
            'essay_obtained_marks': sum(a['marks_obtained'] for a in result if a['marks_obtained'] is not None),
            'graded_count': sum(1 for a in result if a['graded']),
            'total_count': len(result),
            'all_graded': all(a['graded'] for a in result) if result else True
        })


# ============================================================
# FLAGGING VIEWS
# ============================================================

class FlagExamView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, attempt_id):
        if request.user.role not in ['ADMIN', 'TEACHER']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found'}, status=status.HTTP_404_NOT_FOUND)
        
        if request.user.role == 'TEACHER' and attempt.exam.course.instructor != request.user:
            return Response({'error': 'You do not have permission to flag this exam'}, status=status.HTTP_403_FORBIDDEN)
        
        reason = request.data.get('reason', 'Flagged for review')
        attempt.status = 'FLAGGED'
        attempt.save()
        
        session, created = ProctorSession.objects.get_or_create(attempt=attempt)
        session.review_status = 'FLAGGED'
        session.review_notes = f'Flagged by {request.user.full_name}. Reason: {reason}'
        session.save()
        
        send_notification(
            recipient_roles=['ADMIN'],
            title='🚨 Exam Flagged',
            message=f'Exam "{attempt.exam.title}" by {attempt.student.user.full_name} has been flagged.',
            notification_type='SYSTEM_ALERT',
            link='/admin/proctoring-review'
        )
        
        send_notification(
            recipient_user=attempt.student.user,
            title='📋 Exam Under Review',
            message=f'Your exam "{attempt.exam.title}" has been flagged for review.',
            notification_type='SYSTEM_ALERT',
            link='/results'
        )
        
        return Response({
            'message': 'Exam flagged successfully',
            'status': attempt.status,
            'session_id': session.id
        })


class UnflagExamView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, attempt_id):
        if request.user.role != 'ADMIN':
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found'}, status=status.HTTP_404_NOT_FOUND)
        
        attempt.status = 'GRADED'
        attempt.save()
        
        try:
            session = ProctorSession.objects.get(attempt=attempt)
            session.review_status = 'REVIEWED'
            session.review_notes = request.data.get('notes', f'Flag removed by {request.user.full_name}')
            session.save()
            ProctorImage.objects.filter(attempt=attempt).update(
                is_suspicious=False,
                suspicious_reason=''
            )
        except ProctorSession.DoesNotExist:
            pass
        
        send_notification(
            recipient_user=attempt.student.user,
            title='✅ Flag Removed',
            message=f'The flag on your exam "{attempt.exam.title}" has been removed.',
            notification_type='SYSTEM_ALERT',
            link='/results'
        )
        
        return Response({
            'message': 'Flag removed successfully',
            'status': attempt.status
        })


class FlaggedExamsSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        if request.user.role not in ['ADMIN', 'TEACHER']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        queryset = ExamAttempt.objects.filter(status='FLAGGED')
        
        if request.user.role == 'TEACHER':
            queryset = queryset.filter(exam__course__instructor=request.user)
        
        total = queryset.count()
        by_exam = {}
        for attempt in queryset:
            exam_title = attempt.exam.title
            by_exam[exam_title] = by_exam.get(exam_title, 0) + 1
        
        by_exam_list = [{'exam': k, 'count': v} for k, v in by_exam.items()]
        recent = queryset.filter(start_time__gte=timezone.now() - timezone.timedelta(days=7)).count()
        
        return Response({
            'total': total,
            'recent_7_days': recent,
            'by_exam': by_exam_list,
            'status': 'active'
        })


# ============================================================
# ✅ NEW VIEWS - BONUS MARKS AND EDIT ANSWER
# ============================================================

class BonusMarksView(APIView):
    """Add bonus marks to all students or a single student for an exam"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        # Check permission - only teachers, admins, and department heads
        if request.user.role not in ['TEACHER', 'ADMIN', 'DEPT_HEAD']:
            return Response(
                {'error': 'Permission denied. Only teachers, admins, and department heads can add bonus marks.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        exam_id = request.data.get('exam_id')
        bonus_marks = request.data.get('bonus_marks')
        reason = request.data.get('reason', 'Bonus marks added by teacher')
        apply_to_all = request.data.get('apply_to_all', True)
        student_id = request.data.get('student_id')
        
        if not exam_id:
            return Response(
                {'error': 'exam_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if bonus_marks is None:
            return Response(
                {'error': 'bonus_marks is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            bonus_marks = float(bonus_marks)
            if bonus_marks < 0:
                return Response(
                    {'error': 'bonus_marks must be a positive number'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except ValueError:
            return Response(
                {'error': 'bonus_marks must be a valid number'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            exam = Exam.objects.get(id=exam_id)
        except Exam.DoesNotExist:
            return Response(
                {'error': 'Exam not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if user is the instructor or admin/dept_head
        if request.user.role == 'TEACHER':
            if exam.course.instructor != request.user:
                return Response(
                    {'error': 'You are not the instructor for this exam'},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif request.user.role == 'DEPT_HEAD':
            try:
                department = request.user.headed_department
                if exam.course.department != department:
                    return Response(
                        {'error': 'You can only add bonus marks to exams in your department'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except:
                return Response(
                    {'error': 'You are not assigned to any department'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        # Get attempts to apply bonus to
        if apply_to_all:
            attempts = ExamAttempt.objects.filter(exam=exam, status__in=['SUBMITTED', 'GRADED'])
        else:
            if not student_id:
                return Response(
                    {'error': 'student_id is required when apply_to_all is false'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                student = StudentProfile.objects.get(id=student_id)
                attempts = ExamAttempt.objects.filter(exam=exam, student=student, status__in=['SUBMITTED', 'GRADED'])
            except StudentProfile.DoesNotExist:
                return Response(
                    {'error': 'Student not found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        if not attempts.exists():
            return Response(
                {'error': 'No attempts found to apply bonus marks to'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        updated_count = 0
        
        with transaction.atomic():
            for attempt in attempts:
                # Update score
                if attempt.score is not None:
                    old_score = float(attempt.score)
                    new_score = old_score + bonus_marks
                    
                    # Cap at total marks
                    if attempt.total_marks:
                        new_score = min(new_score, float(attempt.total_marks))
                    
                    attempt.score = new_score
                    
                    # Recalculate percentage
                    if attempt.total_marks and float(attempt.total_marks) > 0:
                        attempt.percentage = (new_score / float(attempt.total_marks)) * 100
                        attempt.passed = attempt.percentage >= float(exam.passing_mark)
                    
                    attempt.save()
                    
                    # Log the bonus in answers
                    try:
                        if attempt.answers:
                            attempt.answers['bonus'] = {
                                'marks': bonus_marks,
                                'reason': reason,
                                'added_by': request.user.full_name,
                                'added_at': timezone.now().isoformat()
                            }
                        else:
                            attempt.answers = {
                                'bonus': {
                                    'marks': bonus_marks,
                                    'reason': reason,
                                    'added_by': request.user.full_name,
                                    'added_at': timezone.now().isoformat()
                                }
                            }
                        attempt.save()
                    except:
                        pass
                    
                    updated_count += 1
                    
                    # Send notification to student
                    send_notification(
                        recipient_user=attempt.student.user,
                        title='⭐ Bonus Marks Added!',
                        message=f'You received {bonus_marks} bonus marks for "{exam.title}". Reason: {reason}',
                        notification_type='GRADE_RELEASED',
                        link='/results'
                    )
        
        return Response({
            'success': True,
            'message': f'Bonus marks applied to {updated_count} student(s)',
            'updated_count': updated_count,
            'bonus_marks': bonus_marks,
            'reason': reason,
            'apply_to_all': apply_to_all
        }, status=status.HTTP_200_OK)


class EditAnswerView(APIView):
    """Edit a student's answer marks (override auto-graded answers)"""
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        # Check permission - only teachers, admins, and department heads
        if request.user.role not in ['TEACHER', 'ADMIN', 'DEPT_HEAD']:
            return Response(
                {'error': 'Permission denied. Only teachers, admins, and department heads can edit answers.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        answer_id = request.data.get('answer_id')
        marks_obtained = request.data.get('marks_obtained')
        
        if not answer_id:
            return Response(
                {'error': 'answer_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if marks_obtained is None:
            return Response(
                {'error': 'marks_obtained is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            answer = Answer.objects.get(id=answer_id)
        except Answer.DoesNotExist:
            return Response(
                {'error': 'Answer not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check permission
        exam = answer.attempt.exam
        
        if request.user.role == 'TEACHER':
            if exam.course.instructor != request.user:
                return Response(
                    {'error': 'You are not the instructor for this exam'},
                    status=status.HTTP_403_FORBIDDEN
                )
        elif request.user.role == 'DEPT_HEAD':
            try:
                department = request.user.headed_department
                if exam.course.department != department:
                    return Response(
                        {'error': 'You can only edit answers for exams in your department'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except:
                return Response(
                    {'error': 'You are not assigned to any department'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        try:
            marks_obtained = float(marks_obtained)
            max_marks = float(answer.question.marks)
            if marks_obtained < 0 or marks_obtained > max_marks:
                return Response(
                    {'error': f'Marks must be between 0 and {max_marks}'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except ValueError:
            return Response(
                {'error': 'marks_obtained must be a valid number'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update the answer
        answer.marks_obtained = marks_obtained
        answer.graded_by = request.user
        answer.graded_at = timezone.now()
        answer.is_correct = marks_obtained > 0  # Mark as correct if they got any marks
        answer.save()
        
        # Recalculate attempt score
        attempt = answer.attempt
        all_answers = Answer.objects.filter(attempt=attempt)
        total_score = 0
        
        for ans in all_answers:
            if ans.marks_obtained is not None:
                total_score += float(ans.marks_obtained)
        
        attempt.score = total_score
        if attempt.total_marks and float(attempt.total_marks) > 0:
            attempt.percentage = (total_score / float(attempt.total_marks)) * 100
            attempt.passed = attempt.percentage >= float(exam.passing_mark)
        attempt.save()
        
        # Send notification to student
        send_notification(
            recipient_user=attempt.student.user,
            title='📝 Answer Updated',
            message=f'An answer for "{exam.title}" has been updated by the teacher.',
            notification_type='GRADE_RELEASED',
            link='/results'
        )
        
        return Response({
            'success': True,
            'message': 'Answer updated successfully',
            'answer_id': answer.id,
            'marks_obtained': marks_obtained,
            'attempt_score': total_score,
            'attempt_percentage': attempt.percentage,
            'attempt_passed': attempt.passed
        }, status=status.HTTP_200_OK)
# exams/views.py - ADD THIS VIEW

# backend/exams/views.py - ADD THESE COMPLETE METHODS

# ============================================================
# EXAM SECURITY - COMPLETE HEARTBEAT WITH AI ANALYSIS
# ============================================================
# exams/views.py

from .trust_engine import TrustEngine

class ExamHeartbeatView(APIView):
    """
    Receive heartbeat. Server computes trust from raw signals.
    CLIENT'S trust_score IS IGNORED.
    Also handles real-time multiple-face locking.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, attempt_id):
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id, student__user=request.user)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found'}, status=404)

        # ============================================================
        # 1. CHECK FOR MULTIPLE FACES FIRST (Immediate Lock)
        # ============================================================
        multiple_faces = request.data.get('multiple_faces', False)
        face_count = request.data.get('face_count', 0)

        if multiple_faces or face_count > 1:
            attempt.suspicious_events_count += 1
            attempt.save()
            
            return Response({
                'status': 'locked',
                'is_locked': True,
                'lock_reason': f'Multiple faces detected ({face_count}). Please ensure only one person is visible.',
                'requires_recheck': True,  # Tells frontend this is a temporary lock
                'trust_score': 0,
                'suspicion_score': 100,
                'risk_level': 'CRITICAL',
                'is_flagged': attempt.ai_flagged,
                'time_since_last_heartbeat': 0,
            })

        # ============================================================
        # 2. CHECK IF ALREADY PERMANENTLY LOCKED
        # ============================================================
        if attempt.is_locked:
            return Response({
                'status': 'locked',
                'is_locked': True,
                'lock_reason': attempt.lock_reason or 'Exam locked by system.',
                'requires_recheck': False,  # Permanent lock
                'trust_score': 0,
                'suspicion_score': 100,
                'risk_level': 'CRITICAL',
                'is_flagged': True,
                'time_since_last_heartbeat': 0,
            })

        # ============================================================
        # 3. NORMAL TRUST ENGINE PROCESSING (If 1 face, no lock)
        # ============================================================
        engine = TrustEngine(attempt)
        hb_result = engine.record_heartbeat(request.data)

        # Tab switches (server-side counter)
        increment = min(int(request.data.get('tab_switch_increment', 0)), 1)
        if increment:
            attempt.tab_switch_count = (attempt.tab_switch_count or 0) + increment

        # Fullscreen exits
        fs_increment = min(int(request.data.get('fullscreen_exit_increment', 0)), 1)
        if fs_increment:
            attempt.fullscreen_exit_count = (attempt.fullscreen_exit_count or 0) + fs_increment

        # Network latency history
        latency = request.data.get('network_latency')
        if latency is not None:
            try:
                latency_val = float(latency)
                history = attempt.network_latency_history or []
                history.append(latency_val)
                history = history[-100:]
                attempt.network_latency_history = history
            except (ValueError, TypeError):
                pass

        # Compute trust SERVER-SIDE
        result = engine.save_trust_to_attempt()

        # Log if flagged
        if result['should_flag']:
            try:
                from proctoring.models import ProctorLog
                ProctorLog.objects.create(
                    attempt=attempt,
                    event_type='AUTO_FLAGGED',
                    details={
                        'source': 'server_trust_engine',
                        'trust_score': result['trust_score'],
                        'risk_level': result['risk_level'],
                    }
                )
            except Exception as e:
                logger.warning(f"Could not log flag: {e}")

        # Return OK status (Unlocks frontend if it was previously locked by multiple faces)
        return Response({
            'status': 'ok',
            'is_locked': attempt.is_locked,  # False normally, True only if TrustEngine decided to lock permanently
            'lock_reason': attempt.lock_reason if attempt.is_locked else None,
            'requires_recheck': False if attempt.is_locked else True,
            'trust_score': result['trust_score'],
            'suspicion_score': result['suspicion_score'],
            'risk_level': result['risk_level'],
            'is_flagged': attempt.ai_flagged,
            'time_since_last_heartbeat': hb_result['time_since_last'],
        })

        
# exams/views.py — REPLACE the entire FaceVerificationView class

class FaceVerificationView(APIView):
    """
    Verify student's face with combined frontend + backend detection
    AND real identity match against the enrolled face_embedding.

    POST /api/exams/attempt/<attempt_id>/face-verify/

    ✅ PRESERVED:
        - Frontend face detection signals (face_data)
        - Backend OpenCV Haar cascade detection
        - Combined verification logic
        - Multiple-face detection
        - ExamAttempt flagging

    ✅ ADDED:
        - Real identity comparison via accounts.face_service.verify_against_reference
        - Auto-flag at 3 identity failures
        - Auto-lock at 5 identity failures
        - Reset failure counter on success
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, attempt_id):
        from accounts.face_service import verify_against_reference

        # ============================================================
        # 0. LOAD ATTEMPT
        # ============================================================
        try:
            attempt = ExamAttempt.objects.get(
                id=attempt_id, student__user=request.user
            )
        except ExamAttempt.DoesNotExist:
            return Response(
                {'error': 'Attempt not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        image_data = request.data.get('image_data')
        face_data = request.data.get('face_data', {})

        if not image_data:
            return Response({
                'verified': False,
                'error': 'Image data required'
            }, status=status.HTTP_400_BAD_REQUEST)

        student = attempt.student

        # ============================================================
        # 0b. MUST BE ENROLLED
        # ============================================================
        if not student.face_enrolled or not student.face_embedding:
            return Response({
                'verified': False,
                'error': 'Face not enrolled. Please enroll your face first.',
                'needs_enrollment': True,
            }, status=status.HTTP_400_BAD_REQUEST)

        # ============================================================
        # 1. FRONTEND FACE DETECTION
        # ============================================================
        frontend_face_detected = face_data.get('face_detected', False)
        frontend_confidence = face_data.get('confidence', 0)
        frontend_face_count = face_data.get('face_count', 0)
        frontend_multiple_faces = face_data.get('multiple_faces', False)

        # ============================================================
        # 2. BACKEND OPENCV FACE DETECTION  (PRESERVED)
        # ============================================================
        backend_face_detected = False
        backend_face_count = 0
        backend_confidence = 0

        try:
            import cv2
            import base64
            import numpy as np

            # ✅ Use a local copy so we don't mutate the original string
            cleaned_image_data = image_data
            if ',' in cleaned_image_data:
                cleaned_image_data = cleaned_image_data.split(',')[1]

            image_bytes = base64.b64decode(cleaned_image_data)
            np_arr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if image is not None:
                face_cascade = cv2.CascadeClassifier(
                    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                )
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.1, 4)

                backend_face_count = len(faces)
                backend_face_detected = backend_face_count > 0
                backend_confidence = 0.85 if backend_face_detected else 0

                print(f"🔍 OpenCV detected {backend_face_count} face(s) in FaceVerificationView")

        except Exception as e:
            # OpenCV failed → fall back to frontend results (preserved behavior)
            print(f"OpenCV error in FaceVerificationView: {e}")
            backend_face_detected = frontend_face_detected
            backend_face_count = frontend_face_count
            backend_confidence = frontend_confidence

        # ============================================================
        # 3. COMBINED VERIFICATION  (PRESERVED)
        # ============================================================
        face_verified = False
        final_confidence = 0

        if frontend_face_detected and backend_face_detected:
            face_verified = True
            final_confidence = (frontend_confidence + backend_confidence) / 2
        elif frontend_face_detected:
            face_verified = True
            final_confidence = frontend_confidence * 0.8
        elif backend_face_detected:
            face_verified = True
            final_confidence = backend_confidence * 0.8

        # ============================================================
        # 4. CHECK FOR MULTIPLE FACES  (PRESERVED)
        # ============================================================
        if frontend_multiple_faces or frontend_face_count > 1 or backend_face_count > 1:
            attempt.suspicious_events_count += 1
            attempt.ai_flagged = True
            attempt.ai_flag_reason = "Multiple faces detected"
            attempt.save()

            return Response({
                'verified': False,
                'error': 'Multiple faces detected',
                'is_flagged': True
            }, status=status.HTTP_400_BAD_REQUEST)

        # ============================================================
        # 5. ✅ NEW: REAL IDENTITY MATCH
        #    Only run if we actually detected exactly one face.
        # ============================================================
        identity_verified = False
        identity_confidence = 0.0
        identity_error = None

        if face_verified and backend_face_count == 1:
            try:
                id_result = verify_against_reference(
                    image_data,
                    student.face_embedding
                )
                identity_verified = bool(id_result.get('verified', False))
                identity_confidence = float(id_result.get('confidence', 0) or 0)
                identity_error = id_result.get('error')
                print(
                    f"🔐 Identity check: verified={identity_verified}, "
                    f"confidence={identity_confidence:.2f}"
                )
            except Exception as e:
                print(f"❌ Identity check error: {e}")
                identity_error = str(e)

        # ============================================================
        # 6. FINAL VERIFICATION (identity now required)
        # ============================================================
        if face_verified and final_confidence > 0.4 and identity_verified:
            # ✅ PASS — same person as the enrolled student
            attempt.face_verified = True
            attempt.face_match_confidence = identity_confidence
            attempt.save()

            # Reset failure counter on success
            student.face_verification_failures = 0
            student.face_last_verified_at = timezone.now()
            student.save(update_fields=[
                'face_verification_failures',
                'face_last_verified_at'
            ])

            return Response({
                'verified': True,
                'confidence': identity_confidence,
                'detection_confidence': final_confidence,
                'identity_confidence': identity_confidence,
                'frontend_detected': frontend_face_detected,
                'backend_detected': backend_face_detected,
                'is_flagged': False,
                'message': 'Face verified (detection + identity)'
            })

        # ============================================================
        # 7. ❌ IDENTITY MISMATCH — flag / lock the attempt
        # ============================================================
        if face_verified and backend_face_count == 1 and not identity_verified:
            student.face_verification_failures = (
                student.face_verification_failures or 0
            ) + 1
            student.save(update_fields=['face_verification_failures'])

            is_flagged = False
            is_locked = False

            attempt.face_verified = False
            attempt.face_match_confidence = identity_confidence
            attempt.suspicious_events_count += 1

            if student.face_verification_failures >= 3:
                attempt.ai_flagged = True
                attempt.ai_flag_reason = (
                    f"Face identity mismatch x"
                    f"{student.face_verification_failures}"
                )
                attempt.status = 'FLAGGED'
                is_flagged = True

            if student.face_verification_failures >= 5:
                attempt.is_locked = True
                attempt.lock_reason = "Face verification failed 5 times"
                is_locked = True

            attempt.save()

            # Notify admin on flag
            if is_flagged:
                try:
                    send_notification(
                        recipient_roles=['ADMIN'],
                        title='🚨 Face Identity Mismatch',
                        message=(
                            f"Student {student.user.full_name} failed face "
                            f"identity verification "
                            f"{student.face_verification_failures} times "
                            f"during exam {attempt.exam.title}."
                        ),
                        notification_type='SYSTEM_ALERT',
                        link='/admin/proctoring-review'
                    )
                except Exception as e:
                    print(f"⚠️ Notification failed: {e}")

            return Response({
                'verified': False,
                'error': identity_error or 'Face does not match enrolled student',
                'detection_confidence': final_confidence,
                'identity_confidence': identity_confidence,
                'frontend_detected': frontend_face_detected,
                'backend_detected': backend_face_detected,
                'is_flagged': is_flagged,
                'is_locked': is_locked,
                'failure_count': student.face_verification_failures,
            }, status=status.HTTP_400_BAD_REQUEST)

        # ============================================================
        # 8. VERIFICATION FAILED (no face / low confidence)  (PRESERVED)
        # ============================================================
        return Response({
            'verified': False,
            'error': 'Face verification failed',
            'frontend_detected': frontend_face_detected,
            'backend_detected': backend_face_detected,
            'frontend_confidence': frontend_confidence,
            'backend_confidence': backend_confidence,
            'is_flagged': False
        }, status=status.HTTP_400_BAD_REQUEST)
    """
    Verify student's face with combined frontend + backend detection
    POST /api/exams/attempt/<attempt_id>/face-verify/
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, attempt_id):
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id, student__user=request.user)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found'}, status=status.HTTP_404_NOT_FOUND)
        
        image_data = request.data.get('image_data')
        face_data = request.data.get('face_data', {})
        
        if not image_data:
            return Response({
                'verified': False,
                'error': 'Image data required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ============================================================
        # FRONTEND FACE DETECTION
        # ============================================================
        frontend_face_detected = face_data.get('face_detected', False)
        frontend_confidence = face_data.get('confidence', 0)
        frontend_face_count = face_data.get('face_count', 0)
        frontend_multiple_faces = face_data.get('multiple_faces', False)
        
        # ============================================================
        # BACKEND OPENCV FACE DETECTION
        # ============================================================
        backend_face_detected = False
        backend_face_count = 0
        backend_confidence = 0
        
        try:
            import cv2
            import base64
            import numpy as np
            
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            image_bytes = base64.b64decode(image_data)
            np_arr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            if image is not None:
                face_cascade = cv2.CascadeClassifier(
                    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                )
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                
                backend_face_count = len(faces)
                backend_face_detected = backend_face_count > 0
                backend_confidence = 0.85 if backend_face_detected else 0
                
        except Exception as e:
            print(f"OpenCV error in FaceVerificationView: {e}")
            backend_face_detected = frontend_face_detected
            backend_face_count = frontend_face_count
            backend_confidence = frontend_confidence
        
        # ============================================================
        # COMBINED VERIFICATION
        # ============================================================
        face_verified = False
        final_confidence = 0
        
        if frontend_face_detected and backend_face_detected:
            face_verified = True
            final_confidence = (frontend_confidence + backend_confidence) / 2
        elif frontend_face_detected:
            face_verified = True
            final_confidence = frontend_confidence * 0.8
        elif backend_face_detected:
            face_verified = True
            final_confidence = backend_confidence * 0.8
        
        # Check multiple faces
        if frontend_multiple_faces or frontend_face_count > 1 or backend_face_count > 1:
            attempt.suspicious_events_count += 1
            attempt.ai_flagged = True
            attempt.ai_flag_reason = f"Multiple faces detected"
            attempt.save()
            
            return Response({
                'verified': False,
                'error': 'Multiple faces detected',
                'is_flagged': True
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Final verification
        if face_verified and final_confidence > 0.4:
            attempt.face_verified = True
            attempt.face_match_confidence = final_confidence
            attempt.save()
            
            return Response({
                'verified': True,
                'confidence': final_confidence,
                'frontend_detected': frontend_face_detected,
                'backend_detected': backend_face_detected,
                'is_flagged': False,
                'message': 'Face verified'
            })
        
        return Response({
            'verified': False,
            'error': 'Face verification failed',
            'frontend_detected': frontend_face_detected,
            'backend_detected': backend_face_detected,
            'is_flagged': False
        }, status=status.HTTP_400_BAD_REQUEST)

# exams/views.py - ADD THIS

class GazeAnalysisView(APIView):
    """
    Analyze gaze tracking data in real-time
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, attempt_id):
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id, student__user=request.user)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found'}, status=status.HTTP_404_NOT_FOUND)
        
        gaze_data = request.data.get('gaze_data', {})
        
        ai_proctor = AIProctorBackend()
        result = ai_proctor.analyze_gaze_data(attempt, gaze_data)
        
        return Response(result)
# exams/views.py - ADD THIS

class ObjectDetectionView(APIView):
    """
    Analyze detected objects in proctoring feed
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, attempt_id):
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id, student__user=request.user)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found'}, status=status.HTTP_404_NOT_FOUND)
        
        objects = request.data.get('objects', [])
        
        ai_proctor = AIProctorBackend()
        result = ai_proctor.analyze_objects_detected(attempt, objects)
        
        return Response(result)  
 # exams/views.py - ADD THIS VIEW

# exams/views.py — REPLACE the entire VerifyFaceView class

class VerifyFaceView(APIView):
    """
    Face verification: Frontend + Backend (OpenCV) + IDENTITY MATCH.

    POST /api/exams/verify-face/

    Requirements (all three must pass):
      1. Frontend detected a face
      2. OpenCV backend detected exactly ONE face
      3. Live image identity-matches the enrolled student's face_embedding
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from accounts.face_service import verify_against_reference
        from accounts.models import StudentProfile

        image_data = request.data.get('image_data')
        exam_id = request.data.get('exam_id')
        face_data = request.data.get('face_data', {})

        # ---------- 1. Input ----------
        if not image_data:
            return Response(
                {'verified': False, 'error': 'Image data is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # ---------- 2. Frontend signals ----------
        frontend_face_detected = bool(face_data.get('face_detected', False))
        frontend_face_count = int(face_data.get('face_count', 0) or 0)
        frontend_multiple_faces = bool(face_data.get('multiple_faces', False))

        # ---------- 3. Student + enrollment ----------
        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return Response(
                {'verified': False, 'error': 'Student profile not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not student.face_enrolled or not student.face_embedding:
            return Response({
                'verified': False,
                'error': 'Face not enrolled.',
                'needs_enrollment': True,
            }, status=status.HTTP_400_BAD_REQUEST)

        # ---------- 4. Backend OpenCV detection (fail-closed) ----------
        backend_face_detected = False
        backend_face_count = 0

        try:
            import cv2
            import base64
            import numpy as np

            cleaned = image_data.split(',')[1] if ',' in image_data else image_data
            image_bytes = base64.b64decode(cleaned)
            np_arr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if image is None:
                return Response({
                    'verified': False,
                    'error': 'Could not decode image',
                }, status=status.HTTP_400_BAD_REQUEST)

            cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            faces = cascade.detectMultiScale(gray, 1.1, 4)

            backend_face_count = len(faces)
            backend_face_detected = backend_face_count > 0
            print(f"🔍 OpenCV detected {backend_face_count} face(s)")

        except ImportError as e:
            # Not supposed to happen — opencv is installed
            logger.error(f"OpenCV import failed: {e}")
            return Response({
                'verified': False,
                'error': 'Server face detection unavailable.',
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        except Exception as e:
            logger.error(f"OpenCV error: {e}")
            return Response({
                'verified': False,
                'error': f'Face detection error: {e}',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # ---------- 5. Multiple faces → hard fail ----------
        if (frontend_multiple_faces
                or frontend_face_count > 1
                or backend_face_count > 1):
            if exam_id:
                try:
                    attempt = ExamAttempt.objects.get(id=exam_id)
                    attempt.suspicious_events_count += 1
                    attempt.ai_flagged = True
                    attempt.ai_flag_reason = (
                        f"Multiple faces detected "
                        f"(F:{frontend_face_count}, B:{backend_face_count})"
                    )
                    attempt.save()
                except ExamAttempt.DoesNotExist:
                    pass
            return Response({
                'verified': False,
                'error': 'Multiple faces detected',
                'frontend_face_count': frontend_face_count,
                'backend_face_count': backend_face_count,
                'is_flagged': True,
            }, status=status.HTTP_400_BAD_REQUEST)

        # ---------- 6. Require BOTH detectors to see a face ----------
        detection_ok = (
            frontend_face_detected
            and backend_face_detected
            and backend_face_count == 1
        )

        if not detection_ok:
            return Response({
                'verified': False,
                'error': 'Face not detected by both frontend and backend.',
                'frontend_detected': frontend_face_detected,
                'backend_detected': backend_face_detected,
                'backend_face_count': backend_face_count,
            }, status=status.HTTP_400_BAD_REQUEST)

        # ---------- 7. ✅ Real identity match (dlib / face_recognition) ----------
        try:
            id_result = verify_against_reference(
                image_data, student.face_embedding
            )
        except Exception as e:
            logger.error(f"Identity check error: {e}")
            return Response({
                'verified': False,
                'error': f'Identity check error: {e}',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        identity_verified = bool(id_result.get('verified', False))
        identity_confidence = float(id_result.get('confidence', 0) or 0)

        # ---------- 8. Persist + escalate ----------
        is_flagged = False
        is_locked = False

        if exam_id:
            try:
                attempt = ExamAttempt.objects.get(id=exam_id)
                attempt.face_verified = identity_verified
                attempt.face_match_confidence = identity_confidence

                if not identity_verified:
                    attempt.suspicious_events_count += 1
                    student.face_verification_failures = (
                        student.face_verification_failures or 0
                    ) + 1
                    student.save(update_fields=['face_verification_failures'])

                    if student.face_verification_failures >= 3:
                        attempt.ai_flagged = True
                        attempt.ai_flag_reason = (
                            f"Face identity mismatch x"
                            f"{student.face_verification_failures}"
                        )
                        attempt.status = 'FLAGGED'
                        is_flagged = True

                    if student.face_verification_failures >= 5:
                        attempt.is_locked = True
                        attempt.lock_reason = "Face verification failed 5 times"
                        is_locked = True
                else:
                    student.face_verification_failures = 0
                    student.face_last_verified_at = timezone.now()
                    student.save(update_fields=[
                        'face_verification_failures',
                        'face_last_verified_at',
                    ])

                attempt.save()
            except ExamAttempt.DoesNotExist:
                pass

        # ---------- 9. Response ----------
        if identity_verified:
            return Response({
                'verified': True,
                'confidence': identity_confidence,
                'face_count': 1,
                'frontend_detected': True,
                'backend_detected': True,
                'is_flagged': False,
                'message': 'Face verified (frontend + OpenCV + identity)',
            })

        return Response({
            'verified': False,
            'error': id_result.get('error') or 'Face does not match enrolled student',
            'identity_confidence': identity_confidence,
            'frontend_detected': frontend_face_detected,
            'backend_detected': backend_face_detected,
            'is_flagged': is_flagged,
            'is_locked': is_locked,
            'failure_count': student.face_verification_failures,
        }, status=status.HTTP_400_BAD_REQUEST)


class ExamRecordingUploadView(APIView):
    """
    Upload a video chunk.
    POST /api/exams/attempt/<id>/recording/
    Body (multipart): chunk=file, chunk_index=int, duration=float
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, attempt_id):
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id, student__user=request.user)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found'}, status=404)

        chunk = request.FILES.get('chunk')
        chunk_index = request.data.get('chunk_index')
        duration = request.data.get('duration', 0)

        if not chunk:
            return Response({'error': 'chunk file required'}, status=400)
        if chunk_index is None:
            return Response({'error': 'chunk_index required'}, status=400)

        try:
            chunk_index = int(chunk_index)
        except (ValueError, TypeError):
            return Response({'error': 'chunk_index must be int'}, status=400)

        # Size limit: 10MB per chunk
        if chunk.size > 10 * 1024 * 1024:
            return Response({'error': 'Chunk too large (max 10MB)'}, status=400)

        # Save
        filename = f"attempt_{attempt_id}_chunk_{chunk_index:05d}.webm"

        try:
            recording, created = ExamRecording.objects.update_or_create(
                attempt=attempt,
                chunk_index=chunk_index,
                defaults={
                    'duration_seconds': float(duration or 0),
                    'size_bytes': chunk.size,
                }
            )
            recording.chunk_file.save(filename, ContentFile(chunk.read()), save=True)

            return Response({
                'success': True,
                'chunk_index': chunk_index,
                'total_chunks': ExamRecording.objects.filter(attempt=attempt).count(),
                'recording_id': recording.id,
            })
        except Exception as e:
            logger.error(f"Recording upload error: {e}")
            return Response({'error': str(e)}, status=500)


class ExamRecordingListView(APIView):
    """
    Get all recording chunks (for admin review).
    GET /api/exams/attempt/<id>/recording/
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, attempt_id):
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found'}, status=404)

        # Permission: student can see own, staff can see any in scope
        user = request.user
        if user.role == 'STUDENT':
            if attempt.student.user != user:
                return Response({'error': 'Permission denied'}, status=403)
        elif user.role == 'TEACHER':
            if attempt.exam.course.instructor != user:
                return Response({'error': 'Permission denied'}, status=403)

        recordings = ExamRecording.objects.filter(attempt=attempt).order_by('chunk_index')

        return Response({
            'attempt_id': attempt_id,
            'total_chunks': recordings.count(),
            'total_size_mb': sum(r.size_bytes for r in recordings) / (1024 * 1024),
            'chunks': [
                {
                    'index': r.chunk_index,
                    'url': request.build_absolute_uri(r.chunk_file.url) if r.chunk_file else None,
                    'duration': r.duration_seconds,
                    'size_kb': round(r.size_bytes / 1024, 1),
                    'uploaded_at': r.uploaded_at.isoformat(),
                }
                for r in recordings
            ]
        })        
class EnvironmentCheckView(APIView):
    """Log environment check results."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, attempt_id):
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id, student__user=request.user)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found'}, status=404)

        env_data = request.data

        # Log to proctor logs
        try:
            from proctoring.models import ProctorLog
            ProctorLog.objects.create(
                attempt=attempt,
                event_type='OBJECT_DETECTED',  # reuse or add new type
                details={
                    'type': 'environment_check',
                    'flags': env_data.get('flags', []),
                    'severity': env_data.get('severity', 'LOW'),
                    'is_vm': env_data.get('isVM', False),
                    'is_rdp': env_data.get('isRDP', False),
                    'is_virtual_camera': env_data.get('isVirtualCamera', False),
                    'is_automated': env_data.get('isAutomated', False),
                }
            )
        except Exception as e:
            logger.error(f"Failed to log env check: {e}")

        # Increment suspicion for critical
        severity = env_data.get('severity', 'LOW')
        if severity == 'CRITICAL':
            attempt.suspicious_events_count += 3
            attempt.save()
        elif severity == 'HIGH':
            attempt.suspicious_events_count += 1
            attempt.save()

        return Response({'success': True})
# ============================================================
# FACE IDENTITY VERIFICATION (delegates to accounts.views)
# ============================================================

class VerifyFaceIdentityView(APIView):
    """
    POST /api/exams/verify-face-identity/
    Body: {"image_data": "...", "attempt_id": 123}
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from accounts.views import VerifyFaceAtExamView
        return VerifyFaceAtExamView().post(request)
class CountFacesView(APIView):
    """
    Count faces in an image using UniFace RetinaFace (already installed).
    Replaces the old face_recognition/dlib implementation to avoid 500MB dlib.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        image_data = request.data.get('image_data')
        if not image_data:
            return Response({'face_count': 0, 'error': 'No image'}, status=400)

        try:
            import cv2
            import numpy as np
            import base64
            from accounts.face_service import retina

            # Strip the data URL prefix if present
            cleaned = image_data.split(',')[1] if ',' in image_data else image_data

            # Decode to numpy array, then to OpenCV BGR image
            img_bytes = base64.b64decode(cleaned)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            if img is None:
                return Response({'face_count': 0, 'error': 'Invalid image'}, status=200)

            # RetinaFace detects faces — returns a list
            faces = retina.detect(img)
            return Response({'face_count': len(faces)})

        except Exception as e:
            return Response({'face_count': 0, 'error': str(e)}, status=200)

# In exams/views.py or analytics/views.py
class UpcomingExamWarningsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if request.user.role != 'STUDENT':
            return Response([])
            
        student = request.user.student_profile
        
        # Check if student has profile picture
        has_photo = bool(request.user.profile_picture)
        
        # Get exams starting in the next 7 days
        from exams.models import Exam
        from django.utils import timezone
        import datetime
        
        upcoming_exams = Exam.objects.filter(
            course__in=student.enrollments.filter(status='ACTIVE').values('course'),
            start_time__gte=timezone.now(),
            start_time__lte=timezone.now() + datetime.timedelta(days=7)
        )
        
        warnings = []
        if not has_photo:
            warnings.append({
                'type': 'MISSING_PROFILE_PHOTO',
                'message': 'You have upcoming exams but no profile photo. Please upload one immediately.',
                'action_url': '/profile'
            })
            
        if not student.face_enrolled:
            warnings.append({
                'type': 'MISSING_FACE_ENROLLMENT',
                'message': 'You have not enrolled your face. Please do so before your exam.',
                'action_url': '/enroll-face'
            })
            
        return Response({
            'has_profile_photo': has_photo,
            'face_enrolled': student.face_enrolled,
            'upcoming_exams_count': upcoming_exams.count(),
            'warnings': warnings
        })

   # ============================================================
# LIVE EXAM MONITORING VIEW
# ============================================================

class LiveExamMonitoringView(APIView):
    """
    Teacher can see students currently taking an exam.

    GET /api/exams/<exam_id>/live-monitoring/
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, exam_id):

        user = request.user

        # Check permissions
        if user.role not in ['TEACHER', 'ADMIN', 'DEPT_HEAD']:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Get exam
        try:
            exam = Exam.objects.get(id=exam_id)

        except Exam.DoesNotExist:
            return Response(
                {'error': 'Exam not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Check teacher permission
        is_owner = user.role == 'TEACHER' and exam.course.instructor == user
        is_examiner = user.role == 'TEACHER' and ExaminerAssignment.objects.filter(
            exam=exam,
            examiner=user,
            attempt__status='IN_PROGRESS',
        ).exists()
        if user.role == 'TEACHER' and not is_owner and not is_examiner:
            return Response(
                {'error': 'You can only monitor your own courses'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check department head permission
        if user.role == 'DEPT_HEAD':
            try:
                department = user.headed_department

                if exam.course.department != department:
                    return Response(
                        {'error': 'You can only monitor exams in your department'},
                        status=status.HTTP_403_FORBIDDEN
                    )

            except Exception:
                return Response(
                    {'error': 'You are not assigned to a department'},
                    status=status.HTTP_403_FORBIDDEN
                )

        # Get active exam attempts
        attempts = ExamAttempt.objects.filter(
            exam=exam,
            status='IN_PROGRESS'
        ).select_related(
            'student__user',
            'examiner_assignment__examiner',
        ).order_by('-start_time')
        if user.role == 'TEACHER' and not is_owner:
            attempts = attempts.filter(examiner_assignment__examiner=user)

        result = []

        for attempt in attempts:

            latest_image = None

            # Get latest proctoring image
            try:
                capture = ProctorImage.objects.filter(
                    attempt=attempt
                ).order_by('-capture_time').first()

                if capture and capture.image:
                    latest_image = request.build_absolute_uri(
                        capture.image.url
                    )

            except Exception as e:
                logger.warning(
                    f"Could not retrieve latest image for attempt {attempt.id}: {e}"
                )

            result.append({
                'attempt_id': attempt.id,
                'student_id': attempt.student.student_id,
                'user_id': attempt.student.user_id,
                'student_name': attempt.student.user.full_name,
                'started_at': attempt.start_time,
                'end_time': attempt.end_time,
                'face_verified': getattr(attempt, 'face_verified', False),
                'face_match_confidence': getattr(
                    attempt,
                    'face_match_confidence',
                    0
                ),
                'suspicious_events_count': getattr(
                    attempt,
                    'suspicious_events_count',
                    0
                ),
                'latest_image': latest_image,
                'status': attempt.status,
                'assigned_examiner_id': (
                    attempt.examiner_assignment.examiner_id
                    if hasattr(attempt, 'examiner_assignment')
                    else None
                ),
                'assigned_examiner_name': (
                    attempt.examiner_assignment.examiner.full_name
                    if hasattr(attempt, 'examiner_assignment')
                    else None
                ),
            })

        return Response({
            'exam_id': exam.id,
            'exam_title': exam.title,
            'total_active': len(result),
            'students': result
        })


class ExaminerAssignmentView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, exam_id):
        try:
            exam = Exam.objects.select_related('course__department').get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)

        if request.user.role != 'TEACHER':
            return Response({'error': 'Only the course instructor can assign examiners'}, status=status.HTTP_403_FORBIDDEN)
        is_owner = exam.course.instructor_id == request.user.id
        is_assigned = ExaminerAssignment.objects.filter(
            exam=exam,
            examiner=request.user,
            attempt__status='IN_PROGRESS',
        ).exists()
        if not is_owner and not is_assigned:
            return Response({'error': 'You are not assigned to this exam'}, status=status.HTTP_403_FORBIDDEN)

        options = []
        if is_owner and exam.course.department:
            options = list(
                TeacherProfile.objects.filter(
                    department=exam.course.department.name,
                    user__role='TEACHER',
                    user__is_active=True,
                ).exclude(user=exam.course.instructor).values(
                    'user_id', 'user__full_name',
                ).order_by('user__full_name')
            )
        return Response({
            'can_assign': is_owner,
            'examiners': [{'id': row['user_id'], 'full_name': row['user__full_name']} for row in options],
        })

    def post(self, request, exam_id):
        try:
            exam = Exam.objects.select_related('course__department').get(id=exam_id)
        except Exam.DoesNotExist:
            return Response({'error': 'Exam not found'}, status=status.HTTP_404_NOT_FOUND)

        if request.user.role != 'TEACHER' or exam.course.instructor_id != request.user.id:
            return Response({'error': 'Only the course instructor can assign examiners'}, status=status.HTTP_403_FORBIDDEN)

        attempt_ids = request.data.get('attempt_ids')
        examiner_id = request.data.get('examiner_id')
        if not isinstance(attempt_ids, list) or not attempt_ids or not examiner_id:
            return Response({'error': 'Select an examiner and at least one active student'}, status=status.HTTP_400_BAD_REQUEST)
        if any(not isinstance(attempt_id, int) or isinstance(attempt_id, bool) for attempt_id in attempt_ids):
            return Response({'error': 'Student attempt identifiers must be integers'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            examiner_id = int(examiner_id)
        except (TypeError, ValueError):
            return Response({'error': 'Select a valid department examiner'}, status=status.HTTP_400_BAD_REQUEST)
        if examiner_id < 1:
            return Response({'error': 'Select a valid department examiner'}, status=status.HTTP_400_BAD_REQUEST)
        if not exam.course.department:
            return Response({'error': 'The course must have a department before examiners can be assigned'}, status=status.HTTP_400_BAD_REQUEST)

        examiner = TeacherProfile.objects.filter(
            user_id=examiner_id,
            user__role='TEACHER',
            user__is_active=True,
            department=exam.course.department.name,
        ).select_related('user').first()
        if not examiner:
            return Response({'error': 'The selected examiner is not an active teacher in this department'}, status=status.HTTP_400_BAD_REQUEST)

        attempts = ExamAttempt.objects.filter(
            id__in=attempt_ids,
            exam=exam,
            status='IN_PROGRESS',
        )
        if attempts.count() != len(set(attempt_ids)):
            return Response({'error': 'One or more selected students are no longer taking this exam'}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            ExaminerAssignment.objects.filter(attempt__in=attempts).delete()
            ExaminerAssignment.objects.bulk_create([
                ExaminerAssignment(
                    exam=exam,
                    attempt=attempt,
                    examiner=examiner.user,
                    assigned_by=request.user,
                )
                for attempt in attempts
            ])

        return Response({'message': 'Examiner assigned to selected students', 'assigned_count': attempts.count()})


class CourseProctoringImagesView(APIView):
    """List captured proctoring images for one course and exam category."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, course_id):
        user = request.user
        if user.role not in ['TEACHER', 'ADMIN', 'DEPT_HEAD']:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)

        try:
            course = Course.objects.select_related('department', 'instructor').get(id=course_id)
        except Course.DoesNotExist:
            return Response({'error': 'Course not found'}, status=status.HTTP_404_NOT_FOUND)

        if user.role == 'TEACHER' and course.instructor_id != user.id:
            return Response(
                {'error': 'You can only view proctoring images for your courses'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if user.role == 'DEPT_HEAD':
            try:
                if course.department_id != user.headed_department.id:
                    return Response(
                        {'error': 'You can only view images for courses in your department'},
                        status=status.HTTP_403_FORBIDDEN,
                    )
            except (AttributeError, ObjectDoesNotExist):
                return Response(
                    {'error': 'You are not assigned to a department'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        exam_type = request.query_params.get('exam_type', '').upper()
        valid_exam_types = {choice[0] for choice in Exam.EXAM_TYPE_CHOICES}
        if exam_type not in valid_exam_types:
            return Response(
                {'error': 'exam_type must be QUIZ, MID, or FINAL'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        images = ProctorImage.objects.filter(
            attempt__exam__course=course,
            attempt__exam__exam_type=exam_type,
        ).select_related(
            'attempt__student__user',
            'attempt__exam',
        ).order_by('-capture_time', '-id')

        student_id = request.query_params.get('student_id')
        if student_id is not None:
            if not student_id.isdecimal():
                return Response(
                    {'error': 'student_id must be a valid student profile ID'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            images = images.filter(attempt__student_id=student_id)

        students = images.values(
            'attempt__student_id',
            'attempt__student__user__full_name',
            'attempt__student__student_id',
        ).annotate(image_count=Count('id')).order_by(
            'attempt__student__user__full_name',
            'attempt__student_id',
        )

        return Response({
            'course_id': course.id,
            'course_title': course.title,
            'exam_type': exam_type,
            'total_images': images.count(),
            'students': [
                {
                    'id': student['attempt__student_id'],
                    'name': student['attempt__student__user__full_name'],
                    'student_id': student['attempt__student__student_id'],
                    'image_count': student['image_count'],
                }
                for student in students
            ],
            'selected_student_id': int(student_id) if student_id is not None else None,
            'images': [
                {
                    'id': image.id,
                    'image': request.build_absolute_uri(image.image.url) if image.image else None,
                    'capture_time': image.capture_time,
                    'is_suspicious': image.is_suspicious,
                    'suspicious_reason': image.suspicious_reason,
                    'exam_id': image.attempt.exam_id,
                    'exam_title': image.attempt.exam.title,
                    'attempt_id': image.attempt_id,
                    'student_name': image.attempt.student.user.full_name,
                    'student_id': image.attempt.student.student_id,
                }
                for image in images
            ],
        })

class SEBEntryView(APIView):
    permission_classes = []  
    authentication_classes = []

    def get(self, request, exam_id):
        try:
            exam = Exam.objects.get(id=exam_id, is_published=True, seb_enabled=True)
        except Exam.DoesNotExist:
            return Response({'error': 'Exam not available via SEB'}, status=status.HTTP_404_NOT_FOUND)

        received_hash = request.headers.get('X-SafeExamBrowser-ConfigKeyHash', '')
        absolute_url = request.build_absolute_uri()

        logger.info(f"SEB URL seen by backend: {absolute_url}")
        logger.info(f"SEB key stored: {exam.seb_config_key}")
        logger.info(f"SEB hash received: {received_hash}")

        # ✅ TEMPORARILY DISABLED FOR TESTING
        # if not verify_config_key_hash(absolute_url, exam.seb_config_key, received_hash):
        #     return Response({'error': 'Safe Exam Browser verification failed.'}, status=status.HTTP_403_FORBIDDEN)

        if not request.user or not request.user.is_authenticated:
            frontend = getattr(django_settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')
            return redirect(f"{frontend}/login?seb_return=/exams/{exam.id}/start")

        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=status.HTTP_403_FORBIDDEN)

        from datetime import timedelta
        session = SEBSession.objects.create(
            student=student,
            exam=exam,
            expires_at=timezone.now() + timedelta(seconds=120),
        )

        frontend = getattr(django_settings, 'FRONTEND_URL', 'http://localhost:3000').rstrip('/')
        response = redirect(f"{frontend}/exams/{exam.id}/start")
        response.set_cookie(
            'seb_session_id', str(session.id), max_age=120, httponly=True,
            secure=not django_settings.DEBUG, samesite='Lax', path=f'/',
        )
        return response

class SEBDownloadView(APIView):
    """
    GET /api/exams/<exam_id>/seb-config/
    Serves the .seb config file so the OS can hand it to Safe Exam Browser.
    This endpoint is intentionally public — the .seb file contains only browser
    settings and the startURL; it has no exam questions or sensitive data.
    Real security is enforced at seb-entry (ConfigKeyHash) and start-exam
    (seb_session_id cookie + JWT). The file is served inline (not as an
    attachment) so the seb:// URL scheme can open SEB directly without a download.
    """
    permission_classes = []   # Public — SEB fetches this before the student logs in
    authentication_classes = []

    def get(self, request, exam_id):
        try:
            exam = Exam.objects.get(id=exam_id, is_published=True, seb_enabled=True)
        except Exam.DoesNotExist:
            return Response({'error': 'SEB config not available'}, status=status.HTTP_404_NOT_FOUND)

        if not exam.seb_config_file:
            return Response({'error': 'SEB config not generated yet'}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        if now > exam.end_time:
            return Response({'error': 'Exam has ended'}, status=status.HTTP_400_BAD_REQUEST)

        # Serve inline with application/seb content-type so the OS/browser
        # hands the file directly to the Safe Exam Browser application.
        from django.http import FileResponse
        file_handle = exam.seb_config_file.open('rb')
        response = FileResponse(
            file_handle,
            as_attachment=False,
            filename=f"exam_{exam.id}_{exam.title.replace(' ', '_')}.seb",
            content_type='application/seb',
        )
        return response