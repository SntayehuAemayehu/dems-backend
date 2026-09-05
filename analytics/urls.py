# backend/analytics/urls.py - COMPLETE WITH AI ROUTES

from django.urls import path
from . import views
from .views import (
    # ... existing imports ...
    PaymentScheduleLockView,
    PaymentScheduleUnlockView,
    PaymentScheduleUpdateStatusView,
)
from . import ai_views  # ✅ Import ai_views

urlpatterns = [
    # Analytics endpoints
    path('dashboard/', views.DashboardAnalyticsView.as_view(), name='dashboard-analytics'),
    path('enrollments/', views.EnrollmentAnalyticsView.as_view(), name='enrollment-analytics'),
    path('exams/', views.ExamAnalyticsView.as_view(), name='exam-analytics'),
    path('payments/', views.PaymentAnalyticsView.as_view(), name='payment-analytics'),
    path('export/<str:report_type>/', views.ExportReportView.as_view(), name='export-report'),
    
    # Admin endpoints
    path('admin/config/', views.AdminConfigView.as_view(), name='admin-config'),
    path('admin/config/update/', views.AdminConfigView.as_view(), name='admin-config-update'),
    path('admin/users/', views.AdminUsersView.as_view(), name='admin-users'),
    path('admin/users/<int:user_id>/', views.AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/users/<int:user_id>/toggle/', views.AdminUserToggleView.as_view(), name='admin-user-toggle'),
    path('admin/stats/', views.AdminStatsView.as_view(), name='admin-stats'),
    path('admin/logs/', views.AdminLogsView.as_view(), name='admin-logs'),
    path('admin/logs/clear/', views.ClearSystemLogsView.as_view(), name='clear-logs'),
    path('admin/courses/', views.AdminCourseManagementView.as_view(), name='admin-courses'),
    path('admin/courses/<int:course_id>/', views.AdminCourseDetailView.as_view(), name='admin-course-detail'),
    path('admin/payments/', views.AdminPaymentManagementView.as_view(), name='admin-payments'),
    path('admin/backups/', views.AdminBackupHistoryView.as_view(), name='admin-backups'),
    path('admin/backup/', views.AdminBackupCreateView.as_view(), name='admin-backup-create'),
    path('admin/departments/', views.AdminDepartmentListView.as_view(), name='admin-departments'),
    path('admin/departments/create/', views.AdminDepartmentCreateView.as_view(), name='admin-department-create'),
    path('admin/departments/<int:department_id>/', views.AdminDepartmentDetailView.as_view(), name='admin-department-detail'),
    
    # Bank endpoints
    path('banks/', views.BankAccountListView.as_view(), name='banks'),
    path('banks/<int:pk>/', views.BankAccountDetailView.as_view(), name='bank-detail'),
    
    # Fee Structure endpoints
    path('fee-structures/', views.FeeStructureListView.as_view(), name='fee-structures'),
    path('fee-structures/<int:pk>/', views.FeeStructureDetailView.as_view(), name='fee-structure-detail'),
    
    # Payment Period endpoints
    path('payment-periods/', views.PaymentPeriodListView.as_view(), name='payment-periods'),
    path('payment-periods/<int:pk>/', views.PaymentPeriodDetailView.as_view(), name='payment-period-detail'),
    
    # Payment Schedule endpoints
    path('payment-schedules/', views.StudentPaymentScheduleListView.as_view(), name='payment-schedules'),
    path('payment-schedules/<int:pk>/', views.StudentPaymentScheduleDetailView.as_view(), name='payment-schedule-detail'),
    path('generate-payment-schedules/', views.GenerateStudentPaymentSchedulesView.as_view(), name='generate-payment-schedules'),
    # ✅ Payment Schedule Lock/Unlock
    path('payment-schedules/<int:pk>/lock/', PaymentScheduleLockView.as_view(), name='schedule-lock'),
    path('payment-schedules/<int:pk>/unlock/', PaymentScheduleUnlockView.as_view(), name='schedule-unlock'),
    path('payment-schedules/<int:pk>/update-status/', PaymentScheduleUpdateStatusView.as_view(), name='schedule-update-status'),
    # Payment status and access endpoints
    path('payment-status/', views.StudentPaymentStatusView.as_view(), name='payment-status'),
    path('check-access/', views.CheckStudentAccessView.as_view(), name='check-access'),
    
    # Batch Processing URLs
    path('batch/activate-students/', views.BatchStudentActivationView.as_view(), name='batch-activate-students'),
    path('batch/verify-payments/', views.BatchPaymentVerificationView.as_view(), name='batch-verify-payments'),
    path('batch/verify-documents/', views.BatchDocumentVerificationView.as_view(), name='batch-verify-documents'),
    path('batch/generate-ids/', views.BatchStudentIDGenerationView.as_view(), name='batch-generate-ids'),
    path('batch/send-notifications/', views.BatchNotificationView.as_view(), name='batch-send-notifications'),
    
    # System Lock endpoint
    path('system-lock/', views.SystemLockView.as_view(), name='system-lock'),
    # ✅ PUBLIC HOMEPAGE STATS
    path('public/homepage-stats/', views.PublicHomepageStatsView.as_view(), name='public-homepage-stats'),
    # ============================================================
    # ✅ AI ENDPOINTS - UNCOMMENTED
    # ============================================================
    path('ai/grade-essay/', ai_views.AIGradeEssayView.as_view(), name='ai-grade-essay'),
    path('ai/plagiarism-check/', ai_views.AIPlagiarismCheckView.as_view(), name='ai-plagiarism-check'),
    path('ai/generate-questions/', ai_views.AIGenerateQuestionsView.as_view(), name='ai-generate-questions'),
    path('ai/generate-feedback/', ai_views.AIGenerateFeedbackView.as_view(), name='ai-generate-feedback'),
    path('ai/proctoring-analysis/', ai_views.AIProctoringAnalysisView.as_view(), name='ai-proctoring-analysis'),
    path('ai/batch-grade/', ai_views.AIBatchGradingView.as_view(), name='ai-batch-grade'),
    path('ai/reclcommendations/', ai_views.AIRecommendationsView.as_view(), name='ai-recommendations'),
     # ============================================================
    # ✅ NEW AI & ANALYTICS ENDPOINTS
    # ============================================================
    
    # AI Learning Assistant
    path('ai/student-insights/', views.StudentInsightsView.as_view(), name='student-insights'),
    
    # Adaptive Learning
    path('adaptive/learning-path/', views.AdaptiveLearningPathView.as_view(), name='adaptive-learning'),
    
    # Gamification
    path('gamification/profile/', views.GamificationProfileView.as_view(), name='gamification-profile'),
    path('gamification/leaderboard/', views.LeaderboardView.as_view(), name='leaderboard'),
    
    # Real-Time Analytics
    path('realtime/dashboard/', views.RealtimeDashboardView.as_view(), name='realtime-dashboard'),
    
    # Performance Prediction
    path('predict/student-success/', views.PredictStudentSuccessView.as_view(), name='predict-success'),
    path('predict/exam-performance/', views.PredictExamPerformanceView.as_view(), name='predict-exam'),
    
    # Certificates
    path('certificates/generate/', views.GenerateCertificateView.as_view(), name='generate-certificate'),
    path('certificates/verify/', views.VerifyCertificateView.as_view(), name='verify-certificate'),
    
    # Languages
    path('i18n/languages/', views.GetLanguagesView.as_view(), name='get-languages'),
    path('i18n/translations/', views.GetTranslationsView.as_view(), name='get-translations'),
    # analytics/urls.py - ADD THESE URLS 
    # ✅ BATCH OPERATIONS
    path('batch/delete/', views.BatchDeleteView.as_view(), name='batch-delete'),
    path('batch/export/', views.BatchExportView.as_view(), name='batch-export'),
    path('batch/delete/banks/', views.BatchDeleteView.as_view(), name='batch-delete-banks'),
    path('batch/delete/fee-structures/', views.BatchDeleteView.as_view(), name='batch-delete-fee-structures'),
    path('batch/delete/payment-periods/', views.BatchDeleteView.as_view(), name='batch-delete-payment-periods'),
    path('batch/delete/departments/', views.BatchDeleteView.as_view(), name='batch-delete-departments'),
    path('batch/delete/payment-schedules/', views.BatchDeleteView.as_view(), name='batch-delete-payment-schedules'),
    path('batch/delete/courses/', views.BatchDeleteView.as_view(), name='batch-delete-courses'),
    path('batch/delete/users/', views.BatchDeleteView.as_view(), name='batch-delete-users'),
    path('batch/delete/payments/', views.BatchDeleteView.as_view(), name='batch-delete-payments'),
]










