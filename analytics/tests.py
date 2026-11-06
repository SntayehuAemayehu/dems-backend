from unittest.mock import patch

from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import StudentProfile, User
from analytics.models import SystemLog
from analytics.views import AdminLogsView, AdminUserDetailView, AdminUsersView, ClearSystemLogsView
from middleware.activity_log import ActivityLogMiddleware


class AdminUserManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@example.test',
            password='test-password',
            full_name='Admin User',
            role='ADMIN',
        )
        self.factory = APIRequestFactory()

    @patch('analytics.views.send_notification')
    def test_create_student_saves_academic_details_and_audit_log(self, _send_notification):
        request = self.factory.post('/analytics/admin/users/', {
            'email': 'student@example.test',
            'full_name': 'New Student',
            'password': 'test-password',
            'role': 'STUDENT',
            'department': 'Computer Science',
            'year': 3,
            'semester': 2,
        }, format='json')
        force_authenticate(request, user=self.admin)

        response = AdminUsersView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        student = User.objects.get(email='student@example.test')
        profile = StudentProfile.objects.get(user=student)
        self.assertEqual((profile.year, profile.current_semester), (3, 2))
        log = SystemLog.objects.get(action='USER_CREATED')
        self.assertEqual(log.user, self.admin)
        self.assertEqual(log.details['target_role'], 'STUDENT')

    def test_create_teacher_saves_department(self):
        request = self.factory.post('/analytics/admin/users/', {
            'email': 'teacher@example.test',
            'full_name': 'New Teacher',
            'password': 'test-password',
            'role': 'TEACHER',
            'department': 'Mathematics',
        }, format='json')
        force_authenticate(request, user=self.admin)

        response = AdminUsersView.as_view()(request)

        self.assertEqual(response.status_code, 201)
        teacher = User.objects.get(email='teacher@example.test')
        self.assertEqual(teacher.teacher_profile.department, 'Mathematics')

    def test_update_and_delete_users_are_logged(self):
        target = User.objects.create_user(
            email='target@example.test',
            password='test-password',
            full_name='Before Update',
            role='TEACHER',
        )

        request = self.factory.put(
            f'/analytics/admin/users/{target.id}/',
            {'full_name': 'After Update', 'role': 'TEACHER'},
            format='json',
        )
        force_authenticate(request, user=self.admin)
        response = AdminUserDetailView.as_view()(request, user_id=target.id)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(SystemLog.objects.filter(action='USER_UPDATED', user=self.admin).exists())

        request = self.factory.delete(f'/analytics/admin/users/{target.id}/')
        force_authenticate(request, user=self.admin)
        response = AdminUserDetailView.as_view()(request, user_id=target.id)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(SystemLog.objects.filter(action='USER_DELETED', user=self.admin).exists())

    def test_logs_can_be_filtered_by_actor_role(self):
        teacher = User.objects.create_user(
            email='teacher@example.test',
            password='test-password',
            full_name='Teacher User',
            role='TEACHER',
        )
        SystemLog.objects.create(user=self.admin, action='ADMIN_ACTION')
        SystemLog.objects.create(user=teacher, action='TEACHER_ACTION')
        SystemLog.objects.create(action='SYSTEM_ACTION')

        request = self.factory.get('/analytics/admin/logs/', {'limit': 50, 'role': 'TEACHER'})
        force_authenticate(request, user=self.admin)
        response = AdminLogsView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual([log['action'] for log in response.data], ['TEACHER_ACTION'])

    def test_clearing_logs_records_the_admin_action(self):
        SystemLog.objects.create(user=self.admin, action='OLD_EVENT')
        request = self.factory.post('/analytics/admin/logs/clear/')
        force_authenticate(request, user=self.admin)

        response = ClearSystemLogsView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(SystemLog.objects.filter(action='OLD_EVENT').exists())
        audit_log = SystemLog.objects.get(action='SYSTEM_LOGS_CLEARED')
        self.assertEqual(audit_log.user, self.admin)
        self.assertEqual(audit_log.details['deleted_count'], 1)


class ActivityLogMiddlewareTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='finance@example.test',
            password='test-password',
            full_name='Finance User',
            role='FINANCE',
        )
        self.factory = RequestFactory()

    def test_authenticated_api_changes_are_logged_with_the_actor_role(self):
        request = self.factory.patch('/api/payments/42/', {'status': 'VERIFIED'})
        request.user = self.user
        middleware = ActivityLogMiddleware(lambda _request: HttpResponse(status=200))

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        log = SystemLog.objects.get(action='API_PATCH', user=self.user)
        self.assertEqual(log.details['path'], '/api/payments/42/')
        self.assertEqual(log.details['role'], 'FINANCE')
        self.assertEqual(log.details['status_code'], 200)

    def test_authenticated_api_reads_are_logged(self):
        request = self.factory.get('/api/courses/')
        request.user = self.user
        middleware = ActivityLogMiddleware(lambda _request: HttpResponse(status=200))

        response = middleware(request)

        self.assertEqual(response.status_code, 200)
        log = SystemLog.objects.get(action='API_GET', user=self.user)
        self.assertEqual(log.details['path'], '/api/courses/')
