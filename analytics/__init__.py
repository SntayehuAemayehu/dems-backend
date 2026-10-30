# backend/analytics/__init__.py
# Analytics Package Initialization

from .plagiarism import PlagiarismDetector, SmartGrader, PlagiarismResult, GradingResult
from .fraud_detection import FraudDetector, FraudAnalysisResult, FraudAlert
from .recommendations import CourseRecommender

__all__ = [
    'PlagiarismDetector',
    'SmartGrader',
    'PlagiarismResult',
    'GradingResult',
    'FraudDetector',
    'FraudAnalysisResult',
    'FraudAlert',
    'CourseRecommender'
]