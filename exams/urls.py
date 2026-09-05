# exams/urls.py - COMPLETE

from django.urls import path
from . import views

urlpatterns = [
    # Exam CRUD
    path('', views.ExamListView.as_view(), name='exams'),
    path('<int:pk>/', views.ExamDetailView.as_view(), name='exam-detail'),
    
    # Questions
    path('<int:exam_id>/questions/', views.QuestionView.as_view(), name='questions'),
    path('questions/<int:pk>/', views.QuestionDetailView.as_view(), name='question-detail'),
    
    # Exam taking
    path('<int:exam_id>/start/', views.StartExamView.as_view(), name='start-exam'),
    path('attempt/<int:attempt_id>/submit/', views.SubmitExamView.as_view(), name='submit-exam'),
    
    # Results
    path('results/', views.ExamResultsView.as_view(), name='exam-results'),
    
    # Submissions - Teacher views
    path('submissions/<int:exam_id>/', views.ExamSubmissionsView.as_view(), name='exam-submissions'),
    # exams/urls.py - ADD THIS LINE
    path('verify-face/', views.VerifyFaceView.as_view(), name='verify-face'),
    path('attempt/<int:attempt_id>/heartbeat/', views.ExamHeartbeatView.as_view(), name='exam-heartbeat'),
    # Essay Grading
    path('attempt/<int:attempt_id>/essay-answers/', views.GetEssayAnswersView.as_view(), name='essay-answers'),
    path('grade-essay/', views.GradeEssayAnswerView.as_view(), name='grade-essay'),
    # exams/urls.py - Add these
    path('bonus-marks/', views.BonusMarksView.as_view(), name='bonus-marks'),
    path('edit-answer/', views.EditAnswerView.as_view(), name='edit-answer'),
    # Flagging
    path('<int:attempt_id>/flag/', views.FlagExamView.as_view(), name='flag-exam'),
    path('<int:attempt_id>/unflag/', views.UnflagExamView.as_view(), name='unflag-exam'),
    path('flagged-summary/', views.FlaggedExamsSummaryView.as_view(), name='flagged-summary'),
     # ✅ ADD THESE - Bonus and Edit Answer
    path('bonus-marks/', views.BonusMarksView.as_view(), name='bonus-marks'),
    path('edit-answer/', views.EditAnswerView.as_view(), name='edit-answer'),
    path('attempt/<int:attempt_id>/face-verify/', views.FaceVerificationView.as_view(), name='face-verify'),
    path('attempt/<int:attempt_id>/gaze-analysis/', views.GazeAnalysisView.as_view(), name='gaze-analysis'),
    path('attempt/<int:attempt_id>/object-detection/', views.ObjectDetectionView.as_view(), name='object-detection'),




]