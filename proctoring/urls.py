# proctoring/urls.py - COMPLETE FIXED
# All existing URLs preserved, added new endpoints

from django.urls import path
from . import views

urlpatterns = [
    # ============================================================
    # EXISTING URLs - PRESERVED
    # ============================================================
    
    # Proctoring image capture
    path('sessions/<int:attempt_id>/images/', views.ProctorImageView.as_view(), name='proctor-images'),
    
    # Image flagging
    path('images/<int:image_id>/flag/', views.FlagSuspiciousView.as_view(), name='flag-image'),
    path('images/<int:image_id>/clear/', views.ClearFlagView.as_view(), name='clear-flag'),
    
    # Logs
    path('sessions/<int:attempt_id>/logs/', views.ProctorLogView.as_view(), name='proctor-logs'),
    
    # Session details
    path('sessions/<int:attempt_id>/', views.ProctorSessionView.as_view(), name='proctor-session'),
    
    # Review endpoints
    path('review/', views.ReviewProctoringView.as_view(), name='review-proctoring'),
    path('review/<int:session_id>/', views.ReviewProctoringDetailView.as_view(), name='review-proctoring-detail'),
    path('review/<int:session_id>/update/', views.ReviewProctoringUpdateView.as_view(), name='review-proctoring-update'),
    
    # Flagged exams list
    path('flagged-exams/', views.FlaggedExamsView.as_view(), name='flagged-exams'),
    
    # ============================================================
    # ✅ NEW URLs - For Frontend Integration
    # ============================================================
    
    # Capture proctoring image (main endpoint for frontend)
    path('sessions/capture/', views.ProctorCaptureView.as_view(), name='proctor-capture'),
    
    # Get session status
    path('sessions/<int:attempt_id>/status/', views.ProctorSessionStatusView.as_view(), name='proctor-status'),
    
    # ✅ AI PROCTORING ENDPOINTS
    path('ai/analyze/', views.AIProctorAnalysisView.as_view(), name='ai-proctor-analyze'),
    path('ai/session/<int:session_id>/summary/', views.AIProctorSessionSummaryView.as_view(), name='ai-proctor-summary'),
    path('ai/auto-flag/<int:session_id>/', views.AIProctorAutoFlagView.as_view(), name='ai-proctor-auto-flag'),
    path('ai/objects/', views.AIObjectDetectionView.as_view(), name='ai-object-detection'),
    path('ai/gaze-analysis/', views.AIGazeAnalysisView.as_view(), name='ai-gaze-analysis'),
]