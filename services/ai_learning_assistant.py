# backend/services/ai_learning_assistant.py
# COMPLETE FIXED AI LEARNING ASSISTANT WITH PERSONALIZATION

import openai
from django.utils import timezone
from accounts.models import StudentProfile
from courses.models import Enrollment
import logging

logger = logging.getLogger(__name__)

class AILearningAssistant:
    """AI-powered learning assistant that provides personalized guidance"""
    
    def __init__(self):
        self.model = "gpt-4"
    
    def get_student_insights(self, student):
        """Get comprehensive insights about student's learning"""
        
        # Get student data
        enrollments = Enrollment.objects.filter(student=student)
        completed = enrollments.filter(status='COMPLETED')
        active = enrollments.filter(status='ACTIVE')
        
        insights = {
            'student_name': student.user.full_name,
            'total_courses': enrollments.count(),
            'completed_courses': completed.count(),
            'active_courses': active.count(),
            'cgpa': float(student.cgpa or 0),
            'learning_patterns': self._analyze_learning_patterns(student),
            'strengths': self._identify_strengths(student),
            'weaknesses': self._identify_weaknesses(student),
            'recommendations': self._generate_recommendations(student),
            'next_best_actions': self._get_next_actions(student)
        }
        
        return insights
    
    def _analyze_learning_patterns(self, student):
        """Analyze how the student learns best"""
        try:
            from exams.models import ExamAttempt
            
            attempts = ExamAttempt.objects.filter(student=student)
            
            patterns = {
                'best_performance_time': self._find_best_time(attempts),
                'average_completion_time': self._find_avg_completion(attempts),
                'preferred_difficulty': self._find_preferred_difficulty(attempts),
                'consistency_score': self._calculate_consistency(attempts)
            }
            
            return patterns
        except Exception as e:
            logger.error(f"Error analyzing patterns: {e}")
            return {}
    
    def _find_best_time(self, attempts):
        """Find when student performs best"""
        time_scores = {}
        
        for attempt in attempts:
            if attempt.start_time:
                hour = attempt.start_time.hour
                if hour < 12:
                    period = 'Morning'
                elif hour < 17:
                    period = 'Afternoon'
                else:
                    period = 'Evening'
                
                if period not in time_scores:
                    time_scores[period] = {'count': 0, 'scores': []}
                
                time_scores[period]['count'] += 1
                if attempt.percentage:
                    time_scores[period]['scores'].append(float(attempt.percentage))
        
        best_period = None
        best_avg = 0
        
        for period, data in time_scores.items():
            if data['scores']:
                avg = sum(data['scores']) / len(data['scores'])
                if avg > best_avg:
                    best_avg = avg
                    best_period = period
        
        return {
            'best_time': best_period,
            'average_score': round(best_avg, 2) if best_avg else 0
        }
    
    def _find_avg_completion(self, attempts):
        """Find average time to complete exams"""
        completion_times = []
        
        for attempt in attempts:
            if attempt.start_time and attempt.end_time:
                duration = (attempt.end_time - attempt.start_time).total_seconds() / 60
                if attempt.exam.duration_minutes:
                    completion_times.append(duration / attempt.exam.duration_minutes)
        
        if completion_times:
            avg_ratio = sum(completion_times) / len(completion_times)
            return {
                'average_completion_ratio': round(avg_ratio, 2),
                'description': 'Fast' if avg_ratio < 0.7 else 'Normal' if avg_ratio < 0.9 else 'Slow'
            }
        
        return {'description': 'No data available'}
    
    def _find_preferred_difficulty(self, attempts):
        """Find student's preferred difficulty level"""
        difficulty_scores = {}
        
        for attempt in attempts:
            if attempt.percentage:
                if attempt.percentage >= 80:
                    difficulty = 'Easy'
                elif attempt.percentage >= 60:
                    difficulty = 'Medium'
                else:
                    difficulty = 'Hard'
                
                if difficulty not in difficulty_scores:
                    difficulty_scores[difficulty] = []
                difficulty_scores[difficulty].append(float(attempt.percentage))
        
        preferred = None
        max_avg = 0
        
        for difficulty, scores in difficulty_scores.items():
            avg = sum(scores) / len(scores)
            if avg > max_avg:
                max_avg = avg
                preferred = difficulty
        
        return {
            'preferred_difficulty': preferred,
            'scores': difficulty_scores
        }
    
    def _calculate_consistency(self, attempts):
        """Calculate how consistent the student is"""
        scores = [float(a.percentage) for a in attempts if a.percentage]
        
        if not scores:
            return {'score': 0, 'description': 'No data'}
        
        import statistics
        std_dev = statistics.stdev(scores) if len(scores) > 1 else 0
        avg = sum(scores) / len(scores)
        
        consistency_score = max(0, 100 - (std_dev * 5))
        
        description = 'Very consistent' if consistency_score > 80 else 'Somewhat consistent' if consistency_score > 50 else 'Inconsistent'
        
        return {
            'score': round(consistency_score, 2),
            'description': description,
            'standard_deviation': round(std_dev, 2)
        }
    
    def _identify_strengths(self, student):
        """Identify student's strengths"""
        strengths = []
        
        try:
            from courses.models import Enrollment
            enrollments = Enrollment.objects.filter(student=student, status='COMPLETED')
            
            for enrollment in enrollments:
                if enrollment.grade_letter and enrollment.grade_letter in ['A', 'A+', 'A-', 'B+']:
                    strengths.append({
                        'course': enrollment.course.title,
                        'code': enrollment.course.course_code,
                        'grade': enrollment.grade_letter,
                        'percentage': float(enrollment.percentage_score or 0)
                    })
        except:
            pass
        
        # Sort by grade
        strengths.sort(key=lambda x: x['percentage'], reverse=True)
        
        return strengths[:5]
    
    def _identify_weaknesses(self, student):
        """Identify student's weaknesses"""
        weaknesses = []
        
        try:
            from courses.models import Enrollment
            enrollments = Enrollment.objects.filter(student=student)
            
            for enrollment in enrollments:
                if enrollment.grade_letter and enrollment.grade_letter in ['C', 'C-', 'D', 'F']:
                    weaknesses.append({
                        'course': enrollment.course.title,
                        'code': enrollment.course.course_code,
                        'grade': enrollment.grade_letter,
                        'percentage': float(enrollment.percentage_score or 0)
                    })
        except:
            pass
        
        return weaknesses[:5]
    
    def _generate_recommendations(self, student):
        """Generate personalized recommendations"""
        recommendations = []
        
        # Based on CGPA
        cgpa = float(student.cgpa or 0)
        if cgpa < 2.0:
            recommendations.append("📚 Consider retaking challenging courses to improve your GPA")
            recommendations.append("🎯 Focus on understanding core concepts before moving to advanced topics")
        elif cgpa < 3.0:
            recommendations.append("📈 Good progress! Consider taking on more challenging courses")
        else:
            recommendations.append("🏆 Excellent academic performance! Consider advanced courses or research")
        
        # Based on completion
        try:
            from courses.models import Enrollment
            active = Enrollment.objects.filter(student=student, status='ACTIVE').count()
            if active > 3:
                recommendations.append("⚖️ You have many active courses. Consider focusing on fewer courses at a time")
        except:
            pass
        
        # Based on weaknesses
        weaknesses = self._identify_weaknesses(student)
        if weaknesses:
            recommendations.append(f"⚠️ Focus on improving in: {', '.join(w['code'] for w in weaknesses[:3])}")
        
        return recommendations
    
    def _get_next_actions(self, student):
        """Get recommended next actions for student"""
        actions = []
        
        # Check for upcoming exams
        try:
            from exams.models import Exam
            from courses.models import Enrollment
            
            enrolled_courses = Enrollment.objects.filter(student=student, status='ACTIVE').values_list('course_id', flat=True)
            upcoming_exams = Exam.objects.filter(
                course__in=enrolled_courses,
                is_published=True,
                start_time__gt=timezone.now()
            ).order_by('start_time')[:3]
            
            for exam in upcoming_exams:
                days_until = (exam.start_time - timezone.now()).days
                actions.append({
                    'type': 'exam',
                    'title': f"📝 Prepare for {exam.title}",
                    'details': f"Exam in {days_until} days. {exam.total_marks} marks available.",
                    'priority': 'high' if days_until < 3 else 'medium'
                })
        except:
            pass
        
        # Check for pending assignments
        try:
            from courses.models import Assignment
            enrolled_courses = Enrollment.objects.filter(student=student, status='ACTIVE').values_list('course_id', flat=True)
            pending_assignments = Assignment.objects.filter(
                course__in=enrolled_courses,
                due_date__gt=timezone.now()
            ).order_by('due_date')[:3]
            
            for assignment in pending_assignments:
                days_until = (assignment.due_date - timezone.now()).days
                actions.append({
                    'type': 'assignment',
                    'title': f"📄 Submit: {assignment.title}",
                    'details': f"Due in {days_until} days. Worth {assignment.total_marks} marks.",
                    'priority': 'high' if days_until < 2 else 'medium'
                })
        except:
            pass
        
        # Based on CGPA improvement
        cgpa = float(student.cgpa or 0)
        if cgpa < 3.0:
            actions.append({
                'type': 'improvement',
                'title': "📈 Improve Your GPA",
                'details': "Review past exam results to identify areas for improvement",
                'priority': 'medium'
            })
        
        return actions

# Register as singleton
ai_assistant = AILearningAssistant()