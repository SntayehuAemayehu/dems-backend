# exams/views.py - COMPLETE WITH ALL VIEWS
from decimal import Decimal
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.db import transaction
from .models import Exam, Question, ExamAttempt, Answer
from .serializers import ExamSerializer, QuestionSerializer, ExamAttemptSerializer
from accounts.models import StudentProfile
from notifications.utils import send_notification
from courses.models import Course, Enrollment
from proctoring.models import ProctorSession, ProctorImage
import logging
from .ai_proctor import AIProctorBackend

logger = logging.getLogger(__name__)


# ============================================================
# EXISTING VIEWS - PRESERVED
# ============================================================

class ExamListView(generics.ListCreateAPIView):
    serializer_class = ExamSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        
        if user.role == 'TEACHER':
            return Exam.objects.filter(course__instructor=user)
        
        elif user.role == 'STUDENT':
            try:
                student = StudentProfile.objects.get(user=user)
                if not student.is_enrolled:
                    return Exam.objects.none()
                
                enrolled_courses = Enrollment.objects.filter(
                    student=student, 
                    status='ACTIVE'
                ).values_list('course_id', flat=True)
                
                return Exam.objects.filter(
                    course__in=enrolled_courses, 
                    is_published=True,
                    course__department__name=student.department
                )
            except:
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
    
    def destroy(self, request, *args, **kwargs):
        exam = self.get_object()
        if request.user.role != 'ADMIN' and exam.created_by != request.user:
            return Response(
                {'error': 'You do not have permission to delete this exam'},
                status=status.HTTP_403_FORBIDDEN
            )
        exam.delete()
        return Response({'message': 'Exam deleted successfully'}, status=status.HTTP_200_OK)


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
        
        if request.user.role != 'ADMIN' and exam.created_by != request.user:
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
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class QuestionDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def destroy(self, request, *args, **kwargs):
        question = self.get_object()
        if request.user.role != 'ADMIN' and question.exam.created_by != request.user:
            return Response(
                {'error': 'You do not have permission to delete this question'},
                status=status.HTTP_403_FORBIDDEN
            )
        question.delete()
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
        
        now = timezone.now()
        if now < exam.start_time:
            return Response({'error': 'Exam has not started yet'}, status=status.HTTP_400_BAD_REQUEST)
        if now > exam.end_time:
            return Response({'error': 'Exam has ended'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            student = StudentProfile.objects.get(user=request.user)
        except StudentProfile.DoesNotExist:
            return Response({'error': 'Student profile not found'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not student.is_enrolled:
            return Response({'error': 'Your account is not activated'}, status=status.HTTP_400_BAD_REQUEST)
        
        if exam.course.department.name != student.department:
            return Response({'error': 'You can only take exams within your department'}, status=status.HTTP_400_BAD_REQUEST)
        
        if not Enrollment.objects.filter(student=student, course=exam.course, status='ACTIVE').exists():
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
        
        return Response({
            'attempt_id': attempt.id,
            'questions': QuestionSerializer(questions, many=True).data,
            'duration_minutes': exam.duration_minutes,
            'end_time': attempt.end_time
        })


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
            
            result.append({
                'attempt_id': attempt.id,
                'student_id': attempt.student.id,
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

class ExamHeartbeatView(APIView):
    """
    Receive heartbeat from student during exam with FULL AI analysis.
    This is the MAIN security endpoint for real-time monitoring.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, attempt_id):
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id, student__user=request.user)
        except ExamAttempt.DoesNotExist:
            return Response({'error': 'Attempt not found'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get data from request
        trust_score = request.data.get('trust_score', 100)
        network_latency = request.data.get('network_latency', 0)
        mouse_movements = request.data.get('mouse_movements', 0)
        keystrokes = request.data.get('keystrokes', 0)
        tab_switches = request.data.get('tab_switches', 0)
        violations = request.data.get('violations', 0)
        is_fullscreen = request.data.get('is_fullscreen', True)
        face_detected = request.data.get('face_detected', True)
        multiple_faces = request.data.get('multiple_faces', False)
        gaze_direction = request.data.get('gaze_direction', 'CENTER')
        gaze_confidence = request.data.get('gaze_confidence', 0)
        head_tilt_x = request.data.get('head_tilt_x', 0)
        head_tilt_y = request.data.get('head_tilt_y', 0)
        eyes_closed = request.data.get('eyes_closed', False)
        objects_detected = request.data.get('objects_detected', [])
        
        # ✅ UPDATE ATTEMPT WITH REAL-TIME DATA
        attempt.last_heartbeat = timezone.now()
        attempt.trust_score = trust_score
        attempt.tab_switch_count = tab_switches
        attempt.suspicious_events_count = violations
        
        # ✅ UPDATE GAZE DATA
        if gaze_direction:
            gaze_data = {
                'direction': gaze_direction,
                'confidence': gaze_confidence,
                'gaze_x': request.data.get('gaze_x', 0),
                'gaze_y': request.data.get('gaze_y', 0),
                'timestamp': timezone.now().isoformat()
            }
            if not attempt.gaze_analysis:
                attempt.gaze_analysis = {'history': [], 'gaze_away_count': 0}
            attempt.gaze_analysis['history'].append(gaze_data)
            if len(attempt.gaze_analysis['history']) > 100:
                attempt.gaze_analysis['history'] = attempt.gaze_analysis['history'][-100:]
            if gaze_direction != 'CENTER':
                attempt.gaze_analysis['gaze_away_count'] = attempt.gaze_analysis.get('gaze_away_count', 0) + 1
        
        # ✅ UPDATE OBJECT DETECTION
        if objects_detected:
            if not attempt.object_detection:
                attempt.object_detection = {'detected_objects': [], 'suspicious_count': 0}
            attempt.object_detection['detected_objects'].extend(objects_detected)
            attempt.object_detection['suspicious_count'] += len(objects_detected)
        
        # ✅ UPDATE HEAD ANALYSIS
        if head_tilt_x != 0 or head_tilt_y != 0:
            if not attempt.head_analysis:
                attempt.head_analysis = {'history': [], 'tilted_count': 0}
            attempt.head_analysis['history'].append({
                'tilt_x': head_tilt_x,
                'tilt_y': head_tilt_y,
                'timestamp': timezone.now().isoformat()
            })
            if abs(head_tilt_x) > 25 or abs(head_tilt_y) > 20:
                attempt.head_analysis['tilted_count'] = attempt.head_analysis.get('tilted_count', 0) + 1
        
        # ✅ UPDATE EYE ANALYSIS
        if eyes_closed:
            if not attempt.eye_analysis:
                attempt.eye_analysis = {'closed_count': 0, 'history': []}
            attempt.eye_analysis['closed_count'] = attempt.eye_analysis.get('closed_count', 0) + 1
            attempt.eye_analysis['history'].append({
                'closed': eyes_closed,
                'timestamp': timezone.now().isoformat()
            })
            if len(attempt.eye_analysis['history']) > 50:
                attempt.eye_analysis['history'] = attempt.eye_analysis['history'][-50:]
        
        # ✅ RUN AI ANALYSIS
        from .ai_proctor import AIProctorBackend
        ai_proctor = AIProctorBackend()
        analysis_result = ai_proctor.analyze_heartbeat(attempt, {
            'trust_score': trust_score,
            'network_latency': network_latency,
            'mouse_movements': mouse_movements,
            'keystrokes': keystrokes,
            'tab_switches': tab_switches,
            'violations': violations,
            'is_fullscreen': is_fullscreen,
            'face_detected': face_detected,
            'multiple_faces': multiple_faces,
            'gaze_direction': gaze_direction,
            'eyes_closed': eyes_closed,
        })
        
        attempt.save()
        
        # ✅ LOG SUSPICIOUS EVENTS TO PROCTORING
        if analysis_result.get('is_flagged'):
            from proctoring.models import ProctorLog
            ProctorLog.objects.create(
                attempt=attempt,
                event_type='AUTO_FLAGGED',
                details={
                    'reason': analysis_result.get('flag_reason', 'AI flagged'),
                    'risk_score': analysis_result.get('risk_score', 0),
                    'risk_level': analysis_result.get('risk_level', 'UNKNOWN'),
                    'violations': violations,
                    'tab_switches': tab_switches,
                }
            )
        
        return Response({
            'status': 'ok',
            'timestamp': timezone.now().isoformat(),
            'risk_score': attempt.ai_risk_score,
            'risk_level': attempt.ai_risk_level,
            'is_flagged': attempt.ai_flagged,
            'is_locked': attempt.is_locked,
            'lock_reason': attempt.lock_reason if attempt.is_locked else None,
            'suspicious_events': attempt.suspicious_events_count,
        })

class FaceVerificationView(APIView):
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

class VerifyFaceView(APIView):
    """
    Combined face verification: Frontend + Backend (OpenCV)
    POST /api/exams/verify-face/
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        image_data = request.data.get('image_data')
        exam_id = request.data.get('exam_id')
        face_data = request.data.get('face_data', {})
        
        # ============================================================
        # 1. GET FRONTEND FACE DETECTION RESULTS
        # ============================================================
        frontend_face_detected = face_data.get('face_detected', False)
        frontend_confidence = face_data.get('confidence', 0)
        frontend_face_count = face_data.get('face_count', 0)
        frontend_multiple_faces = face_data.get('multiple_faces', False)
        
        if not image_data:
            return Response({
                'verified': False,
                'error': 'Image data is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ============================================================
        # 2. BACKEND OPENCV FACE DETECTION
        # ============================================================
        backend_face_detected = False
        backend_face_count = 0
        backend_confidence = 0
        
        try:
            import cv2
            import base64
            import numpy as np
            
            # Decode base64 image
            if ',' in image_data:
                image_data = image_data.split(',')[1]
            
            image_bytes = base64.b64decode(image_data)
            np_arr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            
            if image is not None:
                # Detect faces using OpenCV
                face_cascade = cv2.CascadeClassifier(
                    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                )
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(gray, 1.1, 4)
                
                backend_face_count = len(faces)
                backend_face_detected = backend_face_count > 0
                backend_confidence = 0.85 if backend_face_detected else 0
                
                print(f"🔍 OpenCV detected {backend_face_count} face(s)")
                
        except Exception as e:
            # OpenCV failed - fallback to frontend results
            print(f"⚠️ OpenCV error: {e}")
            backend_face_detected = frontend_face_detected
            backend_face_count = frontend_face_count
            backend_confidence = frontend_confidence
        
        # ============================================================
        # 3. COMBINED VERIFICATION
        # ============================================================
        face_verified = False
        final_face_count = 0
        final_confidence = 0
        
        if frontend_face_detected and backend_face_detected:
            # ✅ Both detected a face - HIGHEST SECURITY
            face_verified = True
            final_face_count = max(frontend_face_count, backend_face_count)
            final_confidence = (frontend_confidence + backend_confidence) / 2
            print("✅ Face verified by BOTH frontend and backend")
            
        elif frontend_face_detected and not backend_face_detected:
            # Only frontend detected a face - MEDIUM SECURITY (OpenCV fallback)
            face_verified = True
            final_face_count = frontend_face_count
            final_confidence = frontend_confidence * 0.8
            print("⚠️ Using frontend-only face detection (OpenCV fallback)")
            
        elif backend_face_detected and not frontend_face_detected:
            # Only backend detected a face - Should not happen, but accept
            face_verified = True
            final_face_count = backend_face_count
            final_confidence = backend_confidence * 0.8
            print("⚠️ Using backend-only face detection")
            
        else:
            # Neither detected a face
            face_verified = False
            final_face_count = 0
            final_confidence = 0
            print("❌ No face detected by either frontend or backend")
        
        # ============================================================
        # 4. CHECK FOR MULTIPLE FACES
        # ============================================================
        if frontend_multiple_faces or frontend_face_count > 1 or backend_face_count > 1:
            if exam_id:
                try:
                    attempt = ExamAttempt.objects.get(id=exam_id)
                    attempt.suspicious_events_count += 1
                    attempt.ai_flagged = True
                    attempt.ai_flag_reason = f"Multiple faces detected (Frontend: {frontend_face_count}, Backend: {backend_face_count})"
                    attempt.save()
                except:
                    pass
            
            return Response({
                'verified': False,
                'error': f'Multiple faces detected',
                'frontend_face_count': frontend_face_count,
                'backend_face_count': backend_face_count,
                'is_flagged': True,
                'flag_reason': f'Multiple faces detected'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # ============================================================
        # 5. FINAL VERIFICATION
        # ============================================================
        if face_verified and final_face_count == 1 and final_confidence > 0.4:
            if exam_id:
                try:
                    attempt = ExamAttempt.objects.get(id=exam_id)
                    attempt.face_verified = True
                    attempt.face_match_confidence = final_confidence
                    attempt.save()
                    print(f"✅ Attempt {exam_id} face verified with confidence {final_confidence}")
                except Exception as e:
                    print(f"⚠️ Could not update attempt: {e}")
            
            return Response({
                'verified': True,
                'confidence': final_confidence,
                'face_count': final_face_count,
                'frontend_detected': frontend_face_detected,
                'backend_detected': backend_face_detected,
                'is_flagged': False,
                'message': 'Face verified successfully (combined detection)'
            })
        
        # ============================================================
        # 6. VERIFICATION FAILED
        # ============================================================
        return Response({
            'verified': False,
            'error': 'Face verification failed',
            'frontend_detected': frontend_face_detected,
            'backend_detected': backend_face_detected,
            'frontend_confidence': frontend_confidence,
            'backend_confidence': backend_confidence,
            'face_count': final_face_count,
            'is_flagged': False
        }, status=status.HTTP_400_BAD_REQUEST)