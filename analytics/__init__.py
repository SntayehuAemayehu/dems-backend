# backend/analytics/__init__.py
# Analytics Package Initialization
# ✅ Safe imports — never fail on missing optional dependencies

try:
    from .plagiarism import PlagiarismDetector, SmartGrader, PlagiarismResult, GradingResult
    PLAGIARISM_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ plagiarism module not available: {e}")
    PlagiarismDetector = None
    SmartGrader = None
    PlagiarismResult = None
    GradingResult = None
    PLAGIARISM_AVAILABLE = False

try:
    from .fraud_detection import FraudDetector, FraudAnalysisResult, FraudAlert
    FRAUD_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ fraud_detection module not available: {e}")
    FraudDetector = None
    FraudAnalysisResult = None
    FraudAlert = None
    FRAUD_AVAILABLE = False

try:
    from .recommendations import CourseRecommender
    RECOMMENDATIONS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ recommendations module not available: {e}")
    CourseRecommender = None
    RECOMMENDATIONS_AVAILABLE = False

__all__ = [
    'PlagiarismDetector',
    'SmartGrader',
    'PlagiarismResult',
    'GradingResult',
    'FraudDetector',
    'FraudAnalysisResult',
    'FraudAlert',
    'CourseRecommender',
]