# courses/urls.py - COMPLETE FIXED VERSION

from django.urls import path
from . import views

urlpatterns = [
    # Course CRUD
    path('', views.CourseListView.as_view(), name='courses'),
    path('<int:pk>/', views.CourseDetailView.as_view(), name='course-detail'),
    
    # Course Materials
    path('<int:course_id>/materials/', views.CourseMaterialView.as_view(), name='course-materials'),
    path('materials/<int:pk>/', views.CourseMaterialDetailView.as_view(), name='material-detail'),
    # courses/urls.py - Add these
    path('student/assignments/results/', views.StudentAssignmentResultsView.as_view(), name='student-assignment-results'),
    # Enrollments
    path('enrollments/', views.EnrollmentView.as_view(), name='enrollments'),
    
    # Course Approval
    path('<int:course_id>/approve/', views.CourseApprovalView.as_view(), name='course-approval'),
    # ✅ COURSE GRADE ENDPOINTS
    path('course/<int:course_id>/grade/', views.CourseGradeView.as_view(), name='course-grade'),
    path('my-grades/', views.StudentAllCourseGradesView.as_view(), name='my-grades'),
    
    # ✅ TEACHER COURSE GRADES
    path('teacher/course/<int:course_id>/grades/', views.TeacherCourseGradesView.as_view(), name='teacher-course-grades'),
    # Department Head
    path('dept/students/', views.DeptStudentListView.as_view(), name='dept-students'),
    path('dept/courses/', views.DeptCourseListView.as_view(), name='dept-courses'),
    
    # Live Class
    path('<int:course_id>/start-live/', views.StartLiveClassView.as_view(), name='start-live'),
    
    # Assignments
    path('<int:course_id>/assignments/', views.AssignmentListView.as_view(), name='course-assignments'),
    path('assignments/<int:pk>/', views.AssignmentDetailView.as_view(), name='assignment-detail'),
    path('assignments/<int:assignment_id>/submissions/', views.AssignmentSubmissionView.as_view(), name='assignment-submissions'),
    path('submissions/<int:submission_id>/grade/', views.GradeAssignmentView.as_view(), name='grade-submission'),
    
    # ✅ STUDENT VIEWS - ADD THESE
    path('student/<int:course_id>/materials/', views.StudentCourseMaterialsView.as_view(), name='student-course-materials'),
    path('student/<int:course_id>/assignments/', views.StudentCourseAssignmentsView.as_view(), name='student-course-assignments'),
    path('student/assignments/<int:assignment_id>/submit/', views.StudentAssignmentSubmissionView.as_view(), name='student-submit-assignment'),
]