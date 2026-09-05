# backend/services/prediction_service.py
# COMPLETE STUDENT PERFORMANCE PREDICTION

import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestRegressor
from accounts.models import StudentProfile
from courses.models import Enrollment
from exams.models import ExamAttempt
from django.db.models import Avg
import logging

logger = logging.getLogger(__name__)

class PerformancePredictionEngine:
    """Predict student performance and success probability"""
    
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.is_trained = False
    
    def train_model(self):
        """Train model on historical student data"""
        
        # Get all students with complete data
        students = StudentProfile.objects.filter(
            is_enrolled=True,
            total_credits__gt=0
        )
        
        if students.count() < 20:
            logger.warning("Not enough data to train model (need at least 20 students)")
            return False
        
        # Prepare training data
        X = []
        y = []
        
        for student in students:
            # Features
            cgpa = float(student.cgpa or 0)
            completed_courses = Enrollment.objects.filter(
                student=student, status='COMPLETED'
            ).count()
            
            attempts = ExamAttempt.objects.filter(student=student)
            avg_score = float(attempts.aggregate(avg=Avg('percentage'))['avg'] or 0)
            attempt_count = attempts.count()
            pass_rate = attempts.filter(passed=True).count() / max(attempt_count, 1)
            
            # Target: next CGPA prediction
            next_cgpa = cgpa
            
            X.append([cgpa, completed_courses, avg_score, attempt_count, pass_rate])
            y.append(next_cgpa)
        
        # Convert to numpy arrays
        X = np.array(X)
        y = np.array(y)
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train model
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.model.fit(X_scaled, y)
        
        self.is_trained = True
        logger.info("✅ Performance prediction model trained")
        return True
    
    def predict_student_success(self, student):
        """Predict success probability for a student"""
        
        # Features
        cgpa = float(student.cgpa or 0)
        completed_courses = Enrollment.objects.filter(
            student=student, status='COMPLETED'
        ).count()
        
        attempts = ExamAttempt.objects.filter(student=student)
        avg_score = float(attempts.aggregate(avg=Avg('percentage'))['avg'] or 0)
        attempt_count = attempts.count()
        pass_rate = attempts.filter(passed=True).count() / max(attempt_count, 1)
        
        features = np.array([[cgpa, completed_courses, avg_score, attempt_count, pass_rate]])
        
        # If model is trained, use it
        if self.is_trained:
            try:
                X_scaled = self.scaler.transform(features)
                predicted_cgpa = self.model.predict(X_scaled)[0]
                
                # Calculate success probability
                success_probability = min(max(
                    (predicted_cgpa - 1.0) / 3.0,  # Map from 1.0 to 4.0 to 0-1
                    0
                ), 1)
                
                return {
                    'predicted_cgpa': round(float(predicted_cgpa), 2),
                    'success_probability': round(success_probability * 100, 1),
                    'risk_level': self._get_risk_level(success_probability),
                    'recommendations': self._get_recommendations(predicted_cgpa)
                }
            except Exception as e:
                logger.error(f"Prediction failed: {e}")
        
        # Fallback: heuristic prediction
        success_probability = min(
            (cgpa / 4.0) * 0.6 + (pass_rate * 0.2) + (avg_score / 100 * 0.2),
            1.0
        )
        
        return {
            'predicted_cgpa': round(cgpa, 2),
            'success_probability': round(success_probability * 100, 1),
            'risk_level': self._get_risk_level(success_probability),
            'recommendations': self._get_recommendations(cgpa)
        }
    
    def _get_risk_level(self, probability):
        """Get risk level based on success probability"""
        if probability > 0.8:
            return 'LOW'
        elif probability > 0.6:
            return 'MEDIUM'
        elif probability > 0.4:
            return 'HIGH'
        else:
            return 'CRITICAL'
    
    def _get_recommendations(self, predicted_cgpa):
        """Generate recommendations based on prediction"""
        recommendations = []
        
        if predicted_cgpa < 2.0:
            recommendations.append("📚 Urgent: Consider retaking failed courses")
            recommendations.append("🎯 Focus on improving core course grades")
        elif predicted_cgpa < 2.5:
            recommendations.append("📖 Increase study hours for challenging courses")
            recommendations.append("💬 Seek help from instructors")
        elif predicted_cgpa < 3.0:
            recommendations.append("📈 Good progress! Consider taking advanced courses")
        else:
            recommendations.append("🏆 Excellent performance! Consider research opportunities")
            recommendations.append("🚀 You're on track for honors")
        
        return recommendations
    
    def predict_exam_performance(self, student, exam):
        """Predict exam performance for a specific exam"""
        
        # Get student's history
        attempts = ExamAttempt.objects.filter(student=student)
        avg_score = float(attempts.aggregate(avg=Avg('percentage'))['avg'] or 0)
        
        # Get exam difficulty based on past attempts
        past_exam_attempts = ExamAttempt.objects.filter(
            student=student,
            exam__course__department__name=student.department
        )
        
        if past_exam_attempts.exists():
            avg_related_score = float(
                past_exam_attempts.aggregate(avg=Avg('percentage'))['avg'] or 0
            )
        else:
            avg_related_score = avg_score
        
        # Prediction
        predicted_percentage = min(
            avg_related_score + (student.cgpa - 2.5) * 10,
            95  # Cap at 95%
        )
        
        return {
            'predicted_percentage': round(max(predicted_percentage, 5), 1),
            'confidence': round(min(
                (len(attempts) / 5) * 0.5 + 0.5,
                0.95
            ), 2),
            'expected_grade': self._get_grade_from_percentage(predicted_percentage)
        }
    
    def _get_grade_from_percentage(self, percentage):
        """Get grade from percentage"""
        if percentage >= 90:
            return 'A+'
        elif percentage >= 80:
            return 'A'
        elif percentage >= 70:
            return 'B'
        elif percentage >= 60:
            return 'C'
        elif percentage >= 50:
            return 'D'
        else:
            return 'F'
    
    def get_department_analytics(self, department_name):
        """Get analytics for a department"""
        
        students = StudentProfile.objects.filter(
            department=department_name,
            is_enrolled=True
        )
        
        if students.count() == 0:
            return {'error': 'No students found'}
        
        cgpa_list = [float(s.cgpa or 0) for s in students]
        
        # Calculate stats
        avg_cgpa = sum(cgpa_list) / len(cgpa_list)
        success_rate = sum(1 for c in cgpa_list if c >= 2.0) / len(cgpa_list)
        
        # Distribution
        distribution = {
            'excellent': sum(1 for c in cgpa_list if c >= 3.5),
            'good': sum(1 for c in cgpa_list if 3.0 <= c < 3.5),
            'average': sum(1 for c in cgpa_list if 2.0 <= c < 3.0),
            'at_risk': sum(1 for c in cgpa_list if c < 2.0)
        }
        
        return {
            'total_students': students.count(),
            'average_cgpa': round(avg_cgpa, 2),
            'success_rate': round(success_rate * 100, 1),
            'distribution': distribution,
            'at_risk_students': self._get_at_risk_students(department_name)
        }
    
    def _get_at_risk_students(self, department_name):
        """Get students at risk of dropping out"""
        students = StudentProfile.objects.filter(
            department=department_name,
            is_enrolled=True,
            cgpa__lt=2.0
        ).select_related('user')[:10]
        
        return [
            {
                'id': s.id,
                'name': s.user.full_name,
                'email': s.user.email,
                'cgpa': float(s.cgpa or 0)
            }
            for s in students
        ]

# Singleton
prediction_engine = PerformancePredictionEngine()