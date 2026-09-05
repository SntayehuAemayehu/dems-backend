# backend/analytics/ai_views.py
# COMPLETE AI API ENDPOINTS

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.utils import timezone
from services.openai_service import OpenAIService, AIProctorService
from accounts.models import StudentProfile
from exams.models import ExamAttempt, Answer
from notifications.utils import send_notification
import logging

logger = logging.getLogger(__name__)

openai_service = OpenAIService()
ai_proctor = AIProctorService()

# ============================================================
# 1. SMART ESSAY GRADING API
# ============================================================

class AIGradeEssayView(APIView):
    """
    Grade an essay using AI (OpenAI)
    POST /api/analytics/ai/grade-essay/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        answer_id = request.data.get('answer_id')
        
        if not answer_id:
            return Response({
                'error': 'answer_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            answer = Answer.objects.get(id=answer_id)
        except Answer.DoesNotExist:
            return Response({
                'error': 'Answer not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        user = request.user
        attempt = answer.attempt
        exam = attempt.exam
        
        if user.role == 'TEACHER':
            if exam.course.instructor != user:
                return Response({
                    'error': 'You are not the instructor for this exam'
                }, status=status.HTTP_403_FORBIDDEN)
        elif user.role not in ['ADMIN', 'DEPT_HEAD']:
            return Response({
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get model answer (if available)
        model_answer = ''
        if answer.question.type == 'SHORT':
            # Use the correct_answer as model answer if available
            model_answer = answer.question.correct_answer or ''
        
        # Grade using AI
        result = openai_service.grade_essay(
            student_answer=answer.answer_text,
            model_answer=model_answer,
            max_marks=int(answer.question.marks)
        )
        
        if result.get('success'):
            # Save the grade
            answer.marks_obtained = result.get('score', 0)
            answer.graded_by = user
            answer.graded_at = timezone.now()
            answer.feedback = result.get('feedback', '')
            answer.save()
            
            # Update attempt score
            attempt = answer.attempt
            all_answers = Answer.objects.filter(attempt=attempt)
            total_score = sum(a.marks_obtained or 0 for a in all_answers if a.marks_obtained is not None)
            attempt.score = total_score
            attempt.percentage = (total_score / attempt.exam.total_marks * 100) if attempt.exam.total_marks > 0 else 0
            attempt.passed = attempt.percentage >= float(attempt.exam.passing_mark) if attempt.exam.passing_mark else False
            attempt.save()
            
            # Notify student
            send_notification(
                recipient_user=attempt.student.user,
                title='📝 AI Graded Your Essay',
                message=f'Your essay for "{exam.title}" has been graded by AI. Score: {result.get("score")}/{answer.question.marks}',
                notification_type='GRADE_RELEASED',
                link='/results'
            )
            
            return Response({
                'success': True,
                'message': 'Essay graded successfully',
                'result': result,
                'answer_id': answer.id,
                'marks_obtained': answer.marks_obtained,
                'feedback': answer.feedback
            })
        else:
            return Response({
                'success': False,
                'error': result.get('error', 'Grading failed'),
                'message': 'AI grading failed. Please grade manually.'
            }, status=status.HTTP_400_BAD_REQUEST)

# ============================================================
# 2. AI PLAGIARISM CHECK API
# ============================================================

class AIPlagiarismCheckView(APIView):
    """
    Check text for plagiarism using AI
    POST /api/analytics/ai/plagiarism-check/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        text = request.data.get('text')
        context = request.data.get('context', '')
        
        if not text:
            return Response({
                'error': 'text is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check permission - only teachers and admins
        if request.user.role not in ['TEACHER', 'ADMIN', 'DEPT_HEAD']:
            return Response({
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        result = openai_service.check_plagiarism_ai(text, context)
        
        return Response(result)

# ============================================================
# 3. AI QUESTION GENERATION API
# ============================================================

class AIGenerateQuestionsView(APIView):
    """
    Generate exam questions using AI
    POST /api/analytics/ai/generate-questions/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        topic = request.data.get('topic')
        difficulty = request.data.get('difficulty', 'medium')
        count = request.data.get('count', 5)
        
        if not topic:
            return Response({
                'error': 'topic is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check permission - only teachers and admins
        if request.user.role not in ['TEACHER', 'ADMIN', 'DEPT_HEAD']:
            return Response({
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        result = openai_service.generate_questions(topic, difficulty, count)
        
        return Response(result)

# ============================================================
# 4. AI FEEDBACK GENERATION API
# ============================================================

class AIGenerateFeedbackView(APIView):
    """
    Generate personalized feedback using AI
    POST /api/analytics/ai/generate-feedback/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        answer_id = request.data.get('answer_id')
        
        if not answer_id:
            return Response({
                'error': 'answer_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            answer = Answer.objects.get(id=answer_id)
        except Answer.DoesNotExist:
            return Response({
                'error': 'Answer not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        user = request.user
        if user.role == 'STUDENT':
            if answer.attempt.student.user != user:
                return Response({
                    'error': 'You can only view your own feedback'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Get student info
        student = answer.attempt.student
        exam = answer.attempt.exam
        
        # Generate feedback
        result = openai_service.generate_feedback(
            student_answer=answer.answer_text,
            expected_answer=answer.question.correct_answer or '',
            score=float(answer.marks_obtained or 0)
        )
        
        return Response({
            'success': True,
            'feedback': result,
            'student_name': student.user.full_name,
            'exam_title': exam.title,
            'question_text': answer.question.text
        })

# ============================================================
# 5. AI PROCTORING ANALYSIS API
# ============================================================

class AIProctoringAnalysisView(APIView):
    """
    Analyze proctoring images for suspicious activity
    POST /api/analytics/ai/proctoring-analysis/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        attempt_id = request.data.get('attempt_id')
        
        if not attempt_id:
            return Response({
                'error': 'attempt_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            attempt = ExamAttempt.objects.get(id=attempt_id)
        except ExamAttempt.DoesNotExist:
            return Response({
                'error': 'Attempt not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Check permission
        user = request.user
        if user.role == 'STUDENT':
            if attempt.student.user != user:
                return Response({
                    'error': 'You can only view your own proctoring data'
                }, status=status.HTTP_403_FORBIDDEN)
        
        # Get proctoring images
        from proctoring.models import ProctorImage
        images = ProctorImage.objects.filter(attempt=attempt).order_by('-capture_time')
        
        # Prepare image data for analysis
        image_data = []
        for img in images[:50]:  # Limit to last 50 images
            image_data.append({
                'id': img.id,
                'timestamp': img.capture_time.isoformat(),
                'face_detected': img.face_detected,
                'multiple_faces': img.multiple_faces,
                'mobile_detected': img.mobile_detected,
                'is_suspicious': img.is_suspicious
            })
        
        # Analyze using AI proctor service
        result = ai_proctor.analyze_proctoring_data(attempt.id, image_data)
        
        return Response({
            'success': True,
            'attempt_id': attempt.id,
            'student_name': attempt.student.user.full_name,
            'exam_title': attempt.exam.title,
            'result': result,
            'images_analyzed': len(image_data)
        })

# ============================================================
# 6. BATCH AI GRADING API
# ============================================================

class AIBatchGradingView(APIView):
    """
    Grade multiple essays in batch using AI
    POST /api/analytics/ai/batch-grade/
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        answer_ids = request.data.get('answer_ids', [])
        
        if not answer_ids:
            return Response({
                'error': 'answer_ids is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check permission
        user = request.user
        if user.role not in ['TEACHER', 'ADMIN', 'DEPT_HEAD']:
            return Response({
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Get answers
        answers = Answer.objects.filter(id__in=answer_ids)
        
        if not answers.exists():
            return Response({
                'error': 'No answers found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Prepare for batch grading
        essays = []
        for answer in answers:
            essays.append({
                'student_answer': answer.answer_text,
                'model_answer': answer.question.correct_answer or '',
                'max_marks': int(answer.question.marks)
            })
        
        # Grade in batch
        results = openai_service.grade_essay_batch(essays)
        
        # Save results
        graded_count = 0
        for i, result in enumerate(results):
            if result.get('success'):
                answer = answers[i]
                answer.marks_obtained = result.get('score', 0)
                answer.graded_by = user
                answer.graded_at = timezone.now()
                answer.feedback = result.get('feedback', '')
                answer.save()
                graded_count += 1
        
        return Response({
            'success': True,
            'graded_count': graded_count,
            'total': len(answers),
            'results': results
        })

# ============================================================
# 7. AI RECOMMENDATIONS API
# ============================================================

class AIRecommendationsView(APIView):
    """
    Get personalized course recommendations using AI
    GET /api/analytics/ai/recommendations/
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        
        if user.role != 'STUDENT':
            return Response({
                'recommendations': [],
                'message': 'Recommendations only for students'
            })
        
        try:
            student = StudentProfile.objects.get(user=user)
        except StudentProfile.DoesNotExist:
            return Response({
                'recommendations': [],
                'message': 'Student profile not found'
            })
        
        # Use existing recommendation system
        from analytics.recommendations import CourseRecommender
        recommender = CourseRecommender()
        
        # Load data
        from courses.models import Course, Enrollment
        courses = Course.objects.filter(is_active=True, is_approved=True)
        enrollments = Enrollment.objects.filter(status='ACTIVE')
        
        recommender.load_data(courses, enrollments)
        
        # Get recommendations
        recommendations = recommender.get_recommendations(student.user.id, top_n=5)
        
        # Add AI-enhanced explanations
        if recommendations.get('hybrid'):
            for rec in recommendations['hybrid']:
                try:
                    course = Course.objects.get(id=rec['course_id'])
                    # Enhance with AI (optional)
                    rec['course_title'] = course.title
                    rec['course_code'] = course.course_code
                    rec['description'] = course.description
                    
                    # Generate AI explanation (optional)
                    if rec['score'] > 0.5:
                        rec['reason'] = 'Based on your interests and similar students'
                    else:
                        rec['reason'] = 'Popular course that might interest you'
                except:
                    pass
        
        return Response({
            'success': True,
            'recommendations': recommendations,
            'student_name': student.user.full_name,
            'student_id': student.student_id
        })