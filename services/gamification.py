# backend/services/gamification.py
# COMPLETE GAMIFICATION SYSTEM

from accounts.models import StudentProfile
from courses.models import Enrollment
from exams.models import ExamAttempt
from django.db.models import Sum, Avg, Count
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict
import json
import logging

logger = logging.getLogger(__name__)

class GamificationEngine:
    """Gamification system with points, badges, and leaderboards"""
    
    def __init__(self):
        # Point system
        self.point_system = {
            'course_enrollment': 50,
            'course_completion': 200,
            'exam_passed': 100,
            'exam_excellent': 150,
            'assignment_submitted': 30,
            'assignment_excellent': 80,
            'login_streak': 20,
            'perfection': 500,  # 100% on exam
            'live_class_attended': 40,
            'forum_post': 10,
            'forum_answer': 25,
            'peer_help': 20,
            'weekly_goal': 100,
        }
        
        # Badge thresholds
        self.badge_system = {
            'beginner': {'points': 100, 'icon': '🌱', 'title': 'Beginner Learner'},
            'active': {'points': 500, 'icon': '📚', 'title': 'Active Learner'},
            'dedicated': {'points': 1000, 'icon': '🎯', 'title': 'Dedicated Learner'},
            'excellent': {'points': 2000, 'icon': '⭐', 'title': 'Excellent Learner'},
            'scholar': {'points': 5000, 'icon': '🎓', 'title': 'Academic Scholar'},
            'master': {'points': 10000, 'icon': '🏆', 'title': 'Learning Master'},
        }
    
    def get_student_profile(self, student):
        """Get gamification profile for student"""
        total_points = self._calculate_total_points(student)
        badges = self._get_earned_badges(total_points)
        rank = self._get_rank(student, total_points)
        streak = self._get_login_streak(student)
        recent_achievements = self._get_recent_achievements(student)
        
        return {
            'student_id': student.id,
            'name': student.user.full_name,
            'total_points': total_points,
            'rank': rank,
            'level': self._get_level(total_points),
            'badges': badges,
            'login_streak': streak,
            'achievements': recent_achievements,
            'next_level_points': self._get_next_level_points(total_points),
            'progress_to_next_level': self._get_progress_percentage(total_points)
        }
    
    def _calculate_total_points(self, student):
        """Calculate total points for a student"""
        points = 0
        
        # Course enrollments
        enrollments = Enrollment.objects.filter(student=student, status='ACTIVE')
        points += enrollments.count() * self.point_system['course_enrollment']
        
        # Completed courses
        completed = Enrollment.objects.filter(student=student, status='COMPLETED')
        points += completed.count() * self.point_system['course_completion']
        
        # Exam performance
        attempts = ExamAttempt.objects.filter(student=student, status__in=['SUBMITTED', 'GRADED'])
        passed_attempts = attempts.filter(passed=True)
        points += passed_attempts.count() * self.point_system['exam_passed']
        
        # Excellent performance (80%+)
        excellent = attempts.filter(percentage__gte=80)
        points += excellent.count() * self.point_system['exam_excellent']
        
        # Perfect scores
        perfect = attempts.filter(percentage=100)
        points += perfect.count() * self.point_system['perfection']
        
        return points
    
    def _get_earned_badges(self, total_points):
        """Get badges earned based on points"""
        earned = []
        
        for badge_id, config in self.badge_system.items():
            if total_points >= config['points']:
                earned.append({
                    'id': badge_id,
                    'title': config['title'],
                    'icon': config['icon'],
                    'points_required': config['points'],
                    'earned': True
                })
        
        return earned
    
    def _get_level(self, total_points):
        """Determine current level"""
        levels = [
            (100, 1, "Novice"),
            (500, 2, "Explorer"),
            (1000, 3, "Achiever"),
            (2500, 4, "Scholar"),
            (5000, 5, "Expert"),
            (10000, 6, "Master"),
        ]
        
        for points, level_num, name in levels:
            if total_points < points:
                return {
                    'level': level_num,
                    'name': name,
                    'total_points': points
                }
        
        return {'level': 6, 'name': 'Master', 'total_points': 10000}
    
    def _get_rank(self, student, total_points):
        """Get student's rank among all students"""
        
        # Get all students with their points
        all_students = StudentProfile.objects.filter(is_enrolled=True)
        student_points = []
        
        for s in all_students:
            points = self._calculate_total_points(s)
            student_points.append({'id': s.id, 'points': points})
        
        # Sort by points
        student_points.sort(key=lambda x: x['points'], reverse=True)
        
        # Find student's rank
        for i, sp in enumerate(student_points):
            if sp['id'] == student.id:
                return {
                    'rank': i + 1,
                    'total_students': len(student_points),
                    'percentile': round((i + 1) / len(student_points) * 100, 1)
                }
        
        return {'rank': len(student_points), 'total_students': len(student_points), 'percentile': 100}
    
    def _get_login_streak(self, student):
        """Calculate login streak"""
        # This would need login history tracking
        # For now, use last_login as a proxy
        last_login = student.user.last_login
        
        if last_login and (timezone.now() - last_login).days <= 1:
            # Basic streak (you would need more data for accurate streak)
            return {
                'current_streak': 1,
                'best_streak': 1,
                'description': "🔥 Keep it going!"
            }
        
        return {
            'current_streak': 0,
            'best_streak': 0,
            'description': "Login today to start a streak!"
        }
    
    def _get_recent_achievements(self, student):
        """Get recent achievements"""
        achievements = []
        
        # Recent exam achievements
        recent_attempts = ExamAttempt.objects.filter(
            student=student,
            start_time__gte=timezone.now() - timedelta(days=30)
        )
        
        for attempt in recent_attempts[:3]:
            if attempt.passed:
                achievements.append({
                    'type': 'exam',
                    'title': f"📝 Passed: {attempt.exam.title}",
                    'date': attempt.start_time.date().isoformat(),
                    'points': self.point_system['exam_passed']
                })
        
        # Recent course completions
        recent_completed = Enrollment.objects.filter(
            student=student,
            status='COMPLETED',
            enrollment_date__gte=timezone.now() - timedelta(days=60)
        )
        
        for enrollment in recent_completed[:3]:
            achievements.append({
                'type': 'course',
                'title': f"🎓 Completed: {enrollment.course.title}",
                'date': enrollment.enrollment_date.isoformat(),
                'points': self.point_system['course_completion']
            })
        
        return achievements
    
    def _get_next_level_points(self, total_points):
        """Get points needed for next level"""
        levels = [100, 500, 1000, 2500, 5000, 10000]
        
        for points in levels:
            if total_points < points:
                return points
        
        return 10000
    
    def _get_progress_percentage(self, total_points):
        """Get progress percentage to next level"""
        current_level_points = 0
        next_level_points = self._get_next_level_points(total_points)
        
        levels = [100, 500, 1000, 2500, 5000]
        
        for points in levels:
            if total_points >= points:
                current_level_points = points
        
        if next_level_points == current_level_points:
            return 100
        
        progress = ((total_points - current_level_points) / (next_level_points - current_level_points)) * 100
        return round(min(progress, 100), 1)
    
    def get_leaderboard(self, department=None, semester=None, limit=20):
        """Get leaderboard"""
        
        students = StudentProfile.objects.filter(is_enrolled=True)
        
        if department:
            students = students.filter(department=department)
        
        if semester:
            students = students.filter(current_semester=semester)
        
        leaderboard = []
        for student in students:
            total_points = self._calculate_total_points(student)
            
            if student.student_id:
                leaderboard.append({
                    'rank': 0,  # Will be set after sorting
                    'student_id': student.id,
                    'name': student.user.full_name,
                    'student_number': student.student_id,
                    'department': student.department,
                    'semester': student.current_semester,
                    'points': total_points,
                    'level': self._get_level(total_points)['name'],
                    'cgpa': float(student.cgpa or 0)
                })
        
        # Sort by points
        leaderboard.sort(key=lambda x: x['points'], reverse=True)
        
        # Assign ranks
        for i, entry in enumerate(leaderboard[:limit]):
            entry['rank'] = i + 1
        
        return leaderboard[:limit]

# Singleton
gamification_engine = GamificationEngine()