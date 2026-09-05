# backend/services/adaptive_learning.py
# COMPLETE ADAPTIVE LEARNING SYSTEM

from .ai_learning_assistant import AILearningAssistant
from accounts.models import StudentProfile
from courses.models import Course, Enrollment
from exams.models import Exam, ExamAttempt
import logging

logger = logging.getLogger(__name__)

class AdaptiveLearningEngine:
    """Adaptive learning system that personalizes student journey"""
    
    def __init__(self):
        self.assistant = AILearningAssistant()
    
    def create_learning_path(self, student, target_goal='graduation'):
        """
        Create personalized learning path based on student's current progress
        """
        # Get student's current state
        current_state = self._get_student_state(student)
        
        # Generate personalized path
        path = {
            'student': student.user.full_name,
            'current_semester': student.current_semester,
            'current_cgpa': float(student.cgpa or 0),
            'recommended_courses': self._recommend_courses(student, current_state),
            'study_plan': self._create_study_plan(student),
            'skill_gaps': self._identify_skill_gaps(student),
            'accelerated_paths': self._get_acceleration_options(student),
            'support_recommendations': self._get_support_recommendations(student),
            'milestones': self._create_milestones(student)
        }
        
        return path
    
    def _get_student_state(self, student):
        """Get comprehensive student state"""
        return {
            'completed_courses': Enrollment.objects.filter(
                student=student, status='COMPLETED'
            ).count(),
            'active_courses': Enrollment.objects.filter(
                student=student, status='ACTIVE'
            ).count(),
            'total_credits': student.total_credits,
            'cgpa': float(student.cgpa or 0),
            'current_semester': student.current_semester,
            'learning_patterns': self.assistant._analyze_learning_patterns(student)
        }
    
    def _recommend_courses(self, student, state):
        """Recommend courses based on skill gaps"""
        
        # Get all courses for department
        all_courses = Course.objects.filter(
            department__name=student.department,
            is_active=True,
            is_approved=True
        )
        
        # Get completed courses
        completed = Enrollment.objects.filter(
            student=student,
            status='COMPLETED'
        ).values_list('course__id', flat=True)
        
        # Get active courses
        active = Enrollment.objects.filter(
            student=student,
            status='ACTIVE'
        ).values_list('course__id', flat=True)
        
        # Filter out completed and active
        available = all_courses.exclude(id__in=list(completed) + list(active))
        
        # Calculate priority based on CGPA and semester
        recommendations = []
        
        for course in available:
            course_score = 0.5
            
            # Courses at current semester level
            if course.semester == str(student.current_semester):
                course_score += 0.3
            
            # Courses in areas of weakness
            if float(student.cgpa or 0) < 2.5:
                # Recommend easier courses
                if course.credit_hours <= 3:
                    course_score += 0.2
            else:
                # Recommend advanced courses
                if course.credit_hours >= 3:
                    course_score += 0.1
            
            recommendations.append({
                'course': course.course_code,
                'title': course.title,
                'credit_hours': course.credit_hours,
                'priority_score': round(course_score * 100, 2),
                'recommendation': self._get_recommendation_text(course_score)
            })
        
        # Sort by priority
        recommendations.sort(key=lambda x: x['priority_score'], reverse=True)
        
        return recommendations[:5]
    
    def _get_recommendation_text(self, score):
        """Get recommendation text based on score"""
        if score > 0.8:
            return "🌟 Highly recommended - aligns with your academic goals"
        elif score > 0.6:
            return "✅ Recommended - would benefit your learning path"
        elif score > 0.4:
            return "📚 Good option - consider taking this course"
        else:
            return "ℹ️ Optional - only if you have spare capacity"
    
    def _create_study_plan(self, student):
        """Create weekly study plan"""
        
        # Get active courses
        active_courses = Enrollment.objects.filter(
            student=student, status='ACTIVE'
        ).select_related('course')
        
        plan = []
        
        for i, enrollment in enumerate(active_courses):
            course = enrollment.course
            plan.append({
                'day': f"Day {i + 1}",
                'course': course.title,
                'code': course.course_code,
                'focus': self._get_course_focus(enrollment),
                'estimated_time': f"{course.credit_hours * 2} hours"
            })
        
        return plan
    
    def _get_course_focus(self, enrollment):
        """Determine what to focus on for a course"""
        if enrollment.status == 'COMPLETED':
            return "Review material"
        else:
            return "Study & complete assignments"
    
    def _identify_skill_gaps(self, student):
        """Identify skill gaps"""
        gaps = []
        
        # Based on CGPA
        cgpa = float(student.cgpa or 0)
        if cgpa < 2.0:
            gaps.append("📉 Foundation skills need improvement")
            gaps.append("📖 Focus on fundamental concepts")
        elif cgpa < 3.0:
            gaps.append("📈 Intermediate skills need strengthening")
        
        # Based on course grades
        try:
            from courses.models import Enrollment
            completed = Enrollment.objects.filter(student=student, status='COMPLETED')
            
            for enrollment in completed:
                if enrollment.grade_letter and enrollment.grade_letter in ['C', 'C-', 'D', 'F']:
                    gaps.append(f"⚠️ Need improvement in: {enrollment.course.title}")
        except:
            pass
        
        return gaps[:5]
    
    def _get_acceleration_options(self, student):
        """Get options for accelerated learning"""
        options = []
        
        # Fast track if high CGPA
        if float(student.cgpa or 0) >= 3.5:
            options.append({
                'type': 'fast_track',
                'title': "🚀 Fast Track Program",
                'description': "Based on your excellent performance, you can complete courses faster."
            })
        
        # Credit transfer
        options.append({
            'type': 'credit_transfer',
            'title': "📄 Credit Transfer",
            'description': "Transfer credits from previous learning or certifications."
        })
        
        return options
    
    def _get_support_recommendations(self, student):
        """Get support recommendations"""
        support = []
        
        # Academic support
        if float(student.cgpa or 0) < 2.5:
            support.append({
                'type': 'academic',
                'title': "📚 Academic Support",
                'description': "Consider scheduling sessions with your academic advisor."
            })
        
        # Career support
        if student.current_semester >= 6:
            support.append({
                'type': 'career',
                'title': "💼 Career Development",
                'description': "Start preparing for internships and career opportunities."
            })
        
        return support
    
    def _create_milestones(self, student):
        """Create learning milestones"""
        milestones = []
        
        current_semester = student.current_semester
        cgpa = float(student.cgpa or 0)
        
        # Academic milestones
        milestones.append({
            'type': 'short_term',
            'title': "✅ Complete Current Semester",
            'description': f"Finish Semester {current_semester} with a CGPA of {min(cgpa + 0.2, 4.0):.2f} or better.",
            'target': "End of semester"
        })
        
        # Long-term milestones
        total_credits_needed = 120  # Standard for 4-year degree
        credits_remaining = max(total_credits_needed - student.total_credits, 0)
        milestones.append({
            'type': 'long_term',
            'title': "🎓 Graduation",
            'description': f"You need {credits_remaining} more credits to graduate.",
            'target': f"Semester {min(current_semester + 4, 8)}"
        })
        
        return milestones

# Singleton instance
adaptive_engine = AdaptiveLearningEngine()