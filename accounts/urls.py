# accounts/urls.py - COMPLETE FIXED

from django.urls import path
from . import views

urlpatterns = [
    # Auth endpoints
    path('register/', views.RegisterView.as_view(), name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('profile/', views.UserProfileView.as_view(), name='profile'),
    path('profile/student/', views.StudentProfileView.as_view(), name='student-profile'),
    path('profile/teacher/', views.TeacherProfileView.as_view(), name='teacher-profile'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    # Department endpoints
    path('departments/', views.DepartmentListView.as_view(), name='departments-list'),
    path('departments/create/', views.DepartmentCreateView.as_view(), name='departments-create'),
    path('departments/<int:pk>/', views.DepartmentDetailView.as_view(), name='departments-detail'),
    
    # Password Reset
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', views.ResetPasswordView.as_view(), name='reset-password'),
    path('validate-reset-token/', views.ValidateResetTokenView.as_view(), name='validate-reset-token'),
    # Password Reset with OTP
    path('send-reset-otp/', views.SendResetOTPView.as_view(), name='send-reset-otp'),
    path('verify-otp/', views.VerifyOTPView.as_view(), name='verify-otp'),
    path('reset-password-token/', views.ResetPasswordWithTokenView.as_view(), name='reset-password-token'),
    path('validate-reset-token/', views.ValidateResetTokenView.as_view(), name='validate-reset-token'),
    # Registrar endpoints
    path('registrar/students/', views.RegistrarStudentListView.as_view(), name='registrar-students'),
    path('registrar/students/<int:student_id>/verify/', views.RegistrarStudentVerifyView.as_view(), name='registrar-verify'),
    path('registrar/students/<int:student_id>/activate/', views.RegistrarStudentActivateView.as_view(), name='registrar-activate'),
    path('registrar/students/<int:student_id>/generate-id/', views.RegistrarGenerateIDView.as_view(), name='registrar-generate-id'),
    path('registrar/students/<int:student_id>/notify-document/', views.RegistrarNotifyStudentView.as_view(), name='registrar-notify'),
    path('registrar/students/<int:student_id>/documents/', views.RegistrarStudentDocumentsView.as_view(), name='registrar-student-documents'),
    path('registrar/documents/<str:document_type>/<int:student_id>/download/', views.RegistrarDownloadDocumentView.as_view(), name='registrar-download-document'),
    
    # Registrar Configuration
    path('registrar/config/', views.RegistrationConfigView.as_view(), name='registrar-config'),
    
    # Department Head endpoints
    path('dept-head/students/', views.DeptHeadStudentListView.as_view(), name='dept-head-students'),
    # accounts/urls.py - COMPLETE FIXED
    path('dept-head/dashboard/', views.DeptHeadDashboardView.as_view(), name='dept-head-dashboard'),
    path('dept-head/teachers/', views.DeptHeadTeacherListView.as_view(), name='dept-head-teachers'), 
    path('dept-head/courses/', views.DeptHeadCourseListView.as_view(), name='dept-head-courses'),

    path('dept-head/teachers/manage/', views.DeptHeadTeacherManagementView.as_view(), name='dept-head-teacher-manage'),
    path('dept-head/students/<int:student_id>/results/', views.DeptHeadStudentResultsView.as_view(), name='dept-head-student-results'),
    path('dept-head/send-results/', views.DeptHeadSendResultsToRegistrarView.as_view(), name='dept-head-send-results'),
    path('dept-head/sent-results/', views.DeptHeadGetSentResultsView.as_view(), name='dept-head-sent-results'),
    # Registrar can view sent results (READ ONLY)
    path('registrar/sent-results/', views.DeptHeadGetSentResultsView.as_view(), name='registrar-sent-results'),
    path('dept-head/courses/<int:course_id>/approve/', views.DeptHeadCourseApproveView.as_view(), name='dept-head-course-approve'),
    path('dept-head/final-exams/', views.DeptHeadFinalExamListView.as_view(), name='dept-head-final-exams'),
    path('dept-head/final-exams/<int:exam_id>/', views.DeptHeadFinalExamDetailView.as_view(), name='dept-head-final-exam-detail'),
    path('dept-head/final-exams/<int:exam_id>/update/', views.DeptHeadFinalExamUpdateView.as_view(), name='dept-head-final-exam-update'),
    path('dept-head/final-exams/<int:exam_id>/delete/', views.DeptHeadFinalExamDeleteView.as_view(), name='dept-head-final-exam-delete'),
    path('dept-head/students/<int:student_id>/activate/', views.DeptHeadStudentListView.as_view(), name='dept-head-student-activate'),
    path('dept-head/dashboard/', views.DeptHeadDashboardView.as_view(), name='dept-head-dashboard'),
   
    # Student Document Upload
    path('documents/upload/', views.StudentDocumentUploadView.as_view(), name='document-upload'),
     # ✅ User List for Chat
    path('users/', views.UserListView.as_view(), name='users-list'),
    # Admin Create User
     # Admin-specific login
    path('admin-login/', views.AdminLoginView.as_view(), name='admin-login'),
    path('admin/create-user/', views.AdminCreateUserView.as_view(), name='admin-create-user'),
    
    # Student Grades
    path('grades/', views.StudentGradesView.as_view(), name='student-grades'),
]